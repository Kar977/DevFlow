"""Authentication service — registration, login, token management."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.user import User
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.refresh_token import RefreshTokenRepository
from devflow_api.core.repositories.user import UserRepository
from devflow_api.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from devflow_api.core.services.organization import OrganizationService


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        org_service: OrganizationService,
    ) -> None:
        self._user_repo = user_repo
        self._token_repo = token_repo
        self._org_service = org_service

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        if await self._user_repo.exists_by_email(email):
            raise AppError(
                code="email_already_registered",
                message="An account with this email already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return await self._user_repo.create(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )

    async def login(self, *, email: str, password: str) -> tuple[str, str]:
        """Return (access_token, refresh_token) on successful authentication."""
        user = await self._user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise AppError(
                code="invalid_credentials",
                message="Invalid email or password.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        # Idempotently ensure the user has at least a personal workspace.
        # Covers both new registrations and existing accounts that pre-date
        # automatic org creation.
        display_name = user.full_name or user.email.split("@")[0]
        await self._org_service.ensure_personal_organization(
            user_id=user.id, display_name=display_name
        )
        return await self._issue_tokens(user.id)

    async def refresh(self, *, refresh_token: str) -> tuple[str, str]:
        """Validate a refresh token, rotate it, and return (access, new refresh).

        Rotation: the presented refresh token is revoked and a new one is
        issued alongside the new access token, so each refresh token is
        usable exactly once.

        Reuse detection: if the presented token was already revoked (i.e. it
        was already rotated away, or explicitly logged out), that is treated
        as a signal the token may have been stolen — every active refresh
        token for the user is revoked, forcing a fresh login everywhere.
        """
        token_hash = hash_token(refresh_token)
        stored = await self._token_repo.get_by_hash(token_hash)

        invalid_token_error = AppError(
            code="invalid_refresh_token",
            message="Refresh token is invalid or has expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        if stored is None:
            raise invalid_token_error

        now = datetime.now(UTC)
        if stored.revoked_at is not None:
            await self._token_repo.revoke_all_for_user(stored.user_id, revoked_at=now)
            raise invalid_token_error
        if stored.expires_at.replace(tzinfo=UTC) < now:
            raise invalid_token_error

        await self._token_repo.revoke(stored, revoked_at=now)
        return await self._issue_tokens(stored.user_id)

    async def logout(self, *, refresh_token: str) -> None:
        """Revoke the given refresh token."""
        token_hash = hash_token(refresh_token)
        stored = await self._token_repo.get_by_hash(token_hash)
        if stored is not None and stored.revoked_at is None:
            await self._token_repo.revoke(stored, revoked_at=datetime.now(UTC))

    async def get_user(self, user_id: uuid.UUID) -> User:
        """Return the user by ID or raise 401 if not found."""
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise AppError(
                code="user_not_found",
                message="Authenticated user no longer exists.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return user

    async def update_profile(
        self,
        *,
        user_id: uuid.UUID,
        full_name: str | None,
        avatar_url: str | None,
    ) -> User:
        user = await self.get_user(user_id)
        return await self._user_repo.update(
            user,
            full_name=full_name,
            avatar_url=avatar_url,
        )

    async def _issue_tokens(self, user_id: uuid.UUID) -> tuple[str, str]:
        """Create and persist a new refresh token; return both tokens."""
        settings = get_settings()
        raw_token = generate_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.refresh_token_expire_days
        )
        await self._token_repo.create(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
        access_token = create_access_token(str(user_id))
        return access_token, raw_token

    @staticmethod
    def access_token_expires_in() -> int:
        """Return access token TTL in seconds."""
        return get_settings().access_token_expire_minutes * 60


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    """FastAPI dependency — construct AuthService with its repositories."""
    return AuthService(
        user_repo=UserRepository(session),
        token_repo=RefreshTokenRepository(session),
        org_service=OrganizationService(
            org_repo=OrganizationRepository(session),
            user_repo=UserRepository(session),
        ),
    )
