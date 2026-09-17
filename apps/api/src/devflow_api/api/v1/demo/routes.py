"""Demo-mode status — whether it's on, and when data next resets."""

from fastapi import APIRouter

from devflow_api.core.config import get_settings
from devflow_api.core.schemas.demo import DemoStatusResponse
from devflow_api.demo.scheduler import get_next_reset_at

router = APIRouter()


@router.get(
    "/status",
    response_model=DemoStatusResponse,
    summary="Demo mode status and next scheduled data reset",
)
async def get_demo_status() -> DemoStatusResponse:
    """Unauthenticated and always mounted; reports disabled outside demo mode.

    Lets the frontend banner show an honest "next reset in ~N min" instead
    of a static interval that drifts from what the server is actually doing.
    """
    settings = get_settings()
    return DemoStatusResponse(
        enabled=settings.demo_mode,
        reset_interval_minutes=settings.demo_reset_interval_minutes,
        next_reset_at=get_next_reset_at() if settings.demo_mode else None,
    )
