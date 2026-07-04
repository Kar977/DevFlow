"""GitHubInstallation ORM model — a GitHub App installation linked to an org."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class GitHubInstallation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "github_installations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # GitHub's numeric installation id — globally unique, so one installation
    # can only ever be linked to a single DevFlow organization.
    installation_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True
    )
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_avatar_url: Mapped[str | None] = mapped_column(String(1024))
    repository_selection: Mapped[str] = mapped_column(String(20), nullable=False)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
