"""add reports.organization_id

Org-scoped report types (starting with pr_flow_weekly, audit gap #9) need to
record which organization they were generated for — the payload alone is not
queryable and, if generation fails before a payload exists, the scope would
be lost entirely. Nullable: the existing user-scoped productivity report
types (weekly_summary, project_status, productivity_overview) leave it null.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column("organization_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_reports_organization_id", "reports", ["organization_id"])
    op.create_foreign_key(
        "reports_organization_id_fkey",
        "reports",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("reports_organization_id_fkey", "reports", type_="foreignkey")
    op.drop_index("ix_reports_organization_id", table_name="reports")
    op.drop_column("reports", "organization_id")
