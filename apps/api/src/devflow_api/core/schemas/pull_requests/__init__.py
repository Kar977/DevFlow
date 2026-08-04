"""Pydantic schemas for the Pull Requests module."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from devflow_api.core.schemas.pagination import PageMeta


class ReviewResponse(BaseModel):
    id: uuid.UUID
    reviewer_login: str
    state: str
    submitted_at: datetime

    model_config = {"from_attributes": True}


class PullRequestResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    repository_full_name: str
    github_pr_id: int
    number: int
    title: str
    author_login: str
    state: str
    created_at_github: datetime
    merged_at: datetime | None
    closed_at: datetime | None
    first_review_at: datetime | None
    html_url: str
    last_synced_at: datetime

    model_config = {"from_attributes": True}


class PullRequestDetailResponse(PullRequestResponse):
    reviews: list[ReviewResponse]


class PullRequestListResponse(BaseModel):
    data: list[PullRequestResponse]
    meta: PageMeta
