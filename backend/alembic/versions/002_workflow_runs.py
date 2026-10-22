"""002_workflow_runs

Revision ID: 002_workflow_runs
Revises: 001_initial_data_contracts
Create Date: 2026-10-21 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_workflow_runs"
down_revision: Union[str, None] = "001_initial_data_contracts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow_name", sa.String(length=100), nullable=False, server_default="support_ticket_intake"),
        sa.Column("execution_id", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), nullable=True),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("safe_detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_runs_execution_id", "workflow_runs", ["execution_id"], unique=False)
    op.create_index("ix_workflow_runs_correlation_id", "workflow_runs", ["correlation_id"], unique=False)
    op.create_index("ix_workflow_runs_source_event_id", "workflow_runs", ["source_event_id"], unique=False)
    op.create_index("ix_workflow_runs_ticket_id", "workflow_runs", ["ticket_id"], unique=False)
    op.create_index("ix_workflow_runs_outcome", "workflow_runs", ["outcome"], unique=False)
    op.create_index("ix_workflow_runs_created_at", "workflow_runs", ["created_at"], unique=False)
    op.create_index("ix_workflow_runs_created_at_id", "workflow_runs", ["created_at", "id"], unique=False)
    op.create_index("ix_workflow_runs_corr_exec", "workflow_runs", ["correlation_id", "execution_id"], unique=False)


def downgrade() -> None:
    op.drop_table("workflow_runs")
