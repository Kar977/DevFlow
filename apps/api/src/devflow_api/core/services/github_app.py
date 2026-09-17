"""GitHubAppService — App installations, repository tracking, webhooks."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.config import Settings, get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.integrations.github.app_auth import InstallationTokenProvider
from devflow_api.core.integrations.github.client import GitHubApiClient
from devflow_api.core.integrations.github.oauth import (
    create_install_state,
    verify_install_state,
)
from devflow_api.core.integrations.github.webhooks import verify_signature
from devflow_api.core.models.github_installation import GitHubInstallation
from devflow_api.core.models.repository import Repository
from devflow_api.core.repositories.github_installation import (
    GitHubInstallationRepository,
)
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.repository import RepositoryRepository
from devflow_api.core.services.org_access import require_admin, require_member

_INSTALL_URL_TEMPLATE = "https://github.com/apps/{slug}/installations/new?state={state}"


class GitHubAppService:
    def __init__(
        self,
        installation_repo: GitHubInstallationRepository,
        repository_repo: RepositoryRepository,
        org_repo: OrganizationRepository,
        api_client: GitHubApiClient,
        token_provider: InstallationTokenProvider,
    ) -> None:
        self._installation_repo = installation_repo
        self._repository_repo = repository_repo
        self._org_repo = org_repo
        self._api_client = api_client
        self._token_provider = token_provider

    @staticmethod
    def _require_app_configured(settings: Settings) -> None:
        if not (
            settings.github_app_id
            and settings.github_app_slug
            and settings.github_app_private_key
        ):
            raise AppError(
                code="github_app_not_configured",
                message="GitHub App integration is not configured on this server.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    def _mint_app_jwt(self) -> str:
        try:
            return self._token_provider.mint_app_jwt()
        except ValueError as exc:
            raise AppError(
                code="github_app_not_configured",
                message="GitHub App integration is not configured on this server.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

    async def get_install_url(self, *, org_id: uuid.UUID, user_id: uuid.UUID) -> str:
        await require_admin(self._org_repo, org_id, user_id)
        settings = get_settings()
        self._require_app_configured(settings)
        state = create_install_state(org_id, user_id, secret_key=settings.secret_key)
        return _INSTALL_URL_TEMPLATE.format(slug=settings.github_app_slug, state=state)

    async def complete_setup(
        self,
        *,
        user_id: uuid.UUID,
        installation_id: int,
        setup_action: str,
        state: str,
    ) -> GitHubInstallation:
        """Link a finished GitHub install/update redirect to its organization.

        Idempotent: re-entry (``setup_action=update`` or a repeated redirect)
        refreshes account metadata and the repository pool.
        """
        settings = get_settings()
        try:
            org_id = verify_install_state(
                state, user_id, secret_key=settings.secret_key
            )
        except ValueError as exc:
            raise AppError(
                code="invalid_install_state",
                message=(
                    "Install state is invalid or expired. "
                    "Please restart the GitHub App installation flow."
                ),
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc
        await require_admin(self._org_repo, org_id, user_id)

        existing = await self._installation_repo.get_by_installation_id(installation_id)
        if existing and existing.organization_id != org_id:
            raise AppError(
                code="installation_already_linked",
                message=(
                    "This GitHub App installation is already linked "
                    "to another organization."
                ),
                status_code=status.HTTP_409_CONFLICT,
            )

        app_jwt = self._mint_app_jwt()
        data = await self._api_client.get_installation(app_jwt, installation_id)
        account: dict[str, Any] = data.get("account") or {}
        installation = await self._installation_repo.upsert(
            organization_id=org_id,
            installation_id=installation_id,
            account_login=str(account.get("login", "")),
            account_type=str(account.get("type", "")),
            account_avatar_url=account.get("avatar_url"),
            repository_selection=str(data.get("repository_selection", "all")),
            created_by=user_id,
        )
        await self.refresh_repositories(installation=installation)
        return installation

    async def refresh_repositories(self, *, installation: GitHubInstallation) -> int:
        """Mirror the installation's accessible repositories locally.

        Upserts every repo (never touching ``tracked``) and prunes rows for
        repos the installation can no longer access.
        """
        token = await self._token_provider.get_token(installation.installation_id)
        repos = await self._api_client.list_installation_repositories(token)
        seen_ids: set[int] = set()
        for repo_data in repos:
            github_repo_id = int(repo_data["id"])
            seen_ids.add(github_repo_id)
            await self._repository_repo.upsert(
                organization_id=installation.organization_id,
                github_installation_id=installation.id,
                github_repo_id=github_repo_id,
                full_name=str(repo_data["full_name"]),
                private=bool(repo_data.get("private", False)),
                default_branch=repo_data.get("default_branch"),
            )
        await self._repository_repo.delete_missing(installation.id, seen_ids)
        return len(seen_ids)

    async def list_installations(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[GitHubInstallation]:
        await require_member(self._org_repo, org_id, user_id)
        return await self._installation_repo.list_for_org(org_id)

    async def refresh_installation_repositories(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID, installation_uuid: uuid.UUID
    ) -> int:
        await require_admin(self._org_repo, org_id, user_id)
        installation = await self._get_org_installation(org_id, installation_uuid)
        return await self.refresh_repositories(installation=installation)

    async def disconnect(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID, installation_uuid: uuid.UUID
    ) -> None:
        await require_admin(self._org_repo, org_id, user_id)
        installation = await self._get_org_installation(org_id, installation_uuid)
        try:
            app_jwt = self._mint_app_jwt()
            await self._api_client.delete_installation(
                app_jwt, installation.installation_id
            )
        except Exception:  # noqa: BLE001 — best-effort uninstall on GitHub
            pass
        await self._installation_repo.delete(installation)

    async def list_repositories(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        tracked: bool | None = None,
    ) -> list[Repository]:
        await require_member(self._org_repo, org_id, user_id)
        return await self._repository_repo.list_for_org(org_id, tracked=tracked)

    async def set_repository_tracked(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        repo_id: uuid.UUID,
        tracked: bool,
    ) -> Repository:
        await require_admin(self._org_repo, org_id, user_id)
        repo = await self._repository_repo.get_by_id_for_org(repo_id, org_id)
        if not repo:
            raise AppError(
                code="not_found",
                message="Repository not found in this organization.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return await self._repository_repo.set_tracked(repo, tracked)

    async def handle_webhook(
        self, *, signature: str, raw_body: bytes, event: str
    ) -> None:
        settings = get_settings()
        if not settings.github_webhook_secret:
            raise AppError(
                code="webhook_not_configured",
                message="Webhook secret is not configured.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            verify_signature(
                payload_bytes=raw_body,
                secret=settings.github_webhook_secret,
                signature_header=signature,
            )
        except ValueError as exc:
            raise AppError(
                code="invalid_signature",
                message=str(exc),
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc

        payload: dict[str, Any] = json.loads(raw_body)
        if event == "installation":
            await self._on_installation_event(payload)
        elif event == "installation_repositories":
            await self._on_installation_repositories_event(payload)

    async def _on_installation_event(self, payload: dict[str, Any]) -> None:
        installation = await self._installation_from_payload(payload)
        if installation is None:
            return
        action = str(payload.get("action", ""))
        if action == "deleted":
            await self._installation_repo.delete(installation)
        elif action == "suspend":
            await self._installation_repo.set_suspended_at(
                installation, datetime.now(UTC)
            )
        elif action == "unsuspend":
            await self._installation_repo.set_suspended_at(installation, None)

    async def _on_installation_repositories_event(
        self, payload: dict[str, Any]
    ) -> None:
        installation = await self._installation_from_payload(payload)
        if installation is None:
            return
        for repo_data in payload.get("repositories_added", []):
            await self._repository_repo.upsert(
                organization_id=installation.organization_id,
                github_installation_id=installation.id,
                github_repo_id=int(repo_data["id"]),
                full_name=str(repo_data["full_name"]),
                private=bool(repo_data.get("private", False)),
                default_branch=repo_data.get("default_branch"),
            )
        removed_ids = {
            int(repo_data["id"])
            for repo_data in payload.get("repositories_removed", [])
        }
        if removed_ids:
            await self._repository_repo.delete_by_github_repo_ids(
                installation.id, removed_ids
            )

    async def _installation_from_payload(
        self, payload: dict[str, Any]
    ) -> GitHubInstallation | None:
        raw_id = (payload.get("installation") or {}).get("id")
        if raw_id is None:
            return None
        return await self._installation_repo.get_by_installation_id(int(raw_id))

    async def _get_org_installation(
        self, org_id: uuid.UUID, installation_uuid: uuid.UUID
    ) -> GitHubInstallation:
        installation = await self._installation_repo.get_by_id(installation_uuid)
        if not installation or installation.organization_id != org_id:
            raise AppError(
                code="not_found",
                message="GitHub App installation not found in this organization.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return installation


def get_github_app_service(
    session: AsyncSession = Depends(get_session),
) -> GitHubAppService:
    settings = get_settings()
    installation_repo = GitHubInstallationRepository(session)
    repository_repo = RepositoryRepository(session)
    org_repo = OrganizationRepository(session)

    if settings.demo_mode:
        # Local import: devflow_api.demo is a maintenance package, not part
        # of the normal request-path dependency graph — see its __init__.
        from devflow_api.demo.github import (
            DemoGitHubApiClient,
            DemoGitHubAppService,
            DemoInstallationTokenProvider,
        )

        demo_client = DemoGitHubApiClient()
        return DemoGitHubAppService(
            installation_repo=installation_repo,
            repository_repo=repository_repo,
            org_repo=org_repo,
            api_client=demo_client,
            token_provider=DemoInstallationTokenProvider(api_client=demo_client),
        )

    api_client = GitHubApiClient()
    return GitHubAppService(
        installation_repo=installation_repo,
        repository_repo=repository_repo,
        org_repo=org_repo,
        api_client=api_client,
        token_provider=InstallationTokenProvider(
            api_client=api_client,
            app_id=settings.github_app_id,
            private_key_pem=settings.github_app_private_key_pem,
        ),
    )
