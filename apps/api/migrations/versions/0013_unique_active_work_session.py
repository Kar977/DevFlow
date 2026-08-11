"""enforce at most one open work session per user

A user could end up with more than one row in `work_sessions` where
`ended_at IS NULL` — e.g. two concurrent `POST /tasks/{id}/start` requests
racing past the application-level check. That silently corrupts time
tracking (which one counts?) and, combined with `get_active_for_user`
previously using `scalar_one_or_none()`, could crash every subsequent
`start`/`stop` call for that user with a 500. This adds a partial unique
index so the database rejects the second open session outright.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_work_sessions_active_user",
        "work_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_work_sessions_active_user", table_name="work_sessions")
