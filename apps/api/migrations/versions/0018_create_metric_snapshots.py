"""create metric_snapshots table

Every metric in the codebase is computed on the fly, in Python, from raw
`tasks`/`work_sessions`/`pull_requests` rows for a "current vs previous
period" window (`MetricsService`, `PRMetricsService`). There is no way to see
a trend longer than that, and no persisted history to build one from. This
adds `metric_snapshots`: one row per *closed* ISO week (Monday-anchored, UTC)
per metric, generic across both the user-scoped productivity metrics and the
org-scoped PR-flow KPIs (`scope` discriminates which owner column applies).

Unlike prior migrations that backfill historical rows via `op.execute`, this
one intentionally does **not** backfill: there is no scheduler in this
codebase to run a batch job, so history is built lazily by
`MetricSnapshotService` the first time a trend endpoint is asked to cover a
given week — see that module's docstring for the algorithm. The table starts
empty on deploy; this is expected, not an oversight.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-16 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("metric_key", sa.String(50), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(scope = 'user' AND user_id IS NOT NULL AND org_id IS NULL) OR "
            "(scope = 'org' AND org_id IS NOT NULL AND user_id IS NULL)",
            name="ck_metric_snapshots_scope_matches_owner",
        ),
    )
    # Partial unique indexes, one per scope: a plain UNIQUE would let NULL
    # user_id/org_id duplicate freely (SQL NULL <> NULL), so each scope gets
    # its own uniqueness rule over the column that actually applies to it.
    # Same pattern as 0013_unique_active_work_session.
    op.create_index(
        "uq_metric_snapshots_user_metric_week",
        "metric_snapshots",
        ["user_id", "metric_key", "period_start"],
        unique=True,
        postgresql_where=sa.text("scope = 'user'"),
    )
    op.create_index(
        "uq_metric_snapshots_org_metric_week",
        "metric_snapshots",
        ["org_id", "metric_key", "period_start"],
        unique=True,
        postgresql_where=sa.text("scope = 'org'"),
    )
    # Backs the per-owner trend read: fetch every captured week for this
    # user/org across all metric keys in one query.
    op.create_index(
        "ix_metric_snapshots_user_id_period_start",
        "metric_snapshots",
        ["user_id", "period_start"],
    )
    op.create_index(
        "ix_metric_snapshots_org_id_period_start",
        "metric_snapshots",
        ["org_id", "period_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_metric_snapshots_org_id_period_start", table_name="metric_snapshots"
    )
    op.drop_index(
        "ix_metric_snapshots_user_id_period_start", table_name="metric_snapshots"
    )
    op.drop_index("uq_metric_snapshots_org_metric_week", table_name="metric_snapshots")
    op.drop_index("uq_metric_snapshots_user_metric_week", table_name="metric_snapshots")
    op.drop_table("metric_snapshots")
