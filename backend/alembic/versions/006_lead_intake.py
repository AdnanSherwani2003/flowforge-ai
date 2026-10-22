"""Add lead identity/event registries without rewriting historical leads."""
from alembic import op
import sqlalchemy as sa

revision = "006_lead_intake"
down_revision = "005_reviews"
branch_labels = None
depends_on = None


def upgrade():
    # Exclude legacy writers while taking a consistent backfill snapshot.
    op.execute("LOCK TABLE leads IN SHARE ROW EXCLUSIVE MODE")
    op.create_table(
        "lead_identities",
        sa.Column("normalized_email", sa.String(255), primary_key=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False),
    )
    op.create_table(
        "lead_events",
        sa.Column("source_event_id", sa.String(128), primary_key=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_lead_events_lead_id", "lead_events", ["lead_id"])
    # Earliest creation time, then UUID, is deterministic. Preserve all old IDs
    # and original event-to-lead mappings, even for historical email duplicates.
    op.execute("""
        INSERT INTO lead_identities (normalized_email,lead_id)
        SELECT DISTINCT ON (normalized_email) normalized_email,id
        FROM leads ORDER BY normalized_email,created_at,id
    """)
    op.execute("""
        INSERT INTO lead_events (source_event_id,lead_id,payload_hash)
        SELECT source_event_id,id,payload_hash FROM leads
    """)
    op.add_column("workflow_runs", sa.Column("lead_id", sa.String(36), nullable=True))
    op.create_index("ix_workflow_runs_lead_id", "workflow_runs", ["lead_id"])


def downgrade():
    # Development-only rollback loses event aliases; do not downgrade live data.
    op.drop_index("ix_workflow_runs_lead_id", table_name="workflow_runs")
    op.drop_column("workflow_runs", "lead_id")
    op.drop_table("lead_events")
    op.drop_table("lead_identities")
