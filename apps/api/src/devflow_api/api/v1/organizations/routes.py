"""Organization API placeholders for tenant and account boundaries."""

from fastapi import APIRouter

from devflow_api.core.schemas.status import FeatureStatusResponse

router = APIRouter()


@router.get("", summary="Organizations API status")
async def organizations_status() -> FeatureStatusResponse:
    """Return the current implementation status for organization routes."""
    return FeatureStatusResponse(feature="organizations", status="planned")
