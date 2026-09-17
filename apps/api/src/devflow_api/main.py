"""FastAPI application factory and ASGI entrypoint."""

import asyncio
import logging
from collections.abc import AsyncIterator, MutableMapping
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from devflow_api.api.v1.router import api_router
from devflow_api.core.config import Settings, get_settings
from devflow_api.core.errors import error_payload, register_exception_handlers
from devflow_api.core.schemas.health import HealthResponse
from devflow_api.demo.scheduler import run_reset_loop

logger = logging.getLogger(__name__)

# Security headers applied to every API response.
# CSP is intentionally strict for a JSON API (no scripts/styles/frames served).
# The frontend SPA should set its own broader CSP at the static-hosting / CDN layer.
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware that injects security headers into every HTTP response.

    Using a pure ASGI middleware (instead of ``@app.middleware("http")`` /
    ``BaseHTTPMiddleware``) ensures that FastAPI ``BackgroundTasks`` are not
    dropped — ``BaseHTTPMiddleware`` creates a new ``Response`` wrapper in
    ``call_next()`` that does not carry the original response's ``background``
    attribute, silently discarding background tasks.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in _SECURITY_HEADERS.items():
                    headers[key] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


class DemoGuardMiddleware:
    """Pure-ASGI middleware that blocks specific requests in demo mode.

    Public showcase deployments (see ``Settings.demo_mode``) let a visitor
    edit data freely — that reseeds to a fresh baseline on a timer (see
    ``devflow_api.demo.scheduler``) — but must never let a visitor register
    their own account, since every visitor shares the one demo account.
    That guarantee must live in the API itself, not only in the frontend,
    which a visitor can bypass with a raw HTTP request. Matching is by exact
    (method, path), not by prefix.
    """

    def __init__(
        self, app: ASGIApp, *, blocked_paths: frozenset[tuple[str, str]]
    ) -> None:
        self.app = app
        self._blocked_paths = blocked_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or (scope["method"], scope["path"]) not in (
            self._blocked_paths
        ):
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=error_payload(
                code="demo_read_only",
                message=(
                    "W wersji demonstracyjnej rejestracja jest wyłączona — "
                    "wszyscy korzystają ze wspólnego konta demo."
                ),
            ),
        )
        await response(scope, receive, send)


class HealthCheckExemptTrustedHostMiddleware:
    """TrustedHostMiddleware that always lets ``/health`` through.

    Render's internal health-check prober hits the container over the
    private network with a Host header that never matches the public
    ``allowed_hosts`` list, which would otherwise make TrustedHostMiddleware
    reject the probe with 400 and leave the deploy stuck as unhealthy.
    ``/health`` returns no data, so exempting only it keeps host-header
    protection on every real route.
    """

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        self._guarded = TrustedHostMiddleware(app, allowed_hosts=allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == "/health":
            await self.app(scope, receive, send)
            return
        await self._guarded(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Run the demo data-reset loop for the lifetime of the app.

        A no-op outside demo mode (or with the reset interval set to 0) —
        the app has never had a lifespan before this, so every other
        deployment is unaffected.
        """
        reset_task: asyncio.Task[None] | None = None
        if app_settings.demo_mode and app_settings.demo_reset_interval_minutes > 0:
            reset_task = asyncio.create_task(
                run_reset_loop(app_settings.demo_reset_interval_minutes)
            )
            logger.info(
                "Demo reset loop started (every %s min)",
                app_settings.demo_reset_interval_minutes,
            )
        try:
            yield
        finally:
            if reset_task is not None:
                reset_task.cancel()
                with suppress(asyncio.CancelledError):
                    await reset_task

    # Disable interactive docs in production to avoid leaking API schema publicly
    # — except in demo mode, where the read-only guarantee below makes an
    # interactive schema a safe, useful part of the showcase.
    is_production = app_settings.environment == "production"
    hide_docs = is_production and not app_settings.demo_mode
    app = FastAPI(
        title=app_settings.project_name,
        debug=app_settings.debug,
        version="0.1.0",
        docs_url=None if hide_docs else "/docs",
        redoc_url=None if hide_docs else "/redoc",
        openapi_url=None if hide_docs else "/openapi.json",
        lifespan=lifespan,
    )

    # TrustedHostMiddleware — register before CORS so host is validated first.
    if app_settings.allowed_hosts:
        app.add_middleware(
            HealthCheckExemptTrustedHostMiddleware,
            allowed_hosts=app_settings.allowed_hosts,
        )

    if app_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in app_settings.cors_origins],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if app_settings.demo_mode:
        app.add_middleware(
            DemoGuardMiddleware,
            blocked_paths=frozenset(
                {("POST", f"{app_settings.api_v1_prefix}/auth/register")}
            ),
        )

    # Pure-ASGI security-headers middleware — must be added AFTER CORS/TrustedHost
    # (and the demo guard) so it sits outermost and sees all responses,
    # including error responses.
    app.add_middleware(SecurityHeadersMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> HealthResponse:
        """Return a lightweight health signal for probes and smoke tests."""
        return HealthResponse(status="ok", environment=app_settings.environment)

    return app


app = create_app()
