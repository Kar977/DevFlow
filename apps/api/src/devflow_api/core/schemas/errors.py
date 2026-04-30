"""Pydantic schemas for the standard API error envelope."""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Machine-readable error information."""

    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard API error response body."""

    error: ErrorDetail
