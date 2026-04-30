"""Reports API placeholders for generated insight exports."""

from fastapi import APIRouter

from devflow_api.core.schemas.status import FeatureStatusResponse

router = APIRouter()


@router.get("", summary="Reports API status")
async def reports_status() -> FeatureStatusResponse:
    """Return the current implementation status for report routes."""
    return FeatureStatusResponse(feature="reports", status="planned")
