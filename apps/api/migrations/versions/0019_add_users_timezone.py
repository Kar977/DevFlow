"""add users.timezone

Every metrics computation (`MetricsService`, `MetricSnapshotService`) buckets
by UTC calendar day/week regardless of where the user actually is, which is
wrong for anyone outside UTC: work done late evening or after midnight local
time can land on the wrong day, or even the wrong ISO week. This adds an
optional IANA zone name to `users` so the metrics layer can bucket in the
user's own local time instead.

The column is nullable with no server default and this migration does not
backfill it. `NULL` is a first-class value meaning "unknown timezone", and
every reader treats that identically to `"UTC"` (see
`devflow_api.core.services.period.resolve_tz`) — so existing rows, and any
user who never sets a timezone, keep exactly today's UTC-bucketed behaviour.
The frontend detects the browser's timezone and PATCHes it once via
`/auth/me`; there is no batch job here for the same reason 0018 doesn't
backfill snapshots.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
