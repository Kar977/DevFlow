"""PullRequest ORM model — GitHub PR synced per tracked repository."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class PullRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pull_requests"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # GitHub's numeric PR id (not the per-repo PR number).
    github_pr_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author_login: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at_github: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # GitHub's own "last updated" timestamp for the PR (commits, comments,
    # label changes, etc.) — distinct from TimestampMixin's `updated_at`,
    # which only reflects when *this row* was last written by a local sync
    # and is therefore useless as an activity signal. Nullable + no backfill:
    # existing rows before this column simply have no activity signal beyond
    # `created_at_github` until their next sync. See PRMetricsService's
    # `_stale_prs` for the read side.
    updated_at_github: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    html_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "repository_id", "github_pr_id", name="uq_pull_requests_repo_pr"
        ),
    )
