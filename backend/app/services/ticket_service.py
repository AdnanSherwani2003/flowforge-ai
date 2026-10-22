import logging
from typing import Tuple, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.models.audit_event import AuditEvent
from app.schemas.ticket import TicketCreate
from app.services.hasher import compute_canonical_hash
from app.services.audit_service import record_audit_event

logger = logging.getLogger("flowforge.ticket_service")


def compute_ticket_canonical_hash(ticket_in: TicketCreate) -> str:
    return compute_canonical_hash({
        "body": ticket_in.body,
        "source_event_id": ticket_in.source_event_id,
        "subject": ticket_in.subject,
    })


def create_or_get_ticket(
    db: Session,
    ticket_in: TicketCreate,
    actor: str = "api_client",
    correlation_id: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> Tuple[Ticket, bool]:
    """Handles idempotent ticket submission:
    - Case 1 (New event): Creates record, returns (ticket, False).
    - Case 2 (Duplicate event, identical payload): Returns (existing_ticket, True).
    - Case 3 (Conflicting event, same source_event_id but different payload): Raises 409 Conflict.
    Safely handles concurrency races via database unique constraints.
    """
    payload_hash = compute_ticket_canonical_hash(ticket_in)

    existing = db.execute(
        select(Ticket).where(Ticket.source_event_id == ticket_in.source_event_id)
    ).scalar_one_or_none()

    if existing is not None:
        if existing.payload_hash == payload_hash:
            record_audit_event(
                db=db,
                entity_id=existing.id,
                event_type="ticket_duplicate_received",
                safe_detail={
                    "source_event_id": ticket_in.source_event_id,
                    "correlation_id": correlation_id,
                    "execution_id": execution_id,
                    "action": "duplicate_event_replayed",
                },
                actor=actor,
            )
            db.commit()
            return existing, True
        else:
            record_audit_event(
                db=db,
                entity_id=existing.id,
                event_type="ticket_conflict_received",
                safe_detail={
                    "source_event_id": ticket_in.source_event_id,
                    "correlation_id": correlation_id,
                    "execution_id": execution_id,
                    "action": "conflicting_payload_rejected",
                    "reason": "payload_hash_mismatch",
                },
                actor=actor,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: source_event_id '{ticket_in.source_event_id}' already exists with different payload content.",
            )

    import uuid
    new_ticket = Ticket(
        id=str(uuid.uuid4()),
        source_event_id=ticket_in.source_event_id,
        subject=ticket_in.subject,
        body=ticket_in.body,
        status="received",
        category="unknown",
        payload_hash=payload_hash,
    )
    db.add(new_ticket)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(Ticket).where(Ticket.source_event_id == ticket_in.source_event_id)
        ).scalar_one_or_none()

        if existing is not None:
            if existing.payload_hash == payload_hash:
                record_audit_event(
                    db=db,
                    entity_id=existing.id,
                    event_type="ticket_duplicate_received",
                    safe_detail={
                        "source_event_id": ticket_in.source_event_id,
                        "correlation_id": correlation_id,
                        "execution_id": execution_id,
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
                    event_type="ticket_conflict_received",
                    safe_detail={
                        "source_event_id": ticket_in.source_event_id,
                        "correlation_id": correlation_id,
                        "execution_id": execution_id,
                        "action": "concurrent_conflict_rejected",
                    },
                    actor=actor,
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflict: source_event_id '{ticket_in.source_event_id}' already exists with different payload content.",
                )
        raise

    record_audit_event(
        db=db,
        entity_id=new_ticket.id,
        event_type="ticket_created",
        safe_detail={
            "source_event_id": new_ticket.source_event_id,
            "correlation_id": correlation_id,
            "execution_id": execution_id,
            "subject_length": len(new_ticket.subject),
            "body_length": len(new_ticket.body),
            "category": new_ticket.category,
            "status": new_ticket.status,
        },
        actor=actor,
    )
    db.commit()
    db.refresh(new_ticket)
    return new_ticket, False


def get_ticket_by_id(db: Session, ticket_id: str) -> Optional[Ticket]:
    return db.execute(select(Ticket).where(Ticket.id == ticket_id)).scalar_one_or_none()


def list_tickets(db: Session, limit: int = 20, offset: int = 0) -> Tuple[List[Ticket], int]:
    total = db.scalar(select(func.count(Ticket.id))) or 0
    stmt = (
        select(Ticket)
        .order_by(desc(Ticket.created_at), desc(Ticket.id))
        .limit(limit)
        .offset(offset)
    )
    items = list(db.scalars(stmt).all())
    return items, total


def get_ticket_audit_trail(db: Session, ticket_id: str) -> List[AuditEvent]:
    ticket = get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found",
        )
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.entity_id == ticket_id)
        .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
    )
    return list(db.scalars(stmt).all())
