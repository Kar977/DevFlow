"""rename work_sessions.duration_minutes to duration_seconds

Stores sub-minute precision so short start/stop intervals are no longer
floored away. Existing values are converted from minutes to seconds.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "work_sessions",
        "duration_minutes",
        type_=sa.Integer(),
        existing_type=sa.Integer(),
        existing_nullable=True,
        postgresql_using="duration_minutes * 60",
    )
    op.alter_column(
        "work_sessions",
        "duration_minutes",
        new_column_name="duration_seconds",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "work_sessions",
        "duration_seconds",
        new_column_name="duration_minutes",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "work_sessions",
        "duration_minutes",
        type_=sa.Integer(),
        existing_type=sa.Integer(),
        existing_nullable=True,
        postgresql_using="duration_minutes / 60",
    )
