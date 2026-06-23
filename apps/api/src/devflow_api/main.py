"""FastAPI application factory and ASGI entrypoint."""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from devflow_api.api.v1.router import api_router
from devflow_api.core.config import Settings, get_settings
from devflow_api.core.errors import register_exception_handlers
from devflow_api.core.schemas.health import HealthResponse

# Security headers applied to every API response.
# CSP is intentionally strict for a JSON API (no scripts/styles/frames served).
# The frontend SPA should set its own broader CSP at the static-hosting / CDN layer.
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app_settings = settings or get_settings()

    # Disable interactive docs in production to avoid leaking API schema publicly.
    is_production = app_settings.environment == "production"
    app = FastAPI(
        title=app_settings.project_name,
        debug=app_settings.debug,
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    # TrustedHostMiddleware — register before CORS so host is validated first.
    if app_settings.allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=app_settings.allowed_hosts
        )

    if app_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in app_settings.cors_origins],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: object) -> Response:
        """Attach security headers to every response."""
        response: Response = await call_next(request)  # type: ignore[operator]
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> HealthResponse:
        """Return a lightweight health signal for probes and smoke tests."""
        return HealthResponse(status="ok", environment=app_settings.environment)

    return app


app = create_app()
