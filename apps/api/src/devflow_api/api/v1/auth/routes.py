"""Authentication routes — register, login, token refresh, profile."""

import uuid

from fastapi import APIRouter, Depends, status

from devflow_api.core.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.auth import AuthService, get_auth_service

router = APIRouter()


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
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
)
async def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    access_token, refresh_token = await service.login(
        email=body.email,
        password=body.password,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=AuthService.access_token_expires_in(),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate a refresh token and receive a new token pair",
)
async def refresh_token(
    body: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    access_token, new_refresh_token = await service.refresh(
        refresh_token=body.refresh_token
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=AuthService.access_token_expires_in(),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token",
)
async def logout(
    body: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
    _subject: AuthenticatedSubject = Depends(get_current_subject),
) -> None:
    await service.logout(refresh_token=body.refresh_token)


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
