"""Authentication routes — register, login, token refresh, profile."""

import uuid

from fastapi import APIRouter, Depends, Request, Response, status

from devflow_api.core.config import get_settings
from devflow_api.core.errors import AppError
from devflow_api.core.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UserResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.auth import AuthService, get_auth_service

router = APIRouter()

_REFRESH_COOKIE_NAME = "refresh_token"


def _refresh_cookie_path() -> str:
    """Scope the refresh cookie to auth endpoints only."""
    return f"{get_settings().api_v1_prefix}/auth"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=_refresh_cookie_path(),
        httponly=True,
        samesite="lax",
        secure=settings.environment in ("staging", "production"),
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE_NAME, path=_refresh_cookie_path())


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    body: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    user = await service.register(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    summary="Authenticate and receive an access token",
)
async def login(
    body: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> AccessTokenResponse:
    access_token, refresh_token = await service.login(
        email=body.email,
        password=body.password,
    )
    _set_refresh_cookie(response, refresh_token)
    return AccessTokenResponse(
        access_token=access_token,
        expires_in=AuthService.access_token_expires_in(),
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Rotate the refresh token and receive a new access token",
)
async def refresh_token(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> AccessTokenResponse:
    presented_token = request.cookies.get(_REFRESH_COOKIE_NAME)
    if not presented_token:
        raise AppError(
            code="invalid_refresh_token",
            message="Refresh token is invalid or has expired.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    access_token, new_refresh_token = await service.refresh(
        refresh_token=presented_token
    )
    _set_refresh_cookie(response, new_refresh_token)
    return AccessTokenResponse(
        access_token=access_token,
        expires_in=AuthService.access_token_expires_in(),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token",
)
async def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    _subject: AuthenticatedSubject = Depends(get_current_subject),
) -> None:
    presented_token = request.cookies.get(_REFRESH_COOKIE_NAME)
    if presented_token:
        await service.logout(refresh_token=presented_token)
    _clear_refresh_cookie(response)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the current user's profile",
)
async def get_me(
    service: AuthService = Depends(get_auth_service),
    subject: AuthenticatedSubject = Depends(get_current_subject),
) -> UserResponse:
    user = await service.get_user(uuid.UUID(subject.subject_id))
    return UserResponse.model_validate(user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update the current user's profile",
)
async def update_me(
    body: UpdateProfileRequest,
    service: AuthService = Depends(get_auth_service),
    subject: AuthenticatedSubject = Depends(get_current_subject),
) -> UserResponse:
    user = await service.update_profile(
        user_id=uuid.UUID(subject.subject_id),
        full_name=body.full_name,
        avatar_url=body.avatar_url,
    )
    return UserResponse.model_validate(user)
