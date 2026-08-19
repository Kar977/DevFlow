"""Pydantic schemas for the OrganizationSettings module."""

import uuid
from datetime import date

from pydantic import BaseModel, Field


class UpdateOrganizationSettingsRequest(BaseModel):
    """All fields are optional so each settings tab can PATCH just the
    fields it owns (e.g. "Sprinty" sends cadence, "Metryki" sends only the
    stale-PR threshold) without clobbering the other tab's values.

    ``model_fields_set`` at the route layer distinguishes "omitted" (leave
    unchanged) from "explicitly sent" — the same pattern ``UpdateTaskRequest``
    already uses with the ``UNSET`` sentinel.
    """

    sprint_length_days: int | None = Field(default=None, ge=1, le=60)
    sprint_anchor_date: date | None = None
    stale_pr_threshold_days: int | None = Field(default=None, ge=1, le=90)


class OrganizationSettingsResponse(BaseModel):
    organization_id: uuid.UUID
    sprint_length_days: int
    sprint_anchor_date: date | None
    stale_pr_threshold_days: int

    model_config = {"from_attributes": True}


class SprintResponse(BaseModel):
    """One sprint window, as inclusive calendar dates.

    ``number`` is ``None`` when the org has no cadence configured (the
    fallback ISO-week windows aren't numbered — see
    ``core.services.period.sprint_series``).
    """

    number: int | None
    start_date: date
    end_date: date
    is_current: bool


class SprintListResponse(BaseModel):
    """Not paginated — `meta` is omitted per the documented envelope contract."""

    data: list[SprintResponse]
