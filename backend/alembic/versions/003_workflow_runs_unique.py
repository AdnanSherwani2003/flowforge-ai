"""003_workflow_runs_unique

Revision ID: 003_workflow_runs_unique
Revises: 002_workflow_runs
Create Date: 2026-10-22 17:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_workflow_runs_unique"
down_revision: Union[str, None] = "002_workflow_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_workflow_runs_workflow_execution",
        "workflow_runs",
        ["workflow_name", "execution_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_workflow_runs_workflow_execution",
        "workflow_runs",
        type_="unique",
    )
