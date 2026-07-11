"""Pull request endpoint tests — org-scoped list and detail."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.pull_request_review import PullRequestReview
from devflow_api.core.models.repository import Repository
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.pull_request import (
    PullRequestService,
    get_pull_request_service,
)
from devflow_api.main import create_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)

ORG_ID = uuid.uuid4()
REPO_ID = uuid.uuid4()
REPO_FULL_NAME = "octo-org/api"


def _make_repository(repo_id: uuid.UUID = REPO_ID) -> Repository:
    return Repository(
        id=repo_id,
        organization_id=ORG_ID,
        github_installation_id=uuid.uuid4(),
        github_repo_id=1001,
        full_name=REPO_FULL_NAME,
        private=False,
        default_branch="main",
        tracked=True,
        last_synced_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_pr(
    *,
    repository_id: uuid.UUID = REPO_ID,
    state: str = "open",
    merged_at: datetime | None = None,
    first_review_at: datetime | None = None,
    created_offset_days: int = 0,
) -> PullRequest:
    created = _NOW - timedelta(days=created_offset_days)
    return PullRequest(
        id=uuid.uuid4(),
        repository_id=repository_id,
        github_pr_id=uuid.uuid4().int % 100000,
        number=42,
        title="Fix: something",
        author_login="octocat",
        state=state,
        created_at_github=created,
        merged_at=merged_at,
        closed_at=None,
        first_review_at=first_review_at,
        html_url=f"https://github.com/{REPO_FULL_NAME}/pull/42",
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


class FakeOrgRepo:
    def __init__(self) -> None:
        self.members: dict[tuple[uuid.UUID, uuid.UUID], OrganizationMember] = {}

    def seed_member(self, org_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
        self.members[(org_id, user_id)] = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role=role,
            joined_at=_NOW,
        )

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return self.members.get((org_id, user_id))


class FakeRepositoryRepo:
    def __init__(self) -> None:
        self.rows: list[Repository] = []

    async def list_for_org(
        self, org_id: uuid.UUID, *, tracked: bool | None = None
    ) -> list[Repository]:
        rows = [r for r in self.rows if r.organization_id == org_id]
        if tracked is not None:
            rows = [r for r in rows if r.tracked == tracked]
        return rows


class FakePRRepo:
    def __init__(self, repos: FakeRepositoryRepo) -> None:
        self._repos = repos
        self._prs: list[PullRequest] = []
        self._reviews: dict[uuid.UUID, list[PullRequestReview]] = {}

    def seed(self, pr: PullRequest) -> None:
        self._prs.append(pr)

    def seed_review(self, review: PullRequestReview) -> None:
        self._reviews.setdefault(review.pull_request_id, []).append(review)

    def _org_repo_ids(self, org_id: uuid.UUID) -> set[uuid.UUID]:
        return {r.id for r in self._repos.rows if r.organization_id == org_id}

    def _filtered(
        self,
        org_id: uuid.UUID,
        repository_id: uuid.UUID | None,
        state: str | None,
        author_login: str | None,
    ) -> list[PullRequest]:
        repo_ids = self._org_repo_ids(org_id)
        result = [pr for pr in self._prs if pr.repository_id in repo_ids]
        if repository_id:
            result = [pr for pr in result if pr.repository_id == repository_id]
        if state:
            result = [pr for pr in result if pr.state == state]
        if author_login:
            result = [pr for pr in result if pr.author_login == author_login]
        return result

    async def list_for_org(
        self,
        org_id: uuid.UUID,
        *,
        repository_id: uuid.UUID | None = None,
        state: str | None = None,
        author_login: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PullRequest]:
        result = self._filtered(org_id, repository_id, state, author_login)
        return result[offset : offset + limit]

    async def count_for_org(
        self,
        org_id: uuid.UUID,
        *,
        repository_id: uuid.UUID | None = None,
        state: str | None = None,
        author_login: str | None = None,
    ) -> int:
        return len(self._filtered(org_id, repository_id, state, author_login))

    async def get_by_id_for_org(
        self, pr_id: uuid.UUID, org_id: uuid.UUID
    ) -> PullRequest | None:
        repo_ids = self._org_repo_ids(org_id)
        return next(
            (pr for pr in self._prs if pr.id == pr_id and pr.repository_id in repo_ids),
            None,
        )

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
def repository_repo() -> FakeRepositoryRepo:
    repo = FakeRepositoryRepo()
    repo.rows.append(_make_repository())
    return repo


@pytest.fixture()
def pr_repo(repository_repo: FakeRepositoryRepo) -> FakePRRepo:
    return FakePRRepo(repository_repo)


@pytest.fixture()
def org_repo(user_id: uuid.UUID) -> FakeOrgRepo:
    repo = FakeOrgRepo()
    repo.seed_member(ORG_ID, user_id, "member")
    return repo


@pytest.fixture()
def client(
    user_id: uuid.UUID,
    pr_repo: FakePRRepo,
    repository_repo: FakeRepositoryRepo,
    org_repo: FakeOrgRepo,
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_pull_request_service] = lambda: PullRequestService(
        pr_repo=pr_repo,  # type: ignore[arg-type]
        repository_repo=repository_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
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
    response = client.get(f"/api/v1/pull-requests?organization_id={ORG_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_pull_requests_returns_items(
    client: TestClient, pr_repo: FakePRRepo
) -> None:
    pr_repo.seed(_make_pr())
    pr_repo.seed(_make_pr())
    response = client.get(f"/api/v1/pull-requests?organization_id={ORG_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["items"][0]["repository_full_name"] == REPO_FULL_NAME


def test_list_pull_requests_filters_state(
    client: TestClient, pr_repo: FakePRRepo
) -> None:
    pr_repo.seed(_make_pr(state="open"))
    pr_repo.seed(_make_pr(state="merged"))
    response = client.get(f"/api/v1/pull-requests?organization_id={ORG_ID}&state=open")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["state"] == "open"


def test_list_pull_requests_requires_org_param(client: TestClient) -> None:
    response = client.get("/api/v1/pull-requests")
    assert response.status_code == 422


def test_list_pull_requests_rejects_non_member(
    client: TestClient, pr_repo: FakePRRepo
) -> None:
    response = client.get(f"/api/v1/pull-requests?organization_id={uuid.uuid4()}")
    assert response.status_code == 403


def test_list_pull_requests_requires_auth() -> None:
    app = create_app()
    with TestClient(app) as c:
        response = c.get(f"/api/v1/pull-requests?organization_id={ORG_ID}")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Get pull request detail
# ---------------------------------------------------------------------------


def test_get_pull_request_detail(client: TestClient, pr_repo: FakePRRepo) -> None:
    pr = _make_pr()
    review = _make_review(pr.id)
    pr_repo.seed(pr)
    pr_repo.seed_review(review)
    response = client.get(f"/api/v1/pull-requests/{pr.id}?organization_id={ORG_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(pr.id)
    assert body["repository_full_name"] == REPO_FULL_NAME
    assert len(body["reviews"]) == 1
    assert body["reviews"][0]["reviewer_login"] == "reviewer1"


def test_get_pull_request_not_found(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/pull-requests/{uuid.uuid4()}?organization_id={ORG_ID}"
    )
    assert response.status_code == 404


def test_get_pull_request_from_other_org_returns_404(
    client: TestClient, pr_repo: FakePRRepo, org_repo: FakeOrgRepo, user_id: uuid.UUID
) -> None:
    other_repo_id = uuid.uuid4()  # repo not registered in ORG_ID
    pr = _make_pr(repository_id=other_repo_id)
    pr_repo.seed(pr)
    response = client.get(f"/api/v1/pull-requests/{pr.id}?organization_id={ORG_ID}")
    assert response.status_code == 404
