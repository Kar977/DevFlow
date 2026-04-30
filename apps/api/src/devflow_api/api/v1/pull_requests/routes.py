"""Pull request API placeholders for review-flow data."""

from fastapi import APIRouter

from devflow_api.core.schemas.status import FeatureStatusResponse

router = APIRouter()


@router.get("", summary="Pull requests API status")
async def pull_requests_status() -> FeatureStatusResponse:
    """Return the current implementation status for pull request routes."""
    return FeatureStatusResponse(feature="pull_requests", status="planned")
