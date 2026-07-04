"""rescope pull_requests to repositories and sync_runs to organizations

Old rows are dropped instead of migrated: they were user-scoped, had no
repository linkage, and stored the PR number in github_pr_id, so they cannot
satisfy the new keys.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-04 00:00:00.000000
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column[Any]]:
    return [
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
    ]


def _create_reviews_table() -> None:
    op.create_table(
        "pull_request_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pull_request_id", sa.Uuid(), nullable=False),
        sa.Column("github_review_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_login", sa.String(255), nullable=False),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["pull_request_id"], ["pull_requests.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pull_request_id",
            "github_review_id",
            name="uq_pr_reviews_pr_review",
        ),
    )
    op.create_index(
        "ix_pull_request_reviews_pull_request_id",
        "pull_request_reviews",
        ["pull_request_id"],
    )


def _drop_all() -> None:
    op.drop_index(
        "ix_pull_request_reviews_pull_request_id", table_name="pull_request_reviews"
    )
    op.drop_table("pull_request_reviews")
    op.drop_index("ix_pull_requests_user_id", table_name="pull_requests")
    op.drop_table("pull_requests")
    op.drop_index("ix_sync_runs_user_id", table_name="sync_runs")
    op.drop_table("sync_runs")


def upgrade() -> None:
    _drop_all()

    op.create_table(
        "pull_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("github_pr_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("author_login", sa.String(255), nullable=False),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("created_at_github", sa.DateTime(timezone=True), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("html_url", sa.String(1024), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "github_pr_id", name="uq_pull_requests_repo_pr"
        ),
    )
    op.create_index(
        "ix_pull_requests_repository_id", "pull_requests", ["repository_id"]
    )

    _create_reviews_table()

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_by", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("repos_synced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prs_synced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviews_synced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_organization_id", "sync_runs", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_runs_organization_id", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_index(
        "ix_pull_request_reviews_pull_request_id", table_name="pull_request_reviews"
    )
    op.drop_table("pull_request_reviews")
    op.drop_index("ix_pull_requests_repository_id", table_name="pull_requests")
    op.drop_table("pull_requests")

    # Restore the 0007 user-scoped shape (data is not restored).
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("github_pr_id", sa.Integer(), nullable=False),
        sa.Column("github_repo_full_name", sa.String(255), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("author_login", sa.String(255), nullable=False),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("created_at_github", sa.DateTime(timezone=True), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("html_url", sa.String(1024), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "github_pr_id", name="uq_pull_requests_user_pr"),
    )
    op.create_index("ix_pull_requests_user_id", "pull_requests", ["user_id"])

    _create_reviews_table()

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("prs_synced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviews_synced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_user_id", "sync_runs", ["user_id"])
