"""Shared pagination metadata for list endpoints that accept limit/offset."""

from pydantic import BaseModel


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int
