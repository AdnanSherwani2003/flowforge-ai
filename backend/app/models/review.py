import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, CheckConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enrichment_id: Mapped[str] = mapped_column(String(36), ForeignKey("ticket_enrichments.id", ondelete="RESTRICT"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviewer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','attention')", name="ck_review_status"),
        CheckConstraint("revision >= 1", name="ck_review_revision"),
        CheckConstraint("(status IN ('pending','attention') AND reviewer IS NULL AND note IS NULL AND decided_at IS NULL) OR (status IN ('approved','rejected') AND reviewer IS NOT NULL AND decided_at IS NOT NULL)", name="ck_review_decision"),
        CheckConstraint("status <> 'rejected' OR (note IS NOT NULL AND length(trim(note)) BETWEEN 1 AND 500)", name="ck_review_rejection_note"),
        Index("ix_reviews_status_created_id", "status", "created_at", "id"),
    )
