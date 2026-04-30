"""Pydantic schemas for lightweight status endpoints."""

from pydantic import BaseModel


class ApiStatusResponse(BaseModel):
    """Status response for an API version."""

    version: str
    status: str


class FeatureStatusResponse(BaseModel):
    """Status response for a planned feature area."""

    feature: str
    status: str
