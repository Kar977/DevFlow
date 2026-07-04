"""GitHub integration routes — OAuth identity, App installations, webhooks."""

import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, status

from devflow_api.core.schemas.github import (
    AuthorizeUrlResponse,
    GitHubConnectionResponse,
    InstallationListResponse,
    InstallationResponse,
    InstallUrlRequest,
    InstallUrlResponse,
    RefreshReposResponse,
    SetupRequest,
    SyncResultResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.github_app import (
    GitHubAppService,
    get_github_app_service,
)
from devflow_api.core.services.github_sync import (
    GitHubSyncService,
    get_github_sync_service,
)

router = APIRouter()


@router.post(
    "/app/install-url",
    response_model=InstallUrlResponse,
    summary="Get the GitHub App installation URL for an organization",
)
async def app_install_url(
    payload: InstallUrlRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubAppService = Depends(get_github_app_service),
) -> InstallUrlResponse:
    url = await service.get_install_url(
        org_id=payload.organization_id, user_id=subject.user_id
    )
    return InstallUrlResponse(install_url=url)


@router.post(
    "/app/setup",
    response_model=InstallationResponse,
    summary="Complete the GitHub App installation redirect",
)
async def app_setup(
    payload: SetupRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubAppService = Depends(get_github_app_service),
) -> InstallationResponse:
    installation = await service.complete_setup(
        user_id=subject.user_id,
        installation_id=payload.installation_id,
        setup_action=payload.setup_action,
        state=payload.state,
    )
    return InstallationResponse.model_validate(installation)


@router.get(
    "/app/installations",
    response_model=InstallationListResponse,
    summary="List GitHub App installations of an organization",
)
async def app_installations(
    organization_id: uuid.UUID = Query(...),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubAppService = Depends(get_github_app_service),
) -> InstallationListResponse:
    rows = await service.list_installations(
        org_id=organization_id, user_id=subject.user_id
    )
    return InstallationListResponse(
        items=[InstallationResponse.model_validate(row) for row in rows]
    )


@router.delete(
    "/app/installations/{installation_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a GitHub App installation",
)
async def app_disconnect(
    installation_uuid: uuid.UUID,
    organization_id: uuid.UUID = Query(...),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubAppService = Depends(get_github_app_service),
) -> None:
    await service.disconnect(
        org_id=organization_id,
        user_id=subject.user_id,
        installation_uuid=installation_uuid,
    )


@router.post(
    "/app/installations/{installation_uuid}/refresh-repos",
    response_model=RefreshReposResponse,
    summary="Refresh the repository pool of an installation",
)
async def app_refresh_repos(
    installation_uuid: uuid.UUID,
    organization_id: uuid.UUID = Query(...),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: GitHubAppService = Depends(get_github_app_service),
) -> RefreshReposResponse:
    count = await service.refresh_installation_repositories(
        org_id=organization_id,
        user_id=subject.user_id,
        installation_uuid=installation_uuid,
    )
    return RefreshReposResponse(repos=count)


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
    x_github_event: str = Header(default=""),
    service: GitHubAppService = Depends(get_github_app_service),
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
        event=x_github_event,
    )
