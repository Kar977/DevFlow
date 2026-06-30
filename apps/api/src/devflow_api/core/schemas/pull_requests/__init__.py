"""Pydantic schemas for the Pull Requests module."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReviewResponse(BaseModel):
    id: uuid.UUID
    reviewer_login: str
    state: str
    submitted_at: datetime

    model_config = {"from_attributes": True}


class PullRequestResponse(BaseModel):
    id: uuid.UUID
    github_pr_id: int
    github_repo_full_name: str
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
    items: list[PullRequestResponse]
    total: int


class RepositoryResponse(BaseModel):
    full_name: str
    pr_count: int


class RepositoryListResponse(BaseModel):
    items: list[RepositoryResponse]
