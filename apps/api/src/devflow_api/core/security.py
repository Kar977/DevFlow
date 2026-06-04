"""Security helpers, JWT utilities, and authentication dependency."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from devflow_api.core.config import get_settings
from devflow_api.core.errors import AppError

_bearer_scheme = HTTPBearer()


@dataclass(frozen=True, slots=True)
class AuthenticatedSubject:
    """Authenticated caller identity passed into protected use cases."""

    subject_id: str


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plain-text password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plain password matches the bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def generate_refresh_token() -> str:
    """Return a URL-safe random opaque token (not stored directly)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token for safe DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(subject_id: str) -> str:
    """Return a signed JWT access token for the given subject ID."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, object] = {"sub": subject_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str:
    """Decode and verify a JWT access token; return the subject ID."""
    settings = get_settings()
    try:
        payload: dict[str, object] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exc:
        raise AppError(
            code="invalid_token",
            message="Invalid or expired token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise AppError(
            code="invalid_token",
            message="Token is missing subject claim.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return sub


async def get_current_subject(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthenticatedSubject:
    """FastAPI dependency — extract and validate the Bearer JWT."""
    subject_id = decode_access_token(credentials.credentials)
    return AuthenticatedSubject(subject_id=subject_id)
