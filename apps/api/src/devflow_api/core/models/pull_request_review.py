"""PullRequestReview ORM model — a single review on a PR."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class PullRequestReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pull_request_reviews"

    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    github_review_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reviewer_login: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "pull_request_id",
            "github_review_id",
            name="uq_pr_reviews_pr_review",
        ),
    )
