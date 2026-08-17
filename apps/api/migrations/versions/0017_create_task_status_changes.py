"""create task_status_changes table

`Task.status` was overwritten in place, with no record of when a task
entered a given status or how it got there — the only trace of a transition
was `completed_at` (0014), a denormalized cache of a single one. This adds a
`task_status_changes` audit table, written by `TaskService` on task creation
and on every real `-> status` transition in `update_task`, laying the
groundwork for a future status-history endpoint and cycle-time-per-stage
metric without further data migration.

Existing tasks are backfilled with a "created" row (from_status NULL,
to_status the task's current `status` at migration time is wrong for tasks
that have since moved on, so we backfill from the earliest known fact
instead: every task got a `backlog` status on creation per
`TaskRepository.create`) and, where known, a `-> done` row from
`completed_at`. `from_status` stays NULL on both backfilled rows — the real
prior status isn't recoverable from existing data, so we don't invent one.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_status_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=True),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_status_changes_task_id", "task_status_changes", ["task_id"]
    )
    op.create_index(
        "ix_task_status_changes_task_id_changed_at",
        "task_status_changes",
        ["task_id", "changed_at"],
    )

    # Backfill 1: a "created" row for every existing task. Every task starts
    # life as "backlog" (TaskRepository.create hardcodes it), so that's the
    # only to_status backfill can assert without guessing.
    op.execute(
        """
        INSERT INTO task_status_changes
            (id, task_id, from_status, to_status, changed_by, changed_at)
        SELECT gen_random_uuid(), id, NULL, 'backlog', created_by, created_at
        FROM tasks
        """
    )
    # Backfill 2: a "-> done" row wherever completed_at tells us it happened,
    # and when. from_status stays unknown/NULL — a task could have reached
    # "done" from any prior status and existing data can't say which.
    op.execute(
        """
        INSERT INTO task_status_changes
            (id, task_id, from_status, to_status, changed_by, changed_at)
        SELECT gen_random_uuid(), id, NULL, 'done', NULL, completed_at
        FROM tasks
        WHERE completed_at IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_status_changes_task_id_changed_at", table_name="task_status_changes"
    )
    op.drop_index("ix_task_status_changes_task_id", table_name="task_status_changes")
    op.drop_table("task_status_changes")
