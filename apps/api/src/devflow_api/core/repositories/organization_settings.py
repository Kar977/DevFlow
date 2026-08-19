"""OrganizationSettings repository — database access for org metric cadence."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.organization_settings import (
    DEFAULT_SPRINT_LENGTH_DAYS,
    DEFAULT_STALE_PR_THRESHOLD_DAYS,
    OrganizationSettings,
)
from devflow_api.core.unset import UNSET, Unset


class OrganizationSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_org(
        self, organization_id: uuid.UUID
    ) -> OrganizationSettings | None:
        stmt = select(OrganizationSettings).where(
            OrganizationSettings.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        sprint_length_days: int | Unset = UNSET,
        sprint_anchor_date: date | None | Unset = UNSET,
        stale_pr_threshold_days: int | Unset = UNSET,
    ) -> OrganizationSettings:
        """Create-or-update, leaving any ``UNSET`` field at its current (or
        default, for a brand-new row) value — a partial update, not a
        replace, so one settings tab can PATCH its own fields without
        clobbering another tab's."""
        settings = await self.get_for_org(organization_id)
        if settings is None:
            settings = OrganizationSettings(
                organization_id=organization_id,
                sprint_length_days=DEFAULT_SPRINT_LENGTH_DAYS,
                stale_pr_threshold_days=DEFAULT_STALE_PR_THRESHOLD_DAYS,
            )
            self._session.add(settings)
        if not isinstance(sprint_length_days, Unset):
            settings.sprint_length_days = sprint_length_days
        if not isinstance(sprint_anchor_date, Unset):
            settings.sprint_anchor_date = sprint_anchor_date
        if not isinstance(stale_pr_threshold_days, Unset):
            settings.stale_pr_threshold_days = stale_pr_threshold_days
        await self._session.flush()
        return settings
