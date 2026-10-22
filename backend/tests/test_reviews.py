import time
import uuid
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from fastapi import HTTPException
from itsdangerous import TimestampSigner
from sqlalchemy import select, func, text, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.core import reviewer_auth as auth
from app.api.reviews import Decision
from app.models.review import Review
from app.models.ticket_enrichment import TicketEnrichment
from app.models.ticket import Ticket
from app.models.audit_event import AuditEvent
from app.services import review_service as reviews, ollama_client as ai
from app.schemas.ticket import TicketCreate
from app.services.ticket_service import create_or_get_ticket
from tests.test_postgres_integration import pg_isolated_engine


@pytest.fixture
def reviewer(monkeypatch):
    monkeypatch.setattr(settings, "REVIEWER_USERNAME", "test-reviewer")
    monkeypatch.setattr(settings, "REVIEWER_PASSWORD_HASH", auth.PASSWORDS.hash("synthetic-password"))
    monkeypatch.setattr(settings, "REVIEWER_SESSION_SECRET", "test-signing-key-" * 4)
    auth._ATTEMPTS.clear()
    yield {"Authorization": "Bearer " + auth.serializer().dumps({"sub": "test-reviewer"})}
    auth._ATTEMPTS.clear()


def make_review(client, db, monkeypatch, status="succeeded"):
    async def fake(*args, **kwargs):
        return ai.InferenceOutcome(status, "validated" if status == "succeeded" else "invalid_output",
            category="billing" if status == "succeeded" else "unknown",
            priority="medium" if status == "succeeded" else "unknown", reason="Synthetic generic explanation.")
    monkeypatch.setattr(ai, "classify_ticket", fake)
    ticket = client.post("/api/tickets", json={"source_event_id": "review-" + uuid.uuid4().hex,
        "subject": "Synthetic refund", "body": "Synthetic duplicate charge."}).json()
    result = client.post("/api/tickets/" + ticket["id"] + "/enrich")
    assert result.status_code in (201, 503)
    row = db.scalar(select(Review).where(Review.enrichment_id == result.json()["id"]))
    assert row is not None
    return row, ticket, result.json()


def payload(row, note=None):
    return {"enrichment_id": row.enrichment_id, "expected_revision": row.revision, "note": note}


@pytest.mark.parametrize("route", ["/api/reviews", "/api/reviews/summary", "/api/reviews/missing", "/api/reviews/missing/history"])
def test_review_reads_require_auth(client, route):
    assert client.get(route).status_code == 401


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_decisions_require_auth(client, decision):
    assert client.post("/api/reviews/missing/" + decision, json={"enrichment_id":"x","expected_revision":1,"note":"Reason"}).status_code == 401


def test_login_expiry_invalid_and_throttling(client, reviewer, monkeypatch):
    response = client.post("/api/reviewer/login", json={"username":"test-reviewer","password":"synthetic-password"})
    assert response.status_code == 200 and "no-store" in response.headers["Cache-Control"]
    assert client.get("/api/reviewer/session", headers={"Authorization":"Bearer "+response.json()["token"]}).json()["reviewer"] == "test-reviewer"
    with monkeypatch.context() as patch:
        patch.setattr(TimestampSigner, "get_timestamp", lambda self: int(time.time())-4000)
        old = auth.serializer().dumps({"sub":"test-reviewer"})
    assert client.get("/api/reviews", headers={"Authorization":"Bearer "+old}).status_code == 401
    assert client.get("/api/reviews", headers={"Authorization":"Bearer forged"}).status_code == 401
    assert client.get("/api/reviews", headers={"Authorization":"Bearer "+auth.serializer().dumps({"sub":"other"})}).status_code == 401
    for _ in range(5):
        assert client.post("/api/reviewer/login", json={"username":"test-reviewer","password":"wrong"}).status_code == 401
    assert client.post("/api/reviewer/login", json={"username":"test-reviewer","password":"wrong"}).status_code == 429


@pytest.mark.parametrize("decision,note", [("approve",None),("reject","Recommendation is too urgent.")])
def test_final_decision_idempotency_conflict_history(client, db_session, reviewer, monkeypatch, decision, note):
    row, ticket, enrichment = make_review(client, db_session, monkeypatch)
    original = client.get("/api/tickets/"+ticket["id"]).json()
    body = payload(row, note)
    url = "/api/reviews/"+row.id
    response = client.post(url+"/"+decision, json=body, headers=reviewer)
    assert response.status_code == 200 and response.json()["duplicate"] is False
    assert response.json()["status"] == ("approved" if decision == "approve" else "rejected")
    repeat = client.post(url+"/"+decision, json=body, headers=reviewer)
    assert repeat.status_code == 200 and repeat.json()["duplicate"] is True
    other = "reject" if decision == "approve" else "approve"
    assert client.post(url+"/"+other, json={**body,"note":"Different"}, headers=reviewer).status_code == 409
    assert client.post(url+"/"+decision, json={**body,"note":"Changed"}, headers=reviewer).status_code == 409
    history = client.get(url+"/history", headers=reviewer).json()["items"]
    assert len(history) == 2
    assert history[0]["event"] == "review_created" and history[1]["reviewer"] == "test-reviewer"
    assert client.get("/api/tickets/"+ticket["id"]).json() == original
    assert db_session.get(TicketEnrichment,enrichment["id"]).category == "billing"
    events = db_session.scalars(select(AuditEvent).where(AuditEvent.event_type.in_(["review_approved","review_rejected"]))).all()
    assert len(events) == 1 and "note" not in events[0].safe_detail and "body" not in events[0].safe_detail


@pytest.mark.parametrize("status", ["needs_review","unavailable"])
def test_attention_cannot_be_approved(client, db_session, reviewer, monkeypatch, status):
    row, _, _ = make_review(client, db_session, monkeypatch, status)
    assert row.status == "attention"
    assert client.get("/api/reviews/"+row.id,headers=reviewer).json()["reviewable"] is False
    assert client.post("/api/reviews/"+row.id+"/approve",json=payload(row),headers=reviewer).status_code == 409
    assert client.get("/api/reviews?status=attention",headers=reviewer).json()["total"] == 1


def test_list_filters_pagination_stats_and_empty(client, db_session, reviewer, monkeypatch):
    assert client.get("/api/reviews",headers=reviewer).json()["items"] == []
    first, _, _ = make_review(client, db_session, monkeypatch)
    make_review(client, db_session, monkeypatch)
    make_review(client, db_session, monkeypatch,"needs_review")
    page = client.get("/api/reviews?status=pending&limit=1",headers=reviewer).json()
    second = client.get("/api/reviews?status=pending&limit=1&offset=1",headers=reviewer).json()
    assert page["total"] == 2 and page["items"][0]["id"] != second["items"][0]["id"]
    assert "body" not in page["items"][0]
    assert client.get("/api/reviews?status=invalid",headers=reviewer).status_code == 422
    assert client.get("/api/reviews?limit=51",headers=reviewer).status_code == 422
    stats = client.get("/api/reviews/summary",headers=reviewer).json()
    assert stats["total_tickets"] == 3 and stats["pending"] == 2 and stats["attention"] == 1
    client.post("/api/reviews/"+first.id+"/approve",json=payload(first),headers=reviewer)
    assert client.get("/api/reviews?final_only=true",headers=reviewer).json()["total"] == 1


@pytest.mark.parametrize("note", ["", " ", "x"*501, "line\\nbreak"])
def test_rejection_validation(client, db_session, reviewer, monkeypatch, note):
    row,_,_ = make_review(client,db_session,monkeypatch)
    if note == "line\\nbreak":
        note = "line" + chr(10) + "break"
    assert client.post("/api/reviews/"+row.id+"/reject",json=payload(row,note),headers=reviewer).status_code == 422
    assert db_session.get(Review,row.id).status == "pending"


def test_missing_review_and_stale_revision(client,db_session,reviewer,monkeypatch):
    assert client.get("/api/reviews/missing",headers=reviewer).status_code == 404
    assert client.post("/api/reviews/missing/approve",json={"enrichment_id":"x","expected_revision":1},headers=reviewer).status_code == 404
    row,_,_ = make_review(client,db_session,monkeypatch)
    body=payload(row)
    assert client.post("/api/reviews/"+row.id+"/approve",json={**body,"expected_revision":99},headers=reviewer).status_code == 409
    assert client.post("/api/reviews/"+row.id+"/approve",json={**body,"enrichment_id":str(uuid.uuid4())},headers=reviewer).status_code == 409


def test_new_version_supersedes_pending_but_preserves_final(client, db_session, reviewer, monkeypatch):
    row,_,e = make_review(client,db_session,monkeypatch)
    first_body=payload(row)
    original=db_session.get(TicketEnrichment,e["id"])
    newer=TicketEnrichment(ticket_id=original.ticket_id,model=original.model,model_digest=original.model_digest,
        prompt_version="support-triage-v2",schema_version="1",status="succeeded",category="billing",priority="low",
        reason="Synthetic revised suggestion",diagnostic_code="validated",attempts=1,completed_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc)+timedelta(seconds=1))
    db_session.add(newer);db_session.flush();reviews.ensure_review(db_session,newer);db_session.commit()
    assert client.get("/api/reviews/"+row.id,headers=reviewer).json()["superseded"] is True
    assert client.post("/api/reviews/"+row.id+"/approve",json=first_body,headers=reviewer).status_code == 409
    current=db_session.scalar(select(Review).where(Review.enrichment_id==newer.id))
    assert client.post("/api/reviews/"+current.id+"/approve",json=payload(current),headers=reviewer).status_code == 200
    # A later version does not invalidate the already recorded approval.
    latest=TicketEnrichment(ticket_id=original.ticket_id,model=original.model,model_digest=original.model_digest,
        prompt_version="support-triage-v3",schema_version="1",status="succeeded",category="billing",priority="low",
        reason="Synthetic later version",diagnostic_code="validated",attempts=1,completed_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc)+timedelta(seconds=2))
    db_session.add(latest);db_session.flush();reviews.ensure_review(db_session,latest);db_session.commit()
    preserved=client.get("/api/reviews/"+current.id,headers=reviewer).json()
    assert preserved["status"] == "approved" and preserved["superseded"] is True


@pytest.mark.parametrize("conflicting", [False, True])
def test_real_postgres_review_decision_race(pg_isolated_engine, conflicting):
    with Session(pg_isolated_engine) as db:
        ticket,_=create_or_get_ticket(db,TicketCreate(source_event_id="review-race-"+uuid.uuid4().hex,subject="Synthetic",body="Synthetic"))
        e=TicketEnrichment(ticket_id=ticket.id,model="synthetic:local",model_digest="a"*64,prompt_version="v1",schema_version="1",
            status="succeeded",category="billing",priority="medium",reason="Synthetic",diagnostic_code="validated",attempts=1,
            started_at=datetime.now(timezone.utc),completed_at=datetime.now(timezone.utc))
        db.add(e);db.flush();reviews.ensure_review(db,e);db.commit()
        row=db.scalar(select(Review).where(Review.enrichment_id==e.id))
        review_id=row.id; data=Decision(**payload(row, "Synthetic race reason")); ticket_id=ticket.id
    barrier=threading.Barrier(2)
    def worker(index):
        with Session(pg_isolated_engine) as db:
            barrier.wait(timeout=5)
            try:
                result=reviews.decide(db,review_id,data,"rejected" if conflicting and index else "approved","test-reviewer")
                return 200,result["duplicate"]
            except HTTPException as exc:
                db.rollback();return exc.status_code,False
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(worker,range(2)))
    assert sum(status==200 for status,_ in result)==(1 if conflicting else 2)
    assert sum(status==409 for status,_ in result)==(1 if conflicting else 0)
    with Session(pg_isolated_engine) as db:
        assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.entity_id==ticket_id,AuditEvent.event_type.in_(["review_approved","review_rejected"]))) == 1


def test_migration_backfills_version_bound_reviews(monkeypatch):
    name="test_review_migration_"+uuid.uuid4().hex
    admin=create_engine(settings.sync_database_url,isolation_level="AUTOCOMMIT")
    with admin.connect() as db:db.execute(text("CREATE SCHEMA "+name))
    engine=create_engine(settings.sync_database_url,connect_args={"options":"-csearch_path="+name})
    monkeypatch.setenv("ALEMBIC_SCHEMA",name)
    config=Config("alembic.ini")
    try:
        command.upgrade(config,"004_ticket_enrichments")
        with Session(engine) as db:
            ticket,_=create_or_get_ticket(db,TicketCreate(source_event_id="migration-review",subject="Synthetic",body="Preserve"))
            for status in ("succeeded","needs_review","unavailable"):
                e=TicketEnrichment(ticket_id=ticket.id,model="synthetic:"+status,model_digest="a"*64,prompt_version="v1",schema_version="1",
                    status=status,category="billing" if status=="succeeded" else "unknown",priority="medium" if status=="succeeded" else "unknown",
                    reason="Synthetic",diagnostic_code="fixture",attempts=1,started_at=datetime.now(timezone.utc),completed_at=datetime.now(timezone.utc))
                db.add(e)
            db.commit()
        command.upgrade(config,"head")
        with Session(engine) as db:
            assert db.scalar(select(func.count(Review.id))) == 3
            assert db.scalar(select(func.count(Review.id)).where(Review.status=="pending")) == 1
            assert db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.event_type=="review_created")) == 3
            assert db.scalar(select(Ticket.body)) == "Preserve"
            row=db.scalar(select(Review).limit(1));row.status="approved"
            with pytest.raises(IntegrityError):db.commit()
            db.rollback()
    finally:
        engine.dispose()
        with admin.connect() as db:db.execute(text("DROP SCHEMA "+name+" CASCADE"))
        admin.dispose()

def test_retry_makes_attention_review_ready_and_invalidates_old_revision(client,db_session,reviewer,monkeypatch):
    row,ticket,_=make_review(client,db_session,monkeypatch,"unavailable")
    old=payload(row)
    async def valid(*args,**kwargs):
        return ai.InferenceOutcome("succeeded","validated",category="billing",priority="medium",reason="Generic")
    monkeypatch.setattr(ai,"classify_ticket",valid)
    response=client.post("/api/tickets/"+ticket["id"]+"/enrich?retry_unavailable=true")
    assert response.status_code==200
    db_session.refresh(row)
    assert row.status=="pending" and row.revision==2
    assert client.post("/api/reviews/"+row.id+"/approve",json=old,headers=reviewer).status_code==409
    assert client.post("/api/reviews/"+row.id+"/approve",json=payload(row),headers=reviewer).status_code==200
