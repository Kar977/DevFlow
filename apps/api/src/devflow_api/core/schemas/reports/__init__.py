"""Pydantic schemas for the Reports module."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

_TYPE_PATTERN = "^(weekly_summary|project_status|productivity_overview)$"
_FORMAT_PATTERN = "^(json)$"


class CreateReportRequest(BaseModel):
    type: str = Field(pattern=_TYPE_PATTERN)
    format: str = Field(default="json", pattern=_FORMAT_PATTERN)
    date_from: datetime | None = None
    date_to: datetime | None = None
    project_id: uuid.UUID | None = None


class ReportResponse(BaseModel):
    id: uuid.UUID
    type: str
    format: str
    status: str
    payload: dict[str, Any] | None = None
    error_message: str | None = None
    generated_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int
