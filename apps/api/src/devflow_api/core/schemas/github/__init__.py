"""Pydantic schemas for the GitHub Integration module."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuthorizeUrlResponse(BaseModel):
    authorize_url: str


class GitHubConnectionResponse(BaseModel):
    """Public view of a GitHub connection — never exposes the access token."""

    id: uuid.UUID
    github_user_id: str
    github_login: str
    scopes: str
    connected_at: datetime

    model_config = {"from_attributes": True}


class SyncResultResponse(BaseModel):
    prs_synced: int
    reviews_synced: int


class InstallUrlRequest(BaseModel):
    organization_id: uuid.UUID


class InstallUrlResponse(BaseModel):
    install_url: str


class SetupRequest(BaseModel):
    installation_id: int
    setup_action: str
    state: str


class InstallationResponse(BaseModel):
    id: uuid.UUID
    installation_id: int
    account_login: str
    account_type: str
    account_avatar_url: str | None
    repository_selection: str
    suspended_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InstallationListResponse(BaseModel):
    """Not paginated — `meta` is omitted per the documented envelope contract."""

    data: list[InstallationResponse]


class RefreshReposResponse(BaseModel):
    repos: int


class RepositoryResponse(BaseModel):
    id: uuid.UUID
    github_installation_id: uuid.UUID
    full_name: str
    private: bool
    default_branch: str | None
    tracked: bool
    last_synced_at: datetime | None

    model_config = {"from_attributes": True}


class RepositoryListResponse(BaseModel):
    """Not paginated — `meta` is omitted per the documented envelope contract."""

    data: list[RepositoryResponse]


class RepositoryUpdateRequest(BaseModel):
    tracked: bool


class SyncRunResponse(BaseModel):
    id: uuid.UUID
    status: str
    repos_synced: int
    prs_synced: int
    reviews_synced: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class SyncRunListResponse(BaseModel):
    """Not paginated — `meta` is omitted per the documented envelope contract."""

    data: list[SyncRunResponse]
