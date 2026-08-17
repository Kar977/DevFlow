"""Application error types and FastAPI exception handlers."""

from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_MEDIA_TYPE: Final = "application/json"


class AppError(Exception):
    """Base exception for expected application failures."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build the standard error response envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register standard exception handlers on the FastAPI application."""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
            media_type=ERROR_MEDIA_TYPE,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code="http_error", message=detail),
            media_type=ERROR_MEDIA_TYPE,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_payload(
                code="validation_error",
                message="Request validation failed.",
                # pydantic error dicts can carry a `ctx.error` that is the
                # raw exception instance a field_validator raised (e.g. a
                # ValueError), which plain `json.dumps` can't serialize.
                # jsonable_encoder is what FastAPI's own default handler
                # uses to convert it to a JSON-safe string.
                details={"errors": jsonable_encoder(exc.errors())},
            ),
            media_type=ERROR_MEDIA_TYPE,
        )
