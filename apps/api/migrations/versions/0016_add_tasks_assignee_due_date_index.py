"""add tasks assignee_id/due_date composite index

The new org-wide "my overdue tasks" query (TaskRepository.list_overdue_for_user
/ count_overdue_for_user) filters by assignee_id and a due_date range, then
sorts by due_date — a pattern the existing single-column assignee_id index
cannot satisfy efficiently. A composite index on (assignee_id, due_date)
covers both the filter and the sort in one pass.

Not created concurrently: Alembic runs each migration inside a transaction
here, and a brief write lock on `tasks` while building the index is
acceptable at this table's current size.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-13 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tasks_assignee_id_due_date", "tasks", ["assignee_id", "due_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_assignee_id_due_date", table_name="tasks")
