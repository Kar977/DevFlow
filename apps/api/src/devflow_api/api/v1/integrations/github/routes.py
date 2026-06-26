"""GitHub integration routes — OAuth flow, sync, and webhook handling."""

from fastapi import APIRouter, Depends, Header, Query, Request, status

from devflow_api.core.schemas.github import (
    AuthorizeUrlResponse,
    GitHubConnectionResponse,
    SyncResultResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.github_sync import (
    GitHubSyncService,
    get_github_sync_service,
)

router = APIRouter()


@router.post(
    "/authorize",
    response_model=AuthorizeUrlResponse,
    summary="Get GitHub OAuth authorization URL",
)
async def authorize(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubSyncService = Depends(get_github_sync_service),
) -> AuthorizeUrlResponse:
    url = service.authorize_url(user_id=subject.user_id)
    return AuthorizeUrlResponse(authorize_url=url)


@router.get(
    "/callback",
    response_model=GitHubConnectionResponse,
    summary="Handle GitHub OAuth callback",
)
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubSyncService = Depends(get_github_sync_service),
) -> GitHubConnectionResponse:
    conn = await service.handle_callback(
        user_id=subject.user_id, code=code, state=state
    )
    return GitHubConnectionResponse.model_validate(conn)


@router.get(
    "/status",
    response_model=GitHubConnectionResponse | None,
    summary="Get GitHub connection status",
)
async def connection_status(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubSyncService = Depends(get_github_sync_service),
) -> GitHubConnectionResponse | None:
    conn = await service.get_connection_status(user_id=subject.user_id)
    if conn is None:
        return None
    return GitHubConnectionResponse.model_validate(conn)


@router.delete(
    "/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect GitHub account",
)
async def disconnect(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubSyncService = Depends(get_github_sync_service),
) -> None:
    await service.disconnect(user_id=subject.user_id)


@router.post(
    "/sync",
    response_model=SyncResultResponse,
    summary="Sync assigned GitHub PRs and their reviews for the current user",
)
async def sync(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubSyncService = Depends(get_github_sync_service),
) -> SyncResultResponse:
    return await service.sync(user_id=subject.user_id)


_WEBHOOK_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MiB


@router.post(
    "/webhooks",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Receive GitHub webhook events",
)
async def webhooks(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    service: GitHubSyncService = Depends(get_github_sync_service),
) -> None:
    # Reject oversized payloads before reading body to limit resource consumption.
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _WEBHOOK_MAX_BODY_BYTES:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Webhook payload exceeds the maximum allowed size.",
        )

    raw_body = await request.body()

    # Secondary size guard for chunked transfers without Content-Length.
    if len(raw_body) > _WEBHOOK_MAX_BODY_BYTES:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Webhook payload exceeds the maximum allowed size.",
        )

    # HMAC signature is verified *inside* handle_webhook before JSON parsing.
    await service.handle_webhook(
        signature=x_hub_signature_256,
        raw_body=raw_body,
    )
