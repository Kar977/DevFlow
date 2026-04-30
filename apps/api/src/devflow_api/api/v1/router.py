"""Top-level router for the version 1 API contract."""

from fastapi import APIRouter

from devflow_api.api.v1.auth.routes import router as auth_router
from devflow_api.api.v1.integrations.github.routes import router as github_router
from devflow_api.api.v1.metrics.routes import router as metrics_router
from devflow_api.api.v1.organizations.routes import router as organizations_router
from devflow_api.api.v1.pull_requests.routes import router as pull_requests_router
from devflow_api.api.v1.reports.routes import router as reports_router
from devflow_api.api.v1.repositories.routes import router as repositories_router
from devflow_api.core.schemas.status import ApiStatusResponse

api_router = APIRouter()


@api_router.get("", tags=["system"])
async def api_status() -> ApiStatusResponse:
    """Return basic metadata for the mounted API version."""
    return ApiStatusResponse(version="v1", status="ready")


api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(
    organizations_router, prefix="/organizations", tags=["organizations"]
)
api_router.include_router(
    repositories_router, prefix="/repositories", tags=["repositories"]
)
api_router.include_router(
    pull_requests_router, prefix="/pull-requests", tags=["pull-requests"]
)
api_router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(github_router, prefix="/integrations/github", tags=["github"])
