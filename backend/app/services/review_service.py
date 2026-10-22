"""Durable reviews; immutable final decisions; no external actions."""
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, func, exists, and_, or_, text
from sqlalchemy.orm import aliased, load_only
from app.models.review import Review
from app.models.ticket import Ticket
from app.models.ticket_enrichment import TicketEnrichment as Enrichment
from app.models.audit_event import AuditEvent
from app.services.audit_service import record_audit_event


def lock_ticket(db, ticket_id):
    # All enrichment claims and decisions use this same per-ticket transaction lock.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:ticket, 0))"), {"ticket": ticket_id})


def ensure_review(db, enrichment):
    if enrichment.status == "processing":
        return
    row = db.execute(select(Review).where(Review.enrichment_id == enrichment.id)).scalar_one_or_none()
    target = "pending" if enrichment.status == "succeeded" else "attention"
    if row is None:
        row = Review(id=str(uuid4()), enrichment_id=enrichment.id, status=target, revision=1)
        db.add(row)
        db.flush()
        event = "review_created"
    elif row.status == "attention" and target == "pending":
        row.status = target
        row.revision += 1
        db.flush()
        event = "review_ready"
    else:
        return
    record_audit_event(db, enrichment.ticket_id, event,
                       {"review_id": row.id, "enrichment_id": enrichment.id, "status": target, "revision": row.revision},
                       actor="review_system")


def latest_condition():
    newer = aliased(Enrichment)
    return ~exists(select(newer.id).where(
        newer.ticket_id == Enrichment.ticket_id,
        or_(newer.started_at > Enrichment.started_at,
            and_(newer.started_at == Enrichment.started_at, newer.id > Enrichment.id))))


def joined():
    return select(Review, Enrichment, Ticket).join(Enrichment, Review.enrichment_id == Enrichment.id).join(Ticket, Enrichment.ticket_id == Ticket.id)


def serialize(row, enrichment, ticket, *, superseded=False, detail=False):
    value = {
        "id": row.id, "ticket_id": ticket.id, "enrichment_id": enrichment.id,
        "status": row.status, "revision": row.revision, "reviewer": row.reviewer,
        "note": row.note, "decided_at": row.decided_at, "created_at": row.created_at,
        "updated_at": row.updated_at, "subject": ticket.subject,
        "category": enrichment.category, "priority": enrichment.priority,
        "enrichment_status": enrichment.status, "model": enrichment.model,
        "prompt_version": enrichment.prompt_version, "schema_version": enrichment.schema_version,
        "superseded": superseded, "reviewable": row.status == "pending" and enrichment.status == "succeeded" and not superseded,
    }
    if detail:
        value.update(ticket={"id": ticket.id, "subject": ticket.subject, "body": ticket.body,
                              "source_event_id": ticket.source_event_id, "status": ticket.status,
                              "category": ticket.category, "created_at": ticket.created_at},
                     enrichment={"id": enrichment.id, "status": enrichment.status,
                                 "category": enrichment.category, "priority": enrichment.priority,
                                 "reason": enrichment.reason, "model": enrichment.model,
                                 "model_digest": enrichment.model_digest, "prompt_version": enrichment.prompt_version,
                                 "schema_version": enrichment.schema_version, "diagnostic_code": enrichment.diagnostic_code,
                                 "confidence": enrichment.confidence})
    return value


def get_detail(db, review_id):
    result = db.execute(joined().where(Review.id == review_id)).one_or_none()
    if result is None:
        raise HTTPException(404, "Review not found")
    row, enrichment, ticket = result
    current = db.scalar(select(Enrichment.id).where(Enrichment.ticket_id == ticket.id).order_by(Enrichment.started_at.desc(), Enrichment.id.desc()).limit(1))
    return serialize(row, enrichment, ticket, superseded=current != enrichment.id, detail=True)


def list_reviews(db, status=None, limit=20, offset=0, ticket_id=None, final_only=False):
    query = joined()
    if final_only:
        query = query.where(Review.status.in_(["approved", "rejected"]))
    if status:
        query = query.where(Review.status == status)
    if status in ("pending", "attention"):
        query = query.where(latest_condition())
    if ticket_id:
        query = query.where(Ticket.id == ticket_id)
    count = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.add_columns(latest_condition().label("is_current")).options(load_only(Ticket.id, Ticket.subject)).order_by(Review.created_at.desc(), Review.id.desc()).limit(limit).offset(offset)).all()
    items = []
    for row, enrichment, ticket, is_current in rows:
        items.append(serialize(row, enrichment, ticket, superseded=not is_current))
    return {"items": items, "total": count, "limit": limit, "offset": offset}


def decide(db, review_id, payload, decision, reviewer):
    if decision == "rejected" and not payload.note:
        raise HTTPException(422, "A rejection reason is required")
    initial = db.get(Review, review_id)
    if initial is None:
        raise HTTPException(404, "Review not found")
    enrichment = db.get(Enrichment, initial.enrichment_id)
    lock_ticket(db, enrichment.ticket_id)
    row = db.execute(select(Review).where(Review.id == review_id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    if payload.enrichment_id != row.enrichment_id:
        raise HTTPException(409, "The enrichment version does not match this review")
    if row.status in ("approved", "rejected"):
        if row.status == decision and row.reviewer == reviewer and row.note == payload.note:
            db.commit()
            return {**get_detail(db, review_id), "duplicate": True}
        raise HTTPException(409, "A final decision already exists")
    if payload.expected_revision != row.revision:
        raise HTTPException(409, "The review changed; reload before deciding")
    latest = db.scalar(select(Enrichment.id).where(Enrichment.ticket_id == enrichment.ticket_id).order_by(Enrichment.started_at.desc(), Enrichment.id.desc()).limit(1))
    if latest != enrichment.id or enrichment.status != "succeeded" or row.status != "pending":
        raise HTTPException(409, "No current valid recommendation is available for this decision")
    row.status = decision
    row.reviewer = reviewer
    row.note = payload.note
    row.decided_at = datetime.now(timezone.utc)
    row.revision += 1
    db.flush()
    record_audit_event(db, enrichment.ticket_id, "review_" + decision,
                       {"review_id": row.id, "enrichment_id": row.enrichment_id, "status": decision, "revision": row.revision},
                       actor=reviewer)
    db.commit()
    return {**get_detail(db, review_id), "duplicate": False}


def history(db, review_id):
    detail = get_detail(db, review_id)
    events = db.scalars(select(AuditEvent).where(
        AuditEvent.entity_id == detail["ticket_id"], AuditEvent.safe_detail["review_id"].as_string() == review_id,
    ).order_by(AuditEvent.safe_detail["revision"].as_integer(), AuditEvent.timestamp, AuditEvent.id)).all()
    return {"review_id": review_id, "items": [
        {"id": e.id, "event": e.event_type, "reviewer": e.actor, "timestamp": e.timestamp,
         "status": e.safe_detail.get("status"), "revision": e.safe_detail.get("revision")} for e in events]}


def summary(db):
    counts = dict(db.execute(select(Review.status, func.count()).group_by(Review.status)).all())
    active = dict(db.execute(select(Review.status, func.count()).join(Enrichment).where(latest_condition()).group_by(Review.status)).all())
    return {"total_tickets": db.scalar(select(func.count(Ticket.id))),
            "pending": active.get("pending", 0), "attention": active.get("attention", 0),
            "approved": counts.get("approved", 0), "rejected": counts.get("rejected", 0),
            "enrichment": dict(db.execute(select(Enrichment.status, func.count()).group_by(Enrichment.status)).all())}
