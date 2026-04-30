"""Pydantic schemas for service health responses."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health probe response."""

    status: str
    environment: str
