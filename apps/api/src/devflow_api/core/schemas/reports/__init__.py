"""Pydantic schemas for the Reports module."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from devflow_api.core.schemas.pagination import PageMeta

_TYPE_PATTERN = "^(weekly_summary|project_status|productivity_overview|pr_flow_weekly)$"
_FORMAT_PATTERN = "^(json)$"


class CreateReportRequest(BaseModel):
    type: str = Field(pattern=_TYPE_PATTERN)
    format: str = Field(default="json", pattern=_FORMAT_PATTERN)
    date_from: datetime | None = None
    date_to: datetime | None = None
    project_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None


class ReportResponse(BaseModel):
    id: uuid.UUID
    type: str
    format: str
    status: str
    organization_id: uuid.UUID | None = None
    payload: dict[str, Any] | None = None
    error_message: str | None = None
    generated_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    data: list[ReportResponse]
    meta: PageMeta
