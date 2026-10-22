"""Add separate bounded advisory enrichments without changing ticket rows."""
from alembic import op
import sqlalchemy as sa

revision = "004_ticket_enrichments"
down_revision = "003_workflow_runs_unique"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ticket_enrichments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("model_digest", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36), nullable=True),
        sa.Column("diagnostic_code", sa.String(40), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("ticket_id", "model", "model_digest", "prompt_version", "schema_version", name="uq_ticket_enrichment_version"),
        sa.CheckConstraint("status IN ('processing','succeeded','needs_review','unavailable')", name="ck_enrichment_status"),
        sa.CheckConstraint("category IN ('billing','account_access','technical_issue','shipping','general','unknown')", name="ck_enrichment_category"),
        sa.CheckConstraint("priority IN ('low','medium','high','unknown')", name="ck_enrichment_priority"),
        sa.CheckConstraint("attempts BETWEEN 1 AND 3", name="ck_enrichment_attempts"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_enrichment_confidence"),
        sa.CheckConstraint("(category = 'unknown') = (priority = 'unknown')", name="ck_enrichment_unknowns"),
        sa.CheckConstraint("(status = 'succeeded' AND category <> 'unknown') OR (status <> 'succeeded' AND category = 'unknown')", name="ck_enrichment_advisory_state"),
        sa.CheckConstraint("(status = 'processing' AND lease_token IS NOT NULL AND completed_at IS NULL) OR (status <> 'processing' AND lease_token IS NULL AND completed_at IS NOT NULL)", name="ck_enrichment_lease"),
    )


def downgrade():
    # Explicit operator migration only; never used against application data by tests.
    op.drop_table("ticket_enrichments")
