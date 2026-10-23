"""One database snapshot; frozen first report per completed local day and zone."""
import hashlib
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.models.digest import DailyDigest
from app.models.ticket import Ticket
from app.models.lead import Lead
from app.models.lead_intake import LeadIdentity
from app.models.audit_event import AuditEvent
from app.models.review import Review
from app.models.ticket_enrichment import TicketEnrichment as Enrichment
from app.schemas.digest import DigestMetrics
from app.services.audit_service import record_audit_event
from app.services.review_service import latest_condition

UTC = timezone.utc


def reporting_period(reporting_date=None, zone=None, *, now=None):
    zone = zone or settings.DIGEST_TIMEZONE
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("An aware current timestamp is required")
    local_today = now.astimezone(ZoneInfo(zone)).date()
    day = reporting_date or local_today - timedelta(days=1)
    if day < date(2000, 1, 1) or day >= local_today:
        raise HTTPException(422, "Choose a completed reporting date from 2000-01-01 through yesterday")
    # Construct each local midnight independently: DST days need not be 24 hours.
    start = datetime.combine(day, time.min, tzinfo=ZoneInfo(zone)).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=ZoneInfo(zone)).astimezone(UTC)
    return day, zone, start, end


def _count(model, *conditions):
    return select(func.count()).select_from(model).where(*conditions).scalar_subquery()


def calculate_metrics(db, start, end):
    def during(column):
        return and_(column >= start, column < end)
    dup = AuditEvent.event_type == "lead_duplicate_received"
    reason = AuditEvent.safe_detail["duplicate_reason"].as_string()
    action = AuditEvent.safe_detail["action"].as_string()
    replay = or_(reason == "event", action.in_(["duplicate_lead_event_replayed", "concurrent_duplicate_resolved"]))
    email_match = or_(reason == "email", action == "existing_email_preserved")
    columns = {
        "tickets": _count(Ticket, during(Ticket.created_at)),
        "canonical_leads": select(func.count()).select_from(LeadIdentity).join(Lead, Lead.id == LeadIdentity.lead_id).where(during(Lead.created_at)).scalar_subquery(),
        "lead_created": _count(AuditEvent, during(AuditEvent.timestamp), AuditEvent.event_type == "lead_created"),
        "lead_duplicates": _count(AuditEvent, during(AuditEvent.timestamp), dup),
        "lead_replays": _count(AuditEvent, during(AuditEvent.timestamp), dup, replay),
        # Exclude replay branch if contradictory historical metadata ever appears.
        "lead_email_matches": _count(AuditEvent, during(AuditEvent.timestamp), dup, email_match, ~func.coalesce(replay, False)),
    }
    for status in ("succeeded", "needs_review", "unavailable"):
        columns["enrichment_" + status] = _count(Enrichment, during(Enrichment.completed_at), Enrichment.status == status)
    for status in ("approved", "rejected"):
        columns["review_" + status] = _count(Review, during(Review.decided_at), Review.status == status)
    for status in ("pending", "attention"):
        columns["review_" + status] = select(func.count()).select_from(Review).join(Enrichment, Review.enrichment_id == Enrichment.id).where(Review.status == status, latest_condition()).scalar_subquery()
    columns["enrichment_processing"] = _count(Enrichment, Enrichment.status == "processing")
    # One SELECT means one PostgreSQL MVCC snapshot across every scalar subquery.
    if db.get_bind().dialect.name == "postgresql":
        columns["snapshot_at"] = func.statement_timestamp()
    row = db.execute(select(*(v.label(k) for k, v in columns.items()))).mappings().one()
    generated_at = row.get("snapshot_at") or datetime.now(UTC)
    metrics = DigestMetrics.model_validate({
        "activity": {
            "tickets_created": row["tickets"], "canonical_leads_created": row["canonical_leads"],
            "lead_requests_observed": {
                "created_records": row["lead_created"], "event_replays": row["lead_replays"],
                "email_matches": row["lead_email_matches"],
                "legacy_duplicates": row["lead_duplicates"] - row["lead_replays"] - row["lead_email_matches"],
            },
            "enrichment_results_completed": {s: row["enrichment_" + s] for s in ("succeeded", "needs_review", "unavailable")},
            "review_decisions": {s: row["review_" + s] for s in ("approved", "rejected")},
        },
        "snapshot": {
            "pending_reviews": row["review_pending"], "attention_reviews": row["review_attention"],
            "processing_enrichments": row["enrichment_processing"],
        },
    })
    return metrics, generated_at


def generate_digest(db, reporting_date=None, *, actor="reviewer", correlation_id=None, execution_id=None):
    day, zone, start, end = reporting_period(reporting_date)
    correlation_id = correlation_id or "corr-" + uuid4().hex
    for attempt in range(2):
        try:
            if db.get_bind().dialect.name == "postgresql":
                key = int.from_bytes(hashlib.sha256(f"flowforge:digest:{zone}:{day}".encode()).digest()[:8], "big", signed=True)
                db.execute(text("SET LOCAL lock_timeout = '3000ms'"))
                db.execute(text("SET LOCAL statement_timeout = '5000ms'"))
                db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            row = db.scalar(select(DailyDigest).where(DailyDigest.reporting_date == day, DailyDigest.reporting_timezone == zone))
            duplicate = row is not None
            if row is None:
                metrics, generated_at = calculate_metrics(db, start, end)
                row = DailyDigest(id=str(uuid4()), reporting_date=day, reporting_timezone=zone,
                    period_start=start, period_end=end, generated_at=generated_at,
                    metrics_version=1, metrics=metrics.model_dump(), status="ready",
                    correlation_id=correlation_id, execution_id=execution_id)
                db.add(row)
                db.flush()
            detail = {"reporting_date": day.isoformat(), "reporting_timezone": zone,
                      "correlation_id": correlation_id, "duplicate": duplicate}
            if execution_id:
                detail["execution_id"] = execution_id
            record_audit_event(db, row.id, "digest_replayed" if duplicate else "digest_generated", detail, actor)
            db.commit()
            return row, duplicate
        except IntegrityError:
            db.rollback()
            if attempt:
                raise
    raise RuntimeError("Unreachable digest generation state")


def list_digests(db, reporting_date=None, limit=20, offset=0):
    where = [DailyDigest.reporting_timezone == settings.DIGEST_TIMEZONE]
    if reporting_date:
        where.append(DailyDigest.reporting_date == reporting_date)
    total = db.scalar(select(func.count()).select_from(DailyDigest).where(*where))
    rows = db.scalars(select(DailyDigest).where(*where).order_by(DailyDigest.reporting_date.desc(), DailyDigest.id.desc()).limit(limit).offset(offset)).all()
    return rows, total


def get_digest(db, digest_id):
    row = db.get(DailyDigest, digest_id)
    if row is None:
        raise HTTPException(404, "Daily digest not found")
    return row
