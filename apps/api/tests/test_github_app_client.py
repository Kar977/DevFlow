"""GitHubApiClient tests for GitHub App endpoints — token minting, repos, pulls."""

from typing import Any

import httpx
import pytest

from devflow_api.core.integrations.github.client import GitHubApiClient


def make_client(handler: Any) -> GitHubApiClient:
    return GitHubApiClient(
        transport=httpx.MockTransport(handler), backoff_base_seconds=0.0
    )


async def test_create_installation_access_token_posts_with_app_jwt() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["auth"] = request.headers["Authorization"]
        return httpx.Response(
            201,
            json={"token": "ghs_abc", "expires_at": "2026-07-04T13:00:00Z"},
        )

    client = make_client(handler)
    result = await client.create_installation_access_token("app.jwt.token", 42)

    assert captured["method"] == "POST"
    assert captured["path"] == "/app/installations/42/access_tokens"
    assert captured["auth"] == "Bearer app.jwt.token"
    assert result["token"] == "ghs_abc"


async def test_get_installation_returns_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/app/installations/42"
        return httpx.Response(
            200,
            json={
                "id": 42,
                "account": {"login": "octo-org", "type": "Organization"},
                "repository_selection": "selected",
            },
        )

    client = make_client(handler)
    result = await client.get_installation("app.jwt.token", 42)
    assert result["account"]["login"] == "octo-org"


async def test_delete_installation_accepts_204() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(204)

    client = make_client(handler)
    await client.delete_installation("app.jwt.token", 42)
    assert captured["method"] == "DELETE"
    assert captured["path"] == "/app/installations/42"


async def test_list_installation_repositories_unwraps_and_paginates() -> None:
    pages: list[list[dict[str, Any]]] = [
        [{"id": i, "full_name": f"o/r{i}"} for i in range(2)],
        [{"id": 2, "full_name": "o/r2"}],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/installation/repositories"
        page = int(request.url.params["page"])
        items = pages[page - 1] if page <= len(pages) else []
        return httpx.Response(200, json={"repositories": items})

    client = make_client(handler)
    repos = await client.list_installation_repositories("ghs_abc", per_page=2)
    assert [r["id"] for r in repos] == [0, 1, 2]


async def test_list_repo_pulls_sends_params_and_paginates() -> None:
    seen_params: list[dict[str, str]] = []
    pages: list[list[dict[str, Any]]] = [
        [{"id": 10, "number": 1}, {"id": 11, "number": 2}],
        [{"id": 12, "number": 3}],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/octo/demo/pulls"
        seen_params.append(dict(request.url.params))
        page = int(request.url.params["page"])
        items = pages[page - 1] if page <= len(pages) else []
        return httpx.Response(200, json=items)

    client = make_client(handler)
    pulls = await client.list_repo_pulls("ghs_abc", "octo", "demo", per_page=2)

    assert [p["id"] for p in pulls] == [10, 11, 12]
    assert seen_params[0]["state"] == "all"
    assert seen_params[0]["sort"] == "updated"
    assert seen_params[0]["direction"] == "desc"


async def test_list_repo_pulls_respects_max_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        return httpx.Response(200, json=[{"id": page, "number": page}])

    client = make_client(handler)
    pulls = await client.list_repo_pulls(
        "ghs_abc", "octo", "demo", per_page=1, max_pages=3
    )
    assert [p["id"] for p in pulls] == [1, 2, 3]


async def test_post_raises_on_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    client = make_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await client.create_installation_access_token("app.jwt.token", 42)


async def test_get_retries_on_server_error() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"id": 42, "account": {"login": "x"}})

    client = make_client(handler)
    result = await client.get_installation("app.jwt.token", 42)
    assert result["id"] == 42
    assert attempts["count"] == 2
