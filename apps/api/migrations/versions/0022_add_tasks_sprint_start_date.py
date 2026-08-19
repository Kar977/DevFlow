"""add tasks.sprint_start_date

Lets a task be assigned to a sprint under the organization's cadence
(`organization_settings.sprint_length_days`/`sprint_anchor_date`). NULL means
"backlog" — the task isn't assigned to any sprint, which is also what every
existing row means after this migration, since there's nothing to backfill
it from.

The value is the sprint's *start date*, not an FK to a `sprints` table —
sprints aren't a persisted entity in this schema, they're computed from the
cadence (see `core.services.period.sprint_series`). `TaskService` validates
on write that the date is actually a sprint boundary under the org's current
cadence; a later cadence change is deliberately NOT cascaded here or
anywhere else — see `TaskService._validate_sprint_start_date` for why reads
never re-validate.

Composite index on (project_id, sprint_start_date) rather than a standalone
one on sprint_start_date: every task query is already project-scoped
(`TaskRepository.list_for_project`/`count_for_project`), and the column has
low cardinality across the whole table, so the composite is what actually
serves the "tasks in this sprint" / "backlog" filters. Postgres indexes NULLs
in a btree, so the same index covers `sprint_start_date IS NULL` too.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-19 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("sprint_start_date", sa.Date(), nullable=True))
    op.create_index(
        "ix_tasks_project_id_sprint_start_date",
        "tasks",
        ["project_id", "sprint_start_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_project_id_sprint_start_date", table_name="tasks")
    op.drop_column("tasks", "sprint_start_date")
