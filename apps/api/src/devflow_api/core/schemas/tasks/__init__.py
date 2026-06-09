"""Pydantic schemas for the Tasks + Time Tracking module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

_STATUS_PATTERN = "^(backlog|todo|in_progress|review|done|cancelled)$"
_PRIORITY_PATTERN = "^(low|medium|high|critical)$"


class CreateTaskRequest(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    priority: str = Field(default="medium", pattern=_PRIORITY_PATTERN)
    estimate_minutes: int | None = Field(default=None, ge=0)
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    github_pr_url: str | None = Field(default=None, max_length=1024)


class UpdateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, pattern=_STATUS_PATTERN)
    priority: str | None = Field(default=None, pattern=_PRIORITY_PATTERN)
    estimate_minutes: int | None = Field(default=None, ge=0)
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    github_pr_url: str | None = Field(default=None, max_length=1024)


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: str
    priority: str
    estimate_minutes: int | None
    assignee_id: uuid.UUID | None
    due_date: datetime | None
    github_pr_url: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


class WorkSessionResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkSessionListResponse(BaseModel):
    items: list[WorkSessionResponse]
    total: int
