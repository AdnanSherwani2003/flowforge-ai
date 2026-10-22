import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class TicketEnrichment(Base):
    __tablename__ = "ticket_enrichments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    model_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    reason: Mapped[str] = mapped_column(String(240), nullable=False, default="Enrichment is processing.")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    diagnostic_code: Mapped[str] = mapped_column(String(40), nullable=False, default="processing")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_enrichments_ticket_started_id", "ticket_id", "started_at", "id"),
        UniqueConstraint("ticket_id", "model", "model_digest", "prompt_version", "schema_version", name="uq_ticket_enrichment_version"),
        CheckConstraint("status IN ('processing','succeeded','needs_review','unavailable')", name="ck_enrichment_status"),
        CheckConstraint("category IN ('billing','account_access','technical_issue','shipping','general','unknown')", name="ck_enrichment_category"),
        CheckConstraint("priority IN ('low','medium','high','unknown')", name="ck_enrichment_priority"),
        CheckConstraint("attempts BETWEEN 1 AND 3", name="ck_enrichment_attempts"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_enrichment_confidence"),
        CheckConstraint("(category = 'unknown') = (priority = 'unknown')", name="ck_enrichment_unknowns"),
        CheckConstraint("(status = 'succeeded' AND category <> 'unknown') OR (status <> 'succeeded' AND category = 'unknown')", name="ck_enrichment_advisory_state"),
        CheckConstraint("(status = 'processing' AND lease_token IS NOT NULL AND completed_at IS NULL) OR (status <> 'processing' AND lease_token IS NULL AND completed_at IS NOT NULL)", name="ck_enrichment_lease"),
    )
