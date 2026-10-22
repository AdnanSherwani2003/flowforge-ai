"""Durable version-bound human reviews; additive backfill, no ticket mutations."""
from alembic import op
import sqlalchemy as sa

revision = "005_reviews"
down_revision = "004_ticket_enrichments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enrichment_id", sa.String(36), sa.ForeignKey("ticket_enrichments.id", ondelete="RESTRICT"), unique=True, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reviewer", sa.String(64)),
        sa.Column("note", sa.String(500)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending','approved','rejected','attention')", name="ck_review_status"),
        sa.CheckConstraint("revision >= 1", name="ck_review_revision"),
        sa.CheckConstraint("(status IN ('pending','attention') AND reviewer IS NULL AND note IS NULL AND decided_at IS NULL) OR (status IN ('approved','rejected') AND reviewer IS NOT NULL AND decided_at IS NOT NULL)", name="ck_review_decision"),
        sa.CheckConstraint("status <> 'rejected' OR (note IS NOT NULL AND length(trim(note)) BETWEEN 1 AND 500)", name="ck_review_rejection_note"),
    )
    op.create_index("ix_reviews_status_created_id", "reviews", ["status", "created_at", "id"])
    op.create_index("ix_enrichments_ticket_started_id", "ticket_enrichments", ["ticket_id", "started_at", "id"])
    op.execute("""
        INSERT INTO reviews (id,enrichment_id,status,revision)
        SELECT gen_random_uuid()::text,id,CASE WHEN status='succeeded' THEN 'pending' ELSE 'attention' END,1
        FROM ticket_enrichments WHERE status <> 'processing'
    """)
    op.execute("""
        INSERT INTO audit_events (id,entity_id,event_type,actor,safe_detail)
        SELECT gen_random_uuid()::text,e.ticket_id,'review_created','review_system',
               json_build_object('review_id',r.id,'enrichment_id',e.id,'status',r.status,'revision',r.revision)
        FROM reviews r JOIN ticket_enrichments e ON e.id=r.enrichment_id
    """)


def downgrade():
    # Only exercised in fresh isolated test schemas; retain live review data.
    op.drop_index("ix_enrichments_ticket_started_id", table_name="ticket_enrichments")
    op.drop_table("reviews")
