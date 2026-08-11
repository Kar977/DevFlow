"""add tasks.completed_at

`Task` completion time was approximated by `updated_at`, which drifts every
time a done task is edited afterwards (assignee change, description fix,
etc.) — silently corrupting velocity, streaks, and summary metrics. This
adds a real `completed_at` column, set once by the service on the
`-> done` transition and cleared on the `done ->` transition, with a
backfill for existing done rows so historical metrics stay continuous.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE tasks SET completed_at = updated_at WHERE status = 'done'")


def downgrade() -> None:
    op.drop_column("tasks", "completed_at")
