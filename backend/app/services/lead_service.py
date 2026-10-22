"""Deterministic lead intake: event identity before business identity."""
import hashlib
import uuid
from typing import NamedTuple, Optional, Tuple, List
from fastapi import HTTPException
from sqlalchemy import select, func, desc, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.lead import Lead
from app.models.lead_intake import LeadIdentity, LeadEvent
from app.schemas.lead import LeadCreate
from app.services.hasher import compute_canonical_hash
from app.services.audit_service import record_audit_event


class LeadOutcome(NamedTuple):
    lead: Lead
    duplicate: bool
    duplicate_reason: Optional[str]


def compute_lead_canonical_hash(lead_in: LeadCreate) -> str:
    # Preserve Implementation 02 canonical hashes exactly.
    return compute_canonical_hash({
        "email": lead_in.email, "name": lead_in.name,
        "source_event_id": lead_in.source_event_id,
    })


def _lock(db: Session, kind: str, value: str):
    if db.get_bind().dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(
            ("flowforge:lead:" + kind + ":" + value).encode()
        ).digest()[:8], "big", signed=True)
        db.execute(text("SET LOCAL lock_timeout = '3000ms'"))
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def ingest_lead(
    db: Session, lead_in: LeadCreate, actor: str = "api_client",
    correlation_id: Optional[str] = None, execution_id: Optional[str] = None,
) -> LeadOutcome:
    payload_hash = compute_lead_canonical_hash(lead_in)
    trace = {k: v for k, v in {
        "correlation_id": correlation_id, "execution_id": execution_id
    }.items() if v is not None}

    def audit(lead, event_type, action, reason=None):
        detail = {"action": action, **trace}
        if reason:
            detail["duplicate_reason"] = reason
        record_audit_event(db, lead.id, event_type, detail, actor)

    # Fixed lock order: event, then email. Every writer uses the same protocol.
    # Unique PKs/FKs remain the final guard; retry once after a uniqueness race.
    for attempt in range(2):
        try:
            _lock(db, "event", lead_in.source_event_id)
            event = db.get(LeadEvent, lead_in.source_event_id)
            if event:
                lead = db.get(Lead, event.lead_id)
                if event.payload_hash != payload_hash:
                    audit(lead, "lead_conflict_received", "conflicting_lead_payload_rejected")
                    db.commit()
                    raise HTTPException(409, "Source event already exists with different payload content.")
                audit(lead, "lead_duplicate_received", "duplicate_lead_event_replayed", "event")
                db.commit()
                return LeadOutcome(lead, True, "event")

            _lock(db, "email", str(lead_in.email))
            identity = db.get(LeadIdentity, str(lead_in.email))
            if identity:
                lead = db.get(Lead, identity.lead_id)
                reason = "email"
            else:
                lead = Lead(
                    id=str(uuid.uuid4()), source_event_id=lead_in.source_event_id,
                    normalized_email=str(lead_in.email), name=lead_in.name,
                    status="new", payload_hash=payload_hash,
                )
                db.add(lead)
                db.flush()
                db.add(LeadIdentity(normalized_email=lead.normalized_email, lead_id=lead.id))
                reason = None
            # Record even email-duplicate events: their replay/conflict must be durable.
            db.add(LeadEvent(source_event_id=lead_in.source_event_id,
                             lead_id=lead.id, payload_hash=payload_hash))
            audit(lead, "lead_duplicate_received" if reason else "lead_created",
                  "existing_email_preserved" if reason else "new_lead_created", reason)
            db.commit()
            return LeadOutcome(lead, reason is not None, reason)
        except IntegrityError:
            db.rollback()
            if attempt:
                raise
    raise RuntimeError("Unreachable lead intake state")


def create_or_get_lead(
    db: Session, lead_in: LeadCreate, actor: str = "api_client",
) -> Tuple[Lead, bool]:
    """Keep the original Implementation 02 service tuple contract."""
    result = ingest_lead(db, lead_in, actor)
    return result.lead, result.duplicate


def get_lead_by_id(db: Session, lead_id: str) -> Optional[Lead]:
    return db.execute(select(Lead).where(Lead.id == lead_id)).scalar_one_or_none()


def list_leads(db: Session, limit: int = 20, offset: int = 0) -> Tuple[List[Lead], int]:
    total = db.scalar(select(func.count(Lead.id))) or 0
    stmt = (
        select(Lead)
        .order_by(desc(Lead.created_at), desc(Lead.id))
        .limit(limit)
        .offset(offset)
    )
    items = list(db.scalars(stmt).all())
    return items, total
