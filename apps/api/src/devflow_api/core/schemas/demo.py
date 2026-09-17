"""Pydantic schemas for the demo-mode status endpoint."""

from datetime import datetime

from pydantic import BaseModel


class DemoStatusResponse(BaseModel):
    """Whether demo mode is on, and when data next resets to its baseline."""

    enabled: bool
    reset_interval_minutes: int
    next_reset_at: datetime | None
