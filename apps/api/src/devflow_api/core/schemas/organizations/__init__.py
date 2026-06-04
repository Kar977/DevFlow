"""Pydantic schemas for the Organizations module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class UpdateOrganizationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationListResponse(BaseModel):
    items: list[OrganizationResponse]
    total: int


class InviteMemberRequest(BaseModel):
    email: str
    role: str = Field(default="member", pattern="^(owner|admin|member)$")


class MemberResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class MemberListResponse(BaseModel):
    items: list[MemberResponse]
    total: int
