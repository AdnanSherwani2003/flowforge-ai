"""001_initial_data_contracts

Revision ID: 001_initial_data_contracts
Revises:
Create Date: 2026-10-20 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_data_contracts"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. tickets table
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="received"),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="unknown"),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_source_event_id", "tickets", ["source_event_id"], unique=True)
    op.create_index("ix_tickets_payload_hash", "tickets", ["payload_hash"], unique=False)
    op.create_index("ix_tickets_created_at_id", "tickets", ["created_at", "id"], unique=False)

    # 2. leads table
    op.create_table(
        "leads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column("normalized_email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="new"),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_source_event_id", "leads", ["source_event_id"], unique=True)
    op.create_index("ix_leads_normalized_email", "leads", ["normalized_email"], unique=False)
    op.create_index("ix_leads_created_at_id", "leads", ["created_at", "id"], unique=False)

    # 3. audit_events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("safe_detail", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"], unique=False)
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)
    op.create_index("ix_audit_events_entity_timestamp", "audit_events", ["entity_id", "timestamp"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("leads")
    op.drop_table("tickets")
