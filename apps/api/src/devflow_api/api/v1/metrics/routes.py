"""Metrics API placeholders for computed engineering signals."""

from fastapi import APIRouter

from devflow_api.core.schemas.status import FeatureStatusResponse

router = APIRouter()


@router.get("", summary="Metrics API status")
async def metrics_status() -> FeatureStatusResponse:
    """Return the current implementation status for metric routes."""
    return FeatureStatusResponse(feature="metrics", status="planned")
