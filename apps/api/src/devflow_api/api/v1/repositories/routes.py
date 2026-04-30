"""Repository API placeholders for source-control repository views."""

from fastapi import APIRouter

from devflow_api.core.schemas.status import FeatureStatusResponse

router = APIRouter()


@router.get("", summary="Repositories API status")
async def repositories_status() -> FeatureStatusResponse:
    """Return the current implementation status for repository routes."""
    return FeatureStatusResponse(feature="repositories", status="planned")
