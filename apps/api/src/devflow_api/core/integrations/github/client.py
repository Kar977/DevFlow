"""Async GitHub REST API client with simple retry/backoff."""

import asyncio
from typing import Any

import httpx

GITHUB_API_BASE_URL = "https://api.github.com"
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 0.5


class GitHubApiClient:
    """Thin authenticated wrapper over the GitHub REST API."""

    def __init__(self, *, base_url: str = GITHUB_API_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get(
        self, path: str, *, token: str, params: dict[str, str] | None = None
    ) -> Any:
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        async with httpx.AsyncClient() as client:
            for attempt in range(_MAX_RETRIES):
                try:
                    response = await client.get(
                        url, headers=self._headers(token), params=params, timeout=15.0
                    )
                except httpx.HTTPError as exc:  # network-level failure
                    last_exc = exc
                else:
                    if response.status_code < 500 and response.status_code != 429:
                        response.raise_for_status()
                        return response.json()
                    last_exc = httpx.HTTPStatusError(
                        "retryable status", request=response.request, response=response
                    )
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
        assert last_exc is not None
        raise last_exc

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
