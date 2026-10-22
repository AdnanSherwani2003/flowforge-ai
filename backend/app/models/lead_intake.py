"""Two independent identities; historical lead rows remain immutable."""
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class LeadIdentity(Base):
    __tablename__ = "lead_identities"
    normalized_email: Mapped[str] = mapped_column(String(255), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False)


class LeadEvent(Base):
    __tablename__ = "lead_events"
    source_event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
