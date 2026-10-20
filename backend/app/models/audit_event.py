import uuid
from typing import Any, Dict
from sqlalchemy import String, DateTime, JSON, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    entity_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    actor: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="system",
    )
    timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    safe_detail: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    __table_args__ = (
        Index("ix_audit_events_entity_timestamp", "entity_id", "timestamp"),
    )
