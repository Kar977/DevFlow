"""Authentication API placeholders for future identity workflows."""

from fastapi import APIRouter

from devflow_api.core.schemas.status import FeatureStatusResponse

router = APIRouter()


@router.get("", summary="Authentication API status")
async def auth_status() -> FeatureStatusResponse:
    """Return the current implementation status for authentication routes."""
    return FeatureStatusResponse(feature="auth", status="planned")
