"""create github_installations and repositories tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-04 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "github_installations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("account_avatar_url", sa.String(1024), nullable=True),
        sa.Column("repository_selection", sa.String(20), nullable=False),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id"),
    )
    op.create_index(
        "ix_github_installations_organization_id",
        "github_installations",
        ["organization_id"],
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("github_installation_id", sa.Uuid(), nullable=False),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("private", sa.Boolean(), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column(
            "tracked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["github_installation_id"], ["github_installations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "github_installation_id",
            "github_repo_id",
            name="uq_repositories_installation_repo",
        ),
    )
    op.create_index(
        "ix_repositories_organization_id", "repositories", ["organization_id"]
    )
    op.create_index(
        "ix_repositories_github_installation_id",
        "repositories",
        ["github_installation_id"],
    )
    op.create_index("ix_repositories_tracked", "repositories", ["tracked"])


def downgrade() -> None:
    op.drop_index("ix_repositories_tracked", table_name="repositories")
    op.drop_index("ix_repositories_github_installation_id", table_name="repositories")
    op.drop_index("ix_repositories_organization_id", table_name="repositories")
    op.drop_table("repositories")
    op.drop_index(
        "ix_github_installations_organization_id", table_name="github_installations"
    )
    op.drop_table("github_installations")
