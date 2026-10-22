"""One versioned row per ticket; durable claim before bounded network I/O."""
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.ticket import Ticket
from app.models.ticket_enrichment import TicketEnrichment
from app.schemas.enrichment import PROMPT_VERSION, SCHEMA_VERSION, MAX_ATTEMPTS
from app.services import ollama_client
from app.services.audit_service import record_audit_event

LEASE_SECONDS = 120


def _key(ticket_id):
    return (
        TicketEnrichment.ticket_id == ticket_id,
        TicketEnrichment.model == settings.OLLAMA_MODEL,
        TicketEnrichment.model_digest == settings.OLLAMA_MODEL_DIGEST,
        TicketEnrichment.prompt_version == PROMPT_VERSION,
        TicketEnrichment.schema_version == SCHEMA_VERSION,
    )


def get_enrichment(db, ticket_id):
    return db.execute(select(TicketEnrichment).where(*_key(ticket_id))).scalar_one_or_none()


def _expire_lease(db, row):
    if row.status == "processing":
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=LEASE_SECONDS)
        db.execute(update(TicketEnrichment).execution_options(synchronize_session="fetch").where(
            TicketEnrichment.id == row.id, TicketEnrichment.status == "processing",
            TicketEnrichment.started_at <= cutoff,
        ).values(
            status="unavailable", diagnostic_code="lease_expired", completed_at=datetime.now(timezone.utc),
            lease_token=None, reason="Interrupted enrichment requires an explicit retry.",
        ))
        db.commit()
        db.refresh(row)
    return row


def claim_enrichment(db, ticket_id, retry_unavailable=False):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    # Copy only the needed fields before releasing the transaction/connection.
    subject, body = ticket.subject, ticket.body
    row = get_enrichment(db, ticket_id)
    token = str(uuid.uuid4())
    if row is None:
        row = TicketEnrichment(
            ticket_id=ticket_id, model=settings.OLLAMA_MODEL, model_digest=settings.OLLAMA_MODEL_DIGEST,
            prompt_version=PROMPT_VERSION, schema_version=SCHEMA_VERSION, status="processing",
            category="unknown", priority="unknown", reason="Enrichment is processing.",
            attempts=1, lease_token=token, diagnostic_code="processing", started_at=datetime.now(timezone.utc),
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            return row, token, subject, body, False
        except IntegrityError:
            db.rollback()
            row = get_enrichment(db, ticket_id)
            if row is None:
                raise
    row = _expire_lease(db, row)
    if retry_unavailable and row.status == "unavailable" and row.attempts < MAX_ATTEMPTS:
        claimed = db.execute(update(TicketEnrichment).execution_options(synchronize_session="fetch").where(
            TicketEnrichment.id == row.id, TicketEnrichment.status == "unavailable",
            TicketEnrichment.attempts == row.attempts,
        ).values(
            status="processing", attempts=TicketEnrichment.attempts + 1, lease_token=token,
            started_at=datetime.now(timezone.utc), completed_at=None, diagnostic_code="processing",
            reason="Enrichment is processing.", duration_ms=None,
        )).rowcount
        db.commit()
        db.refresh(row)
        if claimed:
            return row, token, subject, body, True
    db.commit()
    return row, None, subject, body, True


def finish_enrichment(db, row_id, token, result, correlation_id=None, execution_id=None):
    changed = db.execute(update(TicketEnrichment).execution_options(synchronize_session="fetch").where(
        TicketEnrichment.id == row_id, TicketEnrichment.status == "processing",
        TicketEnrichment.lease_token == token,
    ).values(
        status=result.status, category=result.category, priority=result.priority, reason=result.reason,
        confidence=result.confidence, diagnostic_code=result.diagnostic_code, duration_ms=result.duration_ms,
        prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
        completed_at=datetime.now(timezone.utc), lease_token=None,
    )).rowcount
    row = db.get(TicketEnrichment, row_id)
    if changed:
        record_audit_event(
            db, entity_id=row.ticket_id, event_type="ticket_enrichment_recorded", actor="local_ai_advisory",
            safe_detail={
                "enrichment_id": row.id, "status": result.status, "diagnostic_code": result.diagnostic_code,
                "model": row.model, "model_digest": row.model_digest, "prompt_version": row.prompt_version,
                "schema_version": row.schema_version, "correlation_id": correlation_id, "execution_id": execution_id,
            },
        )
    db.commit()
    db.refresh(row)
    return row


async def enrich_ticket(db, ticket_id, retry_unavailable=False, correlation_id=None, execution_id=None):
    row, token, subject, body, duplicate = claim_enrichment(db, ticket_id, retry_unavailable)
    if token is not None:
        row_id = row.id
        # Do not hold a database connection or row lock during model inference.
        db.commit()
        result = await ollama_client.classify_ticket(subject, body)
        row = finish_enrichment(db, row_id, token, result, correlation_id, execution_id)
    return row, duplicate
