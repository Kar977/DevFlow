"""Pydantic schemas for the Projects module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from devflow_api.core.schemas.pagination import PageMeta


class CreateProjectRequest(BaseModel):
    org_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    github_repo_url: str | None = Field(default=None, max_length=1024)


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")
    github_repo_url: str | None = Field(default=None, max_length=1024)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: str | None
    status: str
    github_repo_url: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    data: list[ProjectResponse]
    meta: PageMeta
