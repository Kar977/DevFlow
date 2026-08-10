"""widen pull_request_reviews.github_review_id to bigint

GitHub review IDs now routinely exceed the int32 range, which made every
sync that touched a real review crash with an asyncpg OverflowError and
roll back the whole request (no PRs, no reviews, no sync_runs entry).

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "pull_request_reviews",
        "github_review_id",
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "pull_request_reviews",
        "github_review_id",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
        existing_nullable=False,
    )
