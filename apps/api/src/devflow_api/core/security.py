"""Security helpers and authentication dependency placeholders."""

from dataclasses import dataclass

from fastapi import status

from devflow_api.core.errors import AppError


@dataclass(frozen=True, slots=True)
class AuthenticatedSubject:
    """Authenticated caller identity passed into protected use cases."""

    subject_id: str


async def get_current_subject() -> AuthenticatedSubject:
    """Reject protected access until authentication is implemented."""
    raise AppError(
        code="authentication_not_configured",
        message="Authentication is not configured yet.",
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
    )
