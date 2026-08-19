"""OrganizationSettingsService — per-organization metric cadence settings."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.database import get_session
from devflow_api.core.models.organization_settings import (
    DEFAULT_SPRINT_LENGTH_DAYS,
    DEFAULT_STALE_PR_THRESHOLD_DAYS,
    OrganizationSettings,
)
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.organization_settings import (
    OrganizationSettingsRepository,
)
from devflow_api.core.schemas.organization_settings import SprintResponse
from devflow_api.core.services.org_access import require_admin, require_member
from devflow_api.core.services.period import sprint_series
from devflow_api.core.unset import UNSET, Unset


@dataclass(frozen=True)
class OrgMetricSettings:
    """Effective cadence settings for a metrics computation — always
    populated, even when the org has never configured anything."""

    sprint_length_days: int
    sprint_anchor_date: date | None
    stale_pr_threshold_days: int


class OrganizationSettingsService:
    def __init__(
        self,
        settings_repo: OrganizationSettingsRepository,
        org_repo: OrganizationRepository,
    ) -> None:
        self._settings_repo = settings_repo
        self._org_repo = org_repo

    async def get(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationSettings | None:
        """Return the raw settings row (or ``None``) for the settings tab.

        Any member may read — unlike ``update``, this has no side effects
        worth gating behind an admin role.
        """
        await require_member(self._org_repo, org_id, user_id)
        return await self._settings_repo.get_for_org(org_id)

    async def update(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        sprint_length_days: int | Unset = UNSET,
        sprint_anchor_date: date | None | Unset = UNSET,
        stale_pr_threshold_days: int | Unset = UNSET,
    ) -> OrganizationSettings:
        """Partial update — any field left ``UNSET`` keeps its current (or
        default) value, so a settings tab that only owns a subset of fields
        can PATCH without clobbering the rest."""
        await require_admin(self._org_repo, org_id, user_id)
        return await self._settings_repo.upsert_for_org(
            org_id,
            sprint_length_days=sprint_length_days,
            sprint_anchor_date=sprint_anchor_date,
            stale_pr_threshold_days=stale_pr_threshold_days,
        )

    async def list_sprints(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        back: int = 6,
        forward: int = 2,
        at: datetime | None = None,
    ) -> list[SprintResponse]:
        """The sprint series around *at* (default: now) under the org's
        cadence — the single source of truth callers use instead of
        re-deriving sprint boundaries themselves."""
        await require_member(self._org_repo, org_id, user_id)
        effective = await self.get_effective(org_id)
        spans = sprint_series(
            effective.sprint_anchor_date,
            effective.sprint_length_days,
            at or datetime.now(UTC),
            back=back,
            forward=forward,
        )
        return [
            SprintResponse(
                number=span.number,
                start_date=span.start,
                end_date=span.end,
                is_current=span.is_current,
            )
            for span in spans
        ]

    async def get_effective(self, org_id: uuid.UUID) -> OrgMetricSettings:
        """Settings for internal metric computation — never ``None``.

        No authorization check: called from ``PRMetricsService`` after the
        caller has already been verified as a member for the surrounding
        request, so this is a plain data read, not a new access boundary.
        """
        settings = await self._settings_repo.get_for_org(org_id)
        if settings is None:
            return OrgMetricSettings(
                sprint_length_days=DEFAULT_SPRINT_LENGTH_DAYS,
                sprint_anchor_date=None,
                stale_pr_threshold_days=DEFAULT_STALE_PR_THRESHOLD_DAYS,
            )
        return OrgMetricSettings(
            sprint_length_days=settings.sprint_length_days,
            sprint_anchor_date=settings.sprint_anchor_date,
            stale_pr_threshold_days=settings.stale_pr_threshold_days,
        )


def get_organization_settings_service(
    session: AsyncSession = Depends(get_session),
) -> OrganizationSettingsService:
    return OrganizationSettingsService(
        settings_repo=OrganizationSettingsRepository(session),
        org_repo=OrganizationRepository(session),
    )
