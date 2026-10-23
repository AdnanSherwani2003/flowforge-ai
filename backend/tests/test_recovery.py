import asyncio
import uuid
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import TimeoutError as PoolTimeout
from app.api import system
from app.core.config import settings
from app.core import reviewer_auth
from app.services import enrichment_service as enrich, ollama_client as ai
from app.models.review import Review
from app.models.audit_event import AuditEvent
from datetime import datetime, timezone, timedelta


@pytest.mark.parametrize("available,code,state", [(True, 200, "ready"), (False, 503, "unavailable")])
def test_readiness_separate_from_liveness(client, monkeypatch, available, code, state):
    monkeypatch.setattr(system, "check_database_health", lambda: available)
    response = client.get("/ready")
    assert response.status_code == code and response.json()["status"] == state
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/health").status_code == 200


def test_pool_exhaustion_is_sanitized_retryable(client, monkeypatch):
    from app.api import tickets
    def fail(*args, **kwargs):
        raise PoolTimeout("PRIVATE_DATABASE_CANARY")
    monkeypatch.setattr(tickets.ticket_service, "create_or_get_ticket", fail)
    response = client.post("/api/tickets", json={
        "source_event_id": uuid.uuid4().hex, "subject": "Synthetic", "body": "Test"})
    assert response.status_code == 503 and response.headers["Retry-After"] == "2"
    assert "PRIVATE_DATABASE_CANARY" not in response.text


@pytest.mark.parametrize("mode,expected", [("disabled", "disabled"), ("missing", "model_unavailable"),
                                          ("available", "available"), ("outage", "unavailable")])
def test_optional_diagnostic_auth_and_bounded_probe(client, monkeypatch, mode, expected):
    assert client.get("/api/reviewer/dependencies").status_code == 401
    monkeypatch.setattr(settings, "REVIEWER_USERNAME", "synthetic")
    monkeypatch.setattr(settings, "REVIEWER_PASSWORD_HASH", "configured")
    monkeypatch.setattr(settings, "REVIEWER_SESSION_SECRET", "s" * 48)
    monkeypatch.setattr(settings, "ENRICHMENT_ENABLED", mode != "disabled")
    async def tags(*args):
        if mode == "outage":
            await asyncio.sleep(3)
        return {"models": [{"name": settings.OLLAMA_MODEL,
                            "digest": settings.OLLAMA_MODEL_DIGEST}]} if mode == "available" else {}
    monkeypatch.setattr(system, "_bounded_json", tags)
    token = reviewer_auth.serializer().dumps({"sub": "synthetic"})
    response = client.get("/api/reviewer/dependencies", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200 and response.json() == {
        "ollama": expected, "required_for_readiness": False}
    assert response.headers["Cache-Control"] == "private, no-store"


def test_cancelled_inference_requires_explicit_lease_recovery(client, db_session, monkeypatch):
    ticket_id = client.post("/api/tickets", json={
        "source_event_id": uuid.uuid4().hex, "subject": "Synthetic", "body": "Test"}).json()["id"]
    async def interrupted(*args):
        raise asyncio.CancelledError()
    monkeypatch.setattr(ai, "classify_ticket", interrupted)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(enrich.enrich_ticket(db_session, ticket_id))
    row = enrich.get_enrichment(db_session, ticket_id)
    old_token = row.lease_token
    assert row.status == "processing" and row.attempts == 1
    row.started_at = datetime.now(timezone.utc) - timedelta(seconds=121)
    db_session.commit()
    expired, token, *_ = enrich.claim_enrichment(db_session, ticket_id)
    assert token is None and expired.status == "unavailable" and expired.attempts == 1
    review = db_session.scalar(select(Review).where(Review.enrichment_id == row.id))
    assert review.status == "attention"
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type == "ticket_enrichment_interrupted")) == 1
    enrich.claim_enrichment(db_session, ticket_id)
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type == "ticket_enrichment_interrupted")) == 1
    late = enrich.finish_enrichment(db_session, row.id, old_token,
                                   ai.InferenceOutcome("succeeded", "validated"))
    assert late.status == "unavailable"
