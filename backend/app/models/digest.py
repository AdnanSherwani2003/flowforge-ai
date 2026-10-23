"""Immutable aggregate report, never a copy of customer content."""
import uuid
from datetime import date, datetime
from sqlalchemy import String, Integer, Date, DateTime, JSON, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class DailyDigest(Base):
    __tablename__ = "daily_digests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reporting_date: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    __table_args__ = (
        UniqueConstraint("reporting_date", "reporting_timezone", name="uq_digest_date_timezone"),
        CheckConstraint("period_end > period_start", name="ck_digest_period"),
        CheckConstraint("status = 'ready'", name="ck_digest_status"),
        CheckConstraint("metrics_version = 1", name="ck_digest_metrics_version"),
        Index("ix_daily_digests_date_id", "reporting_date", "id"),
    )
