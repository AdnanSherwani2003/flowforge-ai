import logging
from typing import Tuple, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.lead import Lead
from app.models.audit_event import AuditEvent
from app.schemas.lead import LeadCreate
from app.services.hasher import compute_canonical_hash
from app.services.audit_service import record_audit_event

logger = logging.getLogger("flowforge.lead_service")


def compute_lead_canonical_hash(lead_in: LeadCreate) -> str:
    return compute_canonical_hash({
        "email": lead_in.email,
        "name": lead_in.name,
        "source_event_id": lead_in.source_event_id,
    })


def create_or_get_lead(
    db: Session,
    lead_in: LeadCreate,
    actor: str = "api_client",
) -> Tuple[Lead, bool]:
    payload_hash = compute_lead_canonical_hash(lead_in)

    existing = db.execute(
        select(Lead).where(Lead.source_event_id == lead_in.source_event_id)
    ).scalar_one_or_none()

    domain = lead_in.email.split("@")[-1] if "@" in lead_in.email else "unknown"

    if existing is not None:
        if existing.payload_hash == payload_hash:
            record_audit_event(
                db=db,
                entity_id=existing.id,
                event_type="lead_duplicate_received",
                safe_detail={
                    "source_event_id": lead_in.source_event_id,
                    "action": "duplicate_lead_event_replayed",
                },
                actor=actor,
            )
            db.commit()
            return existing, True
        else:
            record_audit_event(
                db=db,
                entity_id=existing.id,
                event_type="lead_conflict_received",
                safe_detail={
                    "source_event_id": lead_in.source_event_id,
                    "action": "conflicting_lead_payload_rejected",
                },
                actor=actor,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: source_event_id '{lead_in.source_event_id}' already exists with different payload content.",
            )

    import uuid
    new_lead = Lead(
        id=str(uuid.uuid4()),
        source_event_id=lead_in.source_event_id,
        normalized_email=lead_in.email,
        name=lead_in.name,
        status="new",
        payload_hash=payload_hash,
    )
    db.add(new_lead)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(Lead).where(Lead.source_event_id == lead_in.source_event_id)
        ).scalar_one_or_none()

        if existing is not None:
            if existing.payload_hash == payload_hash:
                record_audit_event(
                    db=db,
                    entity_id=existing.id,
                    event_type="lead_duplicate_received",
                    safe_detail={
                        "source_event_id": lead_in.source_event_id,
                        "action": "concurrent_duplicate_resolved",
                    },
                    actor=actor,
                )
                db.commit()
                return existing, True
            else:
                record_audit_event(
                    db=db,
                    entity_id=existing.id,
                    event_type="lead_conflict_received",
                    safe_detail={
                        "source_event_id": lead_in.source_event_id,
                        "action": "concurrent_conflict_rejected",
                    },
                    actor=actor,
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflict: source_event_id '{lead_in.source_event_id}' already exists with different payload content.",
                )
        raise

    record_audit_event(
        db=db,
        entity_id=new_lead.id,
        event_type="lead_created",
        safe_detail={
            "source_event_id": new_lead.source_event_id,
            "email_domain": domain,
            "status": new_lead.status,
        },
        actor=actor,
    )
    db.commit()
    db.refresh(new_lead)
    return new_lead, False


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
