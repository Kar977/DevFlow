"""FastAPI application factory and ASGI entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devflow_api.api.v1.router import api_router
from devflow_api.core.config import Settings, get_settings
from devflow_api.core.errors import register_exception_handlers
from devflow_api.core.schemas.health import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app_settings = settings or get_settings()
    app = FastAPI(
        title=app_settings.project_name,
        debug=app_settings.debug,
        version="0.1.0",
    )

    if app_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in app_settings.cors_origins],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> HealthResponse:
        """Return a lightweight health signal for probes and smoke tests."""
        return HealthResponse(status="ok", environment=app_settings.environment)

    return app


app = create_app()
