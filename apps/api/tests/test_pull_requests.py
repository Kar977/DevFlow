"""Pull request endpoint tests — list, detail, repository list."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.pull_request_review import PullRequestReview
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.pull_request import (
    PullRequestService,
    get_pull_request_service,
)
from devflow_api.main import create_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


def _make_pr(
    user_id: uuid.UUID,
    *,
    state: str = "open",
    repo: str = "owner/repo",
    merged_at: datetime | None = None,
    first_review_at: datetime | None = None,
    created_offset_days: int = 0,
) -> PullRequest:
    created = _NOW - timedelta(days=created_offset_days)
    return PullRequest(
        id=uuid.uuid4(),
        user_id=user_id,
        github_pr_id=uuid.uuid4().int % 10000,
        github_repo_full_name=repo,
        number=42,
        title="Fix: something",
        author_login="octocat",
        state=state,
        created_at_github=created,
        merged_at=merged_at,
        closed_at=None,
        first_review_at=first_review_at,
        html_url=f"https://github.com/{repo}/pull/42",
        last_synced_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_review(pr_id: uuid.UUID) -> PullRequestReview:
    return PullRequestReview(
        id=uuid.uuid4(),
        pull_request_id=pr_id,
        github_review_id=101,
        reviewer_login="reviewer1",
        state="approved",
        submitted_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakePRRepo:
    def __init__(self) -> None:
        self._prs: list[PullRequest] = []
        self._reviews: dict[uuid.UUID, list[PullRequestReview]] = {}

    def seed(self, pr: PullRequest) -> None:
        self._prs.append(pr)

    def seed_review(self, review: PullRequestReview) -> None:
        self._reviews.setdefault(review.pull_request_id, []).append(review)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        state: str | None = None,
        author_login: str | None = None,
        repo: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PullRequest]:
        result = [pr for pr in self._prs if pr.user_id == user_id]
        if state:
            result = [pr for pr in result if pr.state == state]
        if author_login:
            result = [pr for pr in result if pr.author_login == author_login]
        if repo:
            result = [pr for pr in result if pr.github_repo_full_name == repo]
        return result[offset : offset + limit]

    async def count_for_user(
        self,
        user_id: uuid.UUID,
        *,
        state: str | None = None,
        author_login: str | None = None,
        repo: str | None = None,
    ) -> int:
        result = [pr for pr in self._prs if pr.user_id == user_id]
        if state:
            result = [pr for pr in result if pr.state == state]
        if author_login:
            result = [pr for pr in result if pr.author_login == author_login]
        if repo:
            result = [pr for pr in result if pr.github_repo_full_name == repo]
        return len(result)

    async def get_by_id(
        self, pr_id: uuid.UUID, user_id: uuid.UUID
    ) -> PullRequest | None:
        return next(
            (pr for pr in self._prs if pr.id == pr_id and pr.user_id == user_id), None
        )

    async def list_repos_for_user(self, user_id: uuid.UUID) -> list[str]:
        seen: list[str] = []
        for pr in self._prs:
            if pr.user_id == user_id and pr.github_repo_full_name not in seen:
                seen.append(pr.github_repo_full_name)
        return sorted(seen)

    async def list_reviews_for_pr(
        self, pull_request_id: uuid.UUID
    ) -> list[PullRequestReview]:
        return self._reviews.get(pull_request_id, [])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def pr_repo() -> FakePRRepo:
    return FakePRRepo()


@pytest.fixture()
def client(
    user_id: uuid.UUID,
    pr_repo: FakePRRepo,
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_pull_request_service] = lambda: PullRequestService(
        pr_repo=pr_repo  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# List pull requests
# ---------------------------------------------------------------------------


def test_list_pull_requests_empty(client: TestClient) -> None:
    response = client.get("/api/v1/pull-requests")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_pull_requests_returns_items(
    client: TestClient, user_id: uuid.UUID, pr_repo: FakePRRepo
) -> None:
    pr_repo.seed(_make_pr(user_id))
    pr_repo.seed(_make_pr(user_id))
    response = client.get("/api/v1/pull-requests")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 2


def test_list_pull_requests_filters_state(
    client: TestClient, user_id: uuid.UUID, pr_repo: FakePRRepo
) -> None:
    pr_repo.seed(_make_pr(user_id, state="open"))
    pr_repo.seed(_make_pr(user_id, state="merged"))
    response = client.get("/api/v1/pull-requests?state=open")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["state"] == "open"


def test_list_pull_requests_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as c:
        response = c.get("/api/v1/pull-requests")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Get pull request detail
# ---------------------------------------------------------------------------


def test_get_pull_request_detail(
    client: TestClient, user_id: uuid.UUID, pr_repo: FakePRRepo
) -> None:
    pr = _make_pr(user_id)
    review = _make_review(pr.id)
    pr_repo.seed(pr)
    pr_repo.seed_review(review)
    response = client.get(f"/api/v1/pull-requests/{pr.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(pr.id)
    assert len(body["reviews"]) == 1
    assert body["reviews"][0]["reviewer_login"] == "reviewer1"


def test_get_pull_request_not_found(client: TestClient) -> None:
    response = client.get(f"/api/v1/pull-requests/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_pull_request_other_user_returns_404(
    client: TestClient, pr_repo: FakePRRepo
) -> None:
    other_user = uuid.uuid4()
    pr = _make_pr(other_user)
    pr_repo.seed(pr)
    response = client.get(f"/api/v1/pull-requests/{pr.id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Repository list
# ---------------------------------------------------------------------------


def test_list_repositories_empty(client: TestClient) -> None:
    response = client.get("/api/v1/repositories")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_list_repositories_returns_aggregated(
    client: TestClient, user_id: uuid.UUID, pr_repo: FakePRRepo
) -> None:
    pr_repo.seed(_make_pr(user_id, repo="owner/alpha"))
    pr_repo.seed(_make_pr(user_id, repo="owner/alpha"))
    pr_repo.seed(_make_pr(user_id, repo="owner/beta"))
    response = client.get("/api/v1/repositories")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    alpha = next(i for i in items if i["full_name"] == "owner/alpha")
    assert alpha["pr_count"] == 2
