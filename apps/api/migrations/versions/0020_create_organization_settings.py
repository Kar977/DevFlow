"""create organization_settings table

PR-flow metrics (``PRMetricsService``) have always used hardcoded windows —
a 5-day stale threshold, 7-day velocity/throughput windows, Monday-anchored
ISO weeks — with no way for an organization to say "we actually run 2-week
sprints starting on a Wednesday". This adds ``organization_settings``: one
optional row per organization holding sprint cadence (``sprint_length_days``,
``sprint_anchor_date``) and the stale-PR threshold, read through
``OrganizationSettingsService.get_effective`` which fills in today's defaults
when no row exists — so every existing organization keeps exactly its current
behaviour until an owner/admin opts in via the new "Metryki" settings tab.

No backfill: the table starts empty on deploy, same rationale as 0018/0019.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column(
            "sprint_length_days", sa.Integer(), nullable=False, server_default="14"
        ),
        sa.Column("sprint_anchor_date", sa.Date(), nullable=True),
        sa.Column(
            "stale_pr_threshold_days", sa.Integer(), nullable=False, server_default="5"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", name="uq_organization_settings_organization_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("organization_settings")
