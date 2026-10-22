import uuid
from typing import Any, Dict, Optional
from sqlalchemy import String, Integer, DateTime, JSON, func, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workflow_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="support_ticket_intake",
    )
    execution_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    correlation_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    source_event_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    ticket_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    outcome: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    safe_detail: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_workflow_runs_created_at_id", "created_at", "id"),
        Index("ix_workflow_runs_corr_exec", "correlation_id", "execution_id"),
        UniqueConstraint("workflow_name", "execution_id", name="uq_workflow_runs_workflow_execution"),
    )
