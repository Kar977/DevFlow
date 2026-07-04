"""Async GitHub REST API client with simple retry/backoff."""

import asyncio
from typing import Any

import httpx

GITHUB_API_BASE_URL = "https://api.github.com"
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 0.5
_DEFAULT_PER_PAGE = 100
_DEFAULT_MAX_PAGES = 10


class GitHubApiClient:
    """Thin authenticated wrapper over the GitHub REST API."""

    def __init__(
        self,
        *,
        base_url: str = GITHUB_API_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        backoff_base_seconds: float = _BACKOFF_BASE_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._backoff_base_seconds = backoff_base_seconds

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        async with httpx.AsyncClient(transport=self._transport) as client:
            for attempt in range(_MAX_RETRIES):
                try:
                    response = await client.request(
                        method,
                        url,
                        headers=self._headers(token),
                        params=params,
                        timeout=15.0,
                    )
                except httpx.HTTPError as exc:  # network-level failure
                    last_exc = exc
                else:
                    if response.status_code < 500 and response.status_code != 429:
                        response.raise_for_status()
                        return response
                    last_exc = httpx.HTTPStatusError(
                        "retryable status", request=response.request, response=response
                    )
                await asyncio.sleep(self._backoff_base_seconds * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def _get(
        self, path: str, *, token: str, params: dict[str, str] | None = None
    ) -> Any:
        response = await self._request("GET", path, token=token, params=params)
        return response.json()

    async def _get_paginated(
        self,
        path: str,
        *,
        token: str,
        params: dict[str, str] | None = None,
        item_key: str | None = None,
        per_page: int = _DEFAULT_PER_PAGE,
        max_pages: int = _DEFAULT_MAX_PAGES,
    ) -> list[dict[str, Any]]:
        """Collect items across pages until a short page or the page cap."""
        items: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            page_params = dict(params or {})
            page_params["per_page"] = str(per_page)
            page_params["page"] = str(page)
            data = await self._get(path, token=token, params=page_params)
            batch: list[dict[str, Any]] = data[item_key] if item_key else data
            items.extend(batch)
            if len(batch) < per_page:
                break
        return items

    # ------------------------------------------------------------------
    # GitHub App (authenticated with an app JWT)
    # ------------------------------------------------------------------

    async def create_installation_access_token(
        self, app_jwt: str, installation_id: int
    ) -> dict[str, Any]:
        """Mint a short-lived installation access token."""
        response = await self._request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            token=app_jwt,
        )
        result: dict[str, Any] = response.json()
        return result

    async def get_installation(
        self, app_jwt: str, installation_id: int
    ) -> dict[str, Any]:
        """Return installation metadata (account, repository_selection)."""
        result: dict[str, Any] = await self._get(
            f"/app/installations/{installation_id}", token=app_jwt
        )
        return result

    async def delete_installation(self, app_jwt: str, installation_id: int) -> None:
        """Uninstall the app from the target account."""
        await self._request(
            "DELETE", f"/app/installations/{installation_id}", token=app_jwt
        )

    # ------------------------------------------------------------------
    # Installation-token endpoints
    # ------------------------------------------------------------------

    async def list_installation_repositories(
        self,
        token: str,
        *,
        per_page: int = _DEFAULT_PER_PAGE,
        max_pages: int = _DEFAULT_MAX_PAGES,
    ) -> list[dict[str, Any]]:
        """Return repositories accessible to the installation."""
        return await self._get_paginated(
            "/installation/repositories",
            token=token,
            item_key="repositories",
            per_page=per_page,
            max_pages=max_pages,
        )

    async def list_repo_pulls(
        self,
        token: str,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = _DEFAULT_PER_PAGE,
        max_pages: int = _DEFAULT_MAX_PAGES,
    ) -> list[dict[str, Any]]:
        """Return pull requests of a repository, most recently updated first."""
        return await self._get_paginated(
            f"/repos/{owner}/{repo}/pulls",
            token=token,
            params={"state": state, "sort": sort, "direction": direction},
            per_page=per_page,
            max_pages=max_pages,
        )

    # ------------------------------------------------------------------
    # User-token endpoints
    # ------------------------------------------------------------------

    async def get_authenticated_user(self, token: str) -> dict[str, Any]:
        """Return the authenticated user's profile (GET /user)."""
        result: dict[str, Any] = await self._get("/user", token=token)
        return result

    async def list_assigned_issues(self, token: str) -> list[dict[str, Any]]:
        """Return issues (and PRs) assigned to the authenticated user."""
        result: list[dict[str, Any]] = await self._get(
            "/issues",
            token=token,
            params={"filter": "assigned", "state": "open", "per_page": "100"},
        )
        return result

    async def list_assigned_prs(self, token: str) -> list[dict[str, Any]]:
        """Return pull requests assigned to the user.

        Filters GitHub issues to items that have a ``pull_request`` key.
        """
        items: list[dict[str, Any]] = await self._get(
            "/issues",
            token=token,
            params={"filter": "assigned", "state": "all", "per_page": "100"},
        )
        return [item for item in items if "pull_request" in item]

    async def list_authored_prs(self, token: str) -> list[dict[str, Any]]:
        """Return pull requests created by the authenticated user.

        Uses ``filter=created`` so solo developers see their own PRs even when
        those PRs are not explicitly assigned to them.
        """
        items: list[dict[str, Any]] = await self._get(
            "/issues",
            token=token,
            params={"filter": "created", "state": "all", "per_page": "100"},
        )
        return [item for item in items if "pull_request" in item]

    async def list_pr_reviews(
        self, token: str, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        """Return reviews for a specific pull request."""
        result: list[dict[str, Any]] = await self._get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            token=token,
        )
        return result
