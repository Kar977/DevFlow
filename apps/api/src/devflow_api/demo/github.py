"""No-network stand-ins for the GitHub integration, used only in demo mode.

Real GitHub App/OAuth credentials are deliberately left blank on the demo
deployment (see ``docs/demo.md``) — even without these classes, that alone
already stops most outbound calls with a 503. But two things still need an
active override to become fully clickable without ever reaching GitHub:

- ``GitHubAppService.get_install_url`` and ``GitHubSyncService.authorize_url``
  build a ``github.com`` URL the browser is sent to via
  ``window.location.href`` — that must become an internal path instead.
- ``GitHubSyncService.handle_callback`` calls
  ``core.integrations.github.oauth.exchange_code_for_token``, a free
  function that opens its own ``httpx.AsyncClient`` and bypasses
  ``GitHubApiClient`` entirely — swapping the client alone can't stop it.

Every other method of ``GitHubAppService`` and ``OrgSyncService`` already
works unmodified once constructed with :class:`DemoGitHubApiClient` and
:class:`DemoInstallationTokenProvider` (see the ``get_*_service`` factories
in ``core.services``) — nothing else in this module subclasses them.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import status

from devflow_api.core.config import get_settings
from devflow_api.core.errors import AppError
from devflow_api.core.integrations.github.app_auth import InstallationTokenProvider
from devflow_api.core.integrations.github.client import GitHubApiClient
from devflow_api.core.integrations.github.oauth import (
    create_install_state,
    create_oauth_state,
    verify_oauth_state,
)
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.services.github_app import GitHubAppService
from devflow_api.core.services.github_sync import GitHubSyncService
from devflow_api.core.services.org_access import require_admin
from devflow_api.demo.dataset import _REPO_SPECS  # noqa: PLC2701

# Must match the installation and account the seeder writes in
# demo/dataset.py::_build_github_scaffolding — reusing it keeps a demo
# "disconnect" + "reconnect" round-trip consistent with the seeded data.
_DEMO_INSTALLATION_ID = 90_000_001
_DEMO_ACCOUNT_LOGIN = "acme-inc"
_DEMO_ACCOUNT_TYPE = "Organization"
_DEMO_GITHUB_USER_ID = "1000001"
_DEMO_GITHUB_LOGIN = "demo-owner"
_DEMO_SCOPES = "read:user"


class DemoGitHubApiClient(GitHubApiClient):
    """Fixed, deterministic responses — never opens a socket.

    ``list_repo_pulls`` always reports nothing new, so ``list_pr_reviews``
    (which only ever runs per PR returned by it) is never actually reached.
    That is a deliberate simplification: the seeded historical PRs already
    come straight from ``demo/dataset.py``, not through this client, so a
    "sync" that finds nothing new is itself a realistic, safe result to show
    rather than an omission.
    """

    def __init__(self) -> None:
        super().__init__()

    async def create_installation_access_token(
        self, app_jwt: str, installation_id: int
    ) -> dict[str, Any]:
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        return {
            "token": "demo-installation-token",
            "expires_at": expires_at.isoformat(),
        }

    async def get_installation(
        self, app_jwt: str, installation_id: int
    ) -> dict[str, Any]:
        return {
            "id": installation_id,
            "account": {
                "login": _DEMO_ACCOUNT_LOGIN,
                "type": _DEMO_ACCOUNT_TYPE,
                "avatar_url": None,
            },
            "repository_selection": "selected",
        }

    async def delete_installation(self, app_jwt: str, installation_id: int) -> None:
        return None

    async def list_installation_repositories(
        self,
        token: str,
        *,
        per_page: int = 100,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": spec.github_repo_id,
                "full_name": spec.full_name,
                "private": spec.private,
                "default_branch": "main",
            }
            for spec in _REPO_SPECS
        ]

    async def list_repo_pulls(
        self,
        token: str,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 100,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        return []

    async def get_authenticated_user(self, token: str) -> dict[str, Any]:
        return {"id": _DEMO_GITHUB_USER_ID, "login": _DEMO_GITHUB_LOGIN}

    async def list_pr_reviews(
        self, token: str, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        return []


class DemoInstallationTokenProvider(InstallationTokenProvider):
    """Fixed fake tokens — no JWT minting, no GitHub App credentials needed."""

    def __init__(self, *, api_client: GitHubApiClient) -> None:
        super().__init__(api_client=api_client, app_id="demo-app", private_key_pem="")

    def mint_app_jwt(self) -> str:
        return "demo-app-jwt"

    async def get_token(self, installation_id: int) -> str:
        return "demo-installation-token"


class DemoGitHubAppService(GitHubAppService):
    """Sends the visitor to our own setup page instead of GitHub's.

    Only ``get_install_url`` needs overriding: it checks the real (and
    deliberately blank in demo, see ``docs/demo.md``)
    ``DEVFLOW_API_GITHUB_APP_*`` settings before building a ``github.com``
    URL. Everything downstream of that redirect — ``complete_setup``,
    ``refresh_repositories``, ``disconnect`` — already works unmodified once
    this service is constructed with :class:`DemoGitHubApiClient` and
    :class:`DemoInstallationTokenProvider`.
    """

    async def get_install_url(self, *, org_id: uuid.UUID, user_id: uuid.UUID) -> str:
        await require_admin(self._org_repo, org_id, user_id)
        settings = get_settings()
        state = create_install_state(org_id, user_id, secret_key=settings.secret_key)
        return (
            "/integrations/github/setup"
            f"?installation_id={_DEMO_INSTALLATION_ID}&setup_action=install&state={state}"
        )


class DemoGitHubSyncService(GitHubSyncService):
    """Sends the visitor to our own callback page and skips the real OAuth exchange.

    ``authorize_url`` no longer points at ``github.com`` at all, and
    ``handle_callback`` never calls ``exchange_code_for_token`` (which opens
    its own ``httpx.AsyncClient``, bypassing ``GitHubApiClient`` entirely)
    or requires a real token-encryption key (blank in demo — see
    ``docs/demo.md``); it stores the same placeholder value the seeder uses.
    """

    def authorize_url(self, *, user_id: uuid.UUID) -> str:
        settings = get_settings()
        state = create_oauth_state(user_id, secret_key=settings.secret_key)
        return f"/integrations/github/callback?code=demo-code&state={state}"

    async def handle_callback(
        self, *, user_id: uuid.UUID, code: str, state: str
    ) -> GitHubConnection:
        settings = get_settings()
        try:
            verify_oauth_state(state, user_id, secret_key=settings.secret_key)
        except ValueError as exc:
            raise AppError(
                code="invalid_oauth_state",
                message=(
                    "OAuth state is invalid or expired. "
                    "Please restart the GitHub authorization flow."
                ),
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc

        gh_user = await self._api_client.get_authenticated_user(code)
        github_user_id = str(gh_user["id"])
        github_login = str(gh_user["login"])
        encrypted = "seed-placeholder-not-a-token"

        existing = await self._conn_repo.get_by_user_id(user_id)
        if existing:
            return await self._conn_repo.update_token(
                existing, access_token_encrypted=encrypted, scopes=_DEMO_SCOPES
            )
        return await self._conn_repo.create(
            user_id=user_id,
            github_user_id=github_user_id,
            github_login=github_login,
            access_token_encrypted=encrypted,
            scopes=_DEMO_SCOPES,
        )
