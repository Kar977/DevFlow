"""add pull_requests.updated_at_github

"Stale PRs" (`PRMetricsService._stale_prs`) has always measured age from
`created_at_github`, which conflates "old" with "abandoned": a PR opened 6
days ago and reviewed an hour ago counts as stale, while a genuinely dead
4-day-old PR does not. This adds GitHub's own "last updated" timestamp
(commits, comments, label changes, etc.) so staleness can be measured from
actual inactivity instead. `TimestampMixin.updated_at` on the same model
cannot serve this purpose — it only reflects when the local row was last
written by a sync run, not GitHub-side activity.

Nullable, no backfill: `GitHubSyncService._sync_repo` already parses
`updated_at` from every pull payload it fetches (see `org_sync.py`), so
existing rows pick this up automatically on their next sync; there is no
scheduler in this codebase to run a batch backfill job, same rationale as
0018/0019/0020.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pull_requests",
        sa.Column("updated_at_github", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pull_requests", "updated_at_github")
