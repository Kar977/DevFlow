"""OrganizationSettings ORM model — per-organization metric cadence settings.

One row per organization (enforced by the ``unique=True`` FK), created lazily
on first write rather than alongside the organization itself — most orgs will
never touch this and should keep today's defaults (weekly ISO-bucketed
windows, a 5-day stale threshold) without an extra row. See
``OrganizationSettingsService.get_effective`` for the default-filling read
path used by ``PRMetricsService``.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.core.database import Base
from devflow_api.core.models.base import TimestampMixin, UUIDPrimaryKeyMixin

DEFAULT_SPRINT_LENGTH_DAYS = 14
DEFAULT_STALE_PR_THRESHOLD_DAYS = 5


class OrganizationSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cadence and threshold settings driving the org's PR-flow metrics."""

    __tablename__ = "organization_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    sprint_length_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_SPRINT_LENGTH_DAYS
    )
    # NULL means "no cadence configured" — callers fall back to the plain
    # Monday-anchored ISO week (see core.services.period.sprint_window).
    sprint_anchor_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stale_pr_threshold_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_STALE_PR_THRESHOLD_DAYS
    )
