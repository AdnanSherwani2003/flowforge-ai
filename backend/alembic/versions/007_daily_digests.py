"""Add immutable daily aggregates; no historical business-table backfill."""
from alembic import op
import sqlalchemy as sa

revision = "007_daily_digests"
down_revision = "006_lead_intake"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daily_digests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reporting_date", sa.Date(), nullable=False),
        sa.Column("reporting_timezone", sa.String(64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics_version", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("execution_id", sa.String(100)),
        sa.UniqueConstraint("reporting_date", "reporting_timezone", name="uq_digest_date_timezone"),
        sa.CheckConstraint("period_end > period_start", name="ck_digest_period"),
        sa.CheckConstraint("status = 'ready'", name="ck_digest_status"),
        sa.CheckConstraint("metrics_version = 1", name="ck_digest_metrics_version"),
    )
    op.create_index("ix_daily_digests_date_id", "daily_digests", ["reporting_date", "id"])
    op.add_column("workflow_runs", sa.Column("digest_id", sa.String(36)))
    op.create_index("ix_workflow_runs_digest_id", "workflow_runs", ["digest_id"])


def downgrade():
    # Test-schema rollback only. Retain live reports and their frozen evidence.
    op.drop_index("ix_workflow_runs_digest_id", table_name="workflow_runs")
    op.drop_column("workflow_runs", "digest_id")
    op.drop_table("daily_digests")
