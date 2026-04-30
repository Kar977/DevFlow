"""GitHub integration API placeholders for sync configuration."""

from fastapi import APIRouter

from devflow_api.core.schemas.status import FeatureStatusResponse

router = APIRouter()


@router.get("", summary="GitHub integration API status")
async def github_status() -> FeatureStatusResponse:
    """Return the current implementation status for GitHub integration routes."""
    return FeatureStatusResponse(feature="github_integration", status="planned")
