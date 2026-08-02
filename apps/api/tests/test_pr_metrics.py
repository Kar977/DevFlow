"""PRMetricsService unit tests — 5 KPI formulas, member filter, edge cases."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.errors import AppError
from devflow_api.core.models.github_connection import GitHubConnection
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.user import User
from devflow_api.core.schemas.metrics import PRDashboardResponse
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.pr_metrics import (
    PRMetricsService,
    get_pr_metrics_service,
)
from devflow_api.main import create_app

# Windows in PRMetricsService are computed against the real clock, so test
# data must be anchored to it as well.
_NOW = datetime.now(UTC)

ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
REPO_ID = uuid.uuid4()


def _pr(
    *,
    state: str = "open",
    author_login: str = "dev",
    created_offset_days: int = 0,
    merged_at: datetime | None = None,
    first_review_at: datetime | None = None,
) -> PullRequest:
    created = _NOW - timedelta(days=created_offset_days)
    return PullRequest(
        id=uuid.uuid4(),
        repository_id=REPO_ID,
        github_pr_id=uuid.uuid4().int % 100000,
        number=1,
        title="PR",
        author_login=author_login,
        state=state,
        created_at_github=created,
        merged_at=merged_at,
        closed_at=None,
        first_review_at=first_review_at,
        html_url="https://github.com/owner/repo/pull/1",
        last_synced_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )


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

    async def list_members(self, org_id: uuid.UUID) -> list[OrganizationMember]:
        return [m for (o, _u), m in self.members.items() if o == org_id]


class FakePRRepo:
    def __init__(self, prs: list[PullRequest]) -> None:
        self._prs = prs

    async def list_for_org(
        self,
        org_id: uuid.UUID,
        *,
        author_login: str | None = None,
        limit: int = 50,
        offset: int = 0,
        **_: object,
    ) -> list[PullRequest]:
        if author_login is not None:
            return [pr for pr in self._prs if pr.author_login == author_login]
        return self._prs


class FakeConnRepo:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, GitHubConnection] = {}

    def seed(self, user_id: uuid.UUID, github_login: str) -> None:
        self.rows[user_id] = GitHubConnection(
            id=uuid.uuid4(),
            user_id=user_id,
            github_user_id="1",
            github_login=github_login,
            access_token_encrypted="enc",
            scopes="read:user",
            connected_at=_NOW,
            updated_at=_NOW,
        )

    async def get_by_user_id(self, user_id: uuid.UUID) -> GitHubConnection | None:
        return self.rows.get(user_id)


class FakeUserRepo:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, User] = {}

    def seed(self, user_id: uuid.UUID, full_name: str | None, email: str) -> None:
        self.rows[user_id] = User(
            id=user_id,
            email=email,
            hashed_password="x",
            full_name=full_name,
            avatar_url=None,
            created_at=_NOW,
            updated_at=_NOW,
        )

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.rows.get(user_id)


def _service(
    prs: list[PullRequest],
    *,
    org_repo: FakeOrgRepo | None = None,
    conn_repo: FakeConnRepo | None = None,
    user_repo: FakeUserRepo | None = None,
) -> PRMetricsService:
    if org_repo is None:
        org_repo = FakeOrgRepo()
        org_repo.seed_member(ORG_ID, USER_ID, "member")
    return PRMetricsService(
        pr_repo=FakePRRepo(prs),  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
        conn_repo=conn_repo or FakeConnRepo(),  # type: ignore[arg-type]
        user_repo=user_repo or FakeUserRepo(),  # type: ignore[arg-type]
    )


def _run(prs: list[PullRequest], **kwargs: Any) -> PRDashboardResponse:
    service = _service(prs, **kwargs)
    return asyncio.run(service.get_pr_dashboard(org_id=ORG_ID, user_id=USER_ID))


# ---------------------------------------------------------------------------
# stale_pr_count
# ---------------------------------------------------------------------------


def test_stale_pr_count_zero_when_no_prs() -> None:
    result = _run([])
    assert result.stale_pr_count == 0


def test_stale_pr_count_counts_open_older_than_5_days() -> None:
    prs = [
        _pr(state="open", created_offset_days=6),  # stale
        _pr(state="open", created_offset_days=4),  # not stale
        _pr(state="merged", created_offset_days=10),  # not open
    ]
    result = _run(prs)
    assert result.stale_pr_count == 1


# ---------------------------------------------------------------------------
# time_to_first_review
# ---------------------------------------------------------------------------


def test_time_to_first_review_none_when_no_reviews() -> None:
    result = _run([_pr(state="open", created_offset_days=1)])
    assert result.time_to_first_review is None


def test_time_to_first_review_calculates_average() -> None:
    # 2 hours and 4 hours → average 3 hours
    pr1 = _pr(state="open")
    pr1.created_at_github = _NOW - timedelta(hours=10)
    pr1.first_review_at = _NOW - timedelta(hours=8)

    pr2 = _pr(state="open")
    pr2.created_at_github = _NOW - timedelta(hours=6)
    pr2.first_review_at = _NOW - timedelta(hours=2)

    result = _run([pr1, pr2])
    assert result.time_to_first_review == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# review_velocity
# ---------------------------------------------------------------------------


def test_review_velocity_none_when_no_recent_reviews() -> None:
    old_review_at = _NOW - timedelta(days=10)
    pr = _pr(state="merged", created_offset_days=15, first_review_at=old_review_at)
    result = _run([pr])
    assert result.review_velocity is None


# ---------------------------------------------------------------------------
# weekly_throughput
# ---------------------------------------------------------------------------


def test_weekly_throughput_counts_merged_in_window() -> None:
    prs = [
        _pr(state="merged", merged_at=_NOW - timedelta(days=3)),
        _pr(state="merged", merged_at=_NOW - timedelta(days=3)),
        _pr(state="merged", merged_at=_NOW - timedelta(days=10)),  # outside
        _pr(state="open"),
    ]
    result = _run(prs)
    assert result.weekly_throughput == 2


# ---------------------------------------------------------------------------
# review_ratio
# ---------------------------------------------------------------------------


def test_review_ratio_none_when_no_prs() -> None:
    result = _run([])
    assert result.review_ratio is None


def test_review_ratio_zero_when_no_reviews() -> None:
    result = _run([_pr(), _pr()])
    assert result.review_ratio == pytest.approx(0.0)


def test_review_ratio_calculates_fraction() -> None:
    reviewed = _pr(first_review_at=_NOW - timedelta(hours=2))
    unreviewed = _pr()
    result = _run([reviewed, unreviewed])
    assert result.review_ratio == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Access control + member filter
# ---------------------------------------------------------------------------


def test_dashboard_rejects_non_member() -> None:
    service = _service([], org_repo=FakeOrgRepo())  # no membership seeded
    with pytest.raises(AppError) as exc_info:
        asyncio.run(service.get_pr_dashboard(org_id=ORG_ID, user_id=USER_ID))
    assert exc_info.value.status_code == 403


def test_dashboard_filters_by_member_github_login() -> None:
    member_id = uuid.uuid4()
    conn_repo = FakeConnRepo()
    conn_repo.seed(member_id, "octocat")
    prs = [
        _pr(author_login="octocat", state="merged", merged_at=_NOW),
        _pr(author_login="someone-else", state="merged", merged_at=_NOW),
    ]
    service = _service(prs, conn_repo=conn_repo)
    result = asyncio.run(
        service.get_pr_dashboard(
            org_id=ORG_ID, user_id=USER_ID, member_user_id=member_id
        )
    )
    assert result.weekly_throughput == 1


def test_dashboard_member_without_link_returns_404() -> None:
    service = _service([])
    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.get_pr_dashboard(
                org_id=ORG_ID, user_id=USER_ID, member_user_id=uuid.uuid4()
            )
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "member_not_linked"


def test_list_members_marks_unlinked() -> None:
    linked_id = uuid.uuid4()
    unlinked_id = uuid.uuid4()
    org_repo = FakeOrgRepo()
    org_repo.seed_member(ORG_ID, USER_ID, "member")
    org_repo.seed_member(ORG_ID, linked_id, "member")
    org_repo.seed_member(ORG_ID, unlinked_id, "member")
    conn_repo = FakeConnRepo()
    conn_repo.seed(linked_id, "octocat")
    user_repo = FakeUserRepo()
    user_repo.seed(USER_ID, "Me", "me@example.com")
    user_repo.seed(linked_id, "Linked Dev", "linked@example.com")
    user_repo.seed(unlinked_id, None, "unlinked@example.com")

    service = _service([], org_repo=org_repo, conn_repo=conn_repo, user_repo=user_repo)
    result = asyncio.run(service.list_members(org_id=ORG_ID, user_id=USER_ID))

    by_id = {item.user_id: item for item in result.data}
    assert by_id[linked_id].github_login == "octocat"
    assert by_id[unlinked_id].github_login is None
    assert by_id[unlinked_id].display_name == "unlinked@example.com"


# ---------------------------------------------------------------------------
# Route test
# ---------------------------------------------------------------------------


def test_pr_dashboard_route_returns_200() -> None:
    prs = [_pr(state="merged", merged_at=_NOW - timedelta(days=2))]
    service = _service(prs)
    app = create_app()
    app.dependency_overrides[get_pr_metrics_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(USER_ID)
    )
    with TestClient(app) as c:
        response = c.get(f"/api/v1/metrics/pr-dashboard?organization_id={ORG_ID}")
    assert response.status_code == 200
    body = response.json()
    assert "stale_pr_count" in body
    assert body["weekly_throughput"] == 1


def test_pr_dashboard_route_requires_org_param() -> None:
    service = _service([])
    app = create_app()
    app.dependency_overrides[get_pr_metrics_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(USER_ID)
    )
    with TestClient(app) as c:
        response = c.get("/api/v1/metrics/pr-dashboard")
    assert response.status_code == 422


def test_pr_dashboard_members_route_returns_items() -> None:
    org_repo = FakeOrgRepo()
    org_repo.seed_member(ORG_ID, USER_ID, "member")
    user_repo = FakeUserRepo()
    user_repo.seed(USER_ID, "Me", "me@example.com")
    service = _service([], org_repo=org_repo, user_repo=user_repo)
    app = create_app()
    app.dependency_overrides[get_pr_metrics_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(USER_ID)
    )
    with TestClient(app) as c:
        response = c.get(
            f"/api/v1/metrics/pr-dashboard/members?organization_id={ORG_ID}"
        )
    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) == 1
    assert items[0]["display_name"] == "Me"
