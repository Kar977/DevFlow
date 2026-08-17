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
from devflow_api.core.services.period import week_start as _week_start
from devflow_api.core.services.pr_metrics import (
    PRMetricsService,
    _build_pr_trends,
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
# get_pr_flow_report — period-aware KPIs + bottlenecks (audit gap #9)
# ---------------------------------------------------------------------------


def test_get_pr_flow_report_computes_period_kpis() -> None:
    service = _service(
        [
            _pr(state="merged", merged_at=_NOW - timedelta(days=2)),
            _pr(
                state="open",
                created_offset_days=1,
                first_review_at=_NOW - timedelta(hours=1),
            ),
        ]
    )
    result = asyncio.run(
        service.get_pr_flow_report(
            org_id=ORG_ID,
            user_id=USER_ID,
            date_from=_NOW - timedelta(days=7),
            date_to=_NOW,
        )
    )
    assert result.throughput == 1
    assert result.review_ratio == pytest.approx(0.5)


def test_get_pr_flow_report_bottlenecks_lists_stale_open_prs_oldest_first() -> None:
    newer_stale = _pr(state="open", created_offset_days=6)
    older_stale = _pr(state="open", created_offset_days=20)
    not_stale = _pr(state="open", created_offset_days=1)
    service = _service([newer_stale, older_stale, not_stale])
    result = asyncio.run(
        service.get_pr_flow_report(
            org_id=ORG_ID, user_id=USER_ID, date_from=None, date_to=None
        )
    )
    assert result.stale_pr_count == 2
    ids = [item.number for item in result.bottlenecks.stale_open]
    # oldest first
    assert result.bottlenecks.stale_open[0].age_days > (
        result.bottlenecks.stale_open[1].age_days
    )
    assert len(ids) == 2


def test_get_pr_flow_report_bottlenecks_caps_at_five() -> None:
    prs = [_pr(state="open", created_offset_days=10 + i) for i in range(8)]
    service = _service(prs)
    result = asyncio.run(
        service.get_pr_flow_report(
            org_id=ORG_ID, user_id=USER_ID, date_from=None, date_to=None
        )
    )
    assert result.stale_pr_count == 8
    assert len(result.bottlenecks.stale_open) == 5


def test_get_pr_flow_report_lists_slowest_first_review() -> None:
    slow = _pr(created_offset_days=5)
    slow.first_review_at = _NOW - timedelta(days=1)  # ~4 days wait
    fast = _pr(created_offset_days=1)
    fast.first_review_at = _NOW - timedelta(hours=1)  # ~23h wait
    unreviewed = _pr(created_offset_days=2)
    service = _service([slow, fast, unreviewed])
    result = asyncio.run(
        service.get_pr_flow_report(
            org_id=ORG_ID, user_id=USER_ID, date_from=None, date_to=None
        )
    )
    waits = [item.wait_hours for item in result.bottlenecks.slowest_first_review]
    assert len(waits) == 2
    assert waits == sorted(waits, reverse=True)


def test_get_pr_flow_report_rejects_non_member() -> None:
    service = _service([], org_repo=FakeOrgRepo())  # no membership seeded
    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.get_pr_flow_report(
                org_id=ORG_ID, user_id=USER_ID, date_from=None, date_to=None
            )
        )
    assert exc_info.value.status_code == 403


def test_get_pr_flow_report_empty_org_returns_nulls_and_empty_lists() -> None:
    service = _service([])
    result = asyncio.run(
        service.get_pr_flow_report(
            org_id=ORG_ID, user_id=USER_ID, date_from=None, date_to=None
        )
    )
    assert result.stale_pr_count == 0
    assert result.time_to_first_review_h is None
    assert result.review_velocity_h is None
    assert result.throughput == 0
    assert result.review_ratio is None
    assert result.bottlenecks.stale_open == []
    assert result.bottlenecks.slowest_first_review == []


def test_pr_dashboard_windows_unchanged_after_generalising_helpers() -> None:
    """Pin: get_pr_dashboard's output must not shift after _review_velocity
    and _weekly_throughput were generalised to accept an explicit window
    instead of hardcoding `now`."""
    prs = [
        _pr(state="merged", merged_at=_NOW - timedelta(days=3)),
        _pr(
            state="open",
            created_offset_days=2,
            first_review_at=_NOW - timedelta(hours=5),
        ),
    ]
    result = _run(prs)
    assert result.weekly_throughput == 1
    assert result.review_velocity == pytest.approx(
        (_NOW - timedelta(hours=5) - (_NOW - timedelta(days=2))).total_seconds() / 3600
    )


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
# _build_pr_trends — pure function, no fakes needed
# ---------------------------------------------------------------------------


def test_build_pr_trends_zero_fills_empty_weeks() -> None:
    result = _build_pr_trends([], now=_NOW, weeks=4)
    assert len(result.weekly) == 4
    assert all(p.opened == 0 and p.merged == 0 for p in result.weekly)
    assert all(p.avg_time_to_first_review_h is None for p in result.weekly)
    week_starts = [p.week_start for p in result.weekly]
    assert week_starts == sorted(week_starts)


def test_build_pr_trends_buckets_opened_by_created_at() -> None:
    # Hour-based offsets (not day-based) so the PRs stay in *today's* ISO
    # week regardless of which weekday the suite happens to run on.
    pr1, pr2 = _pr(), _pr()
    pr1.created_at_github = _NOW - timedelta(hours=2)
    pr2.created_at_github = _NOW - timedelta(hours=1)
    result = _build_pr_trends([pr1, pr2], now=_NOW, weeks=4)
    assert result.weekly[-1].opened == 2
    assert result.weekly[-1].merged == 0


def test_build_pr_trends_merged_buckets_by_merged_at_not_created_at() -> None:
    # Opened 3 whole weeks ago (a 21-day, i.e. exact-multiple-of-7 offset
    # keeps ISO-week alignment regardless of today's weekday) but merged
    # this week: must count in the MERGED week's bucket, not the OPENED
    # week's bucket.
    pr = _pr(created_offset_days=21, state="merged")
    pr.merged_at = _NOW - timedelta(hours=2)
    result = _build_pr_trends([pr], now=_NOW, weeks=4)
    assert result.weekly[-1].merged == 1
    assert result.weekly[-1].opened == 0
    assert result.weekly[0].opened == 1
    assert result.weekly[0].merged == 0


def test_build_pr_trends_avg_review_time_is_cohort_by_created_week() -> None:
    # Anchored to the start of the *current* ISO week (not to "now" minus a
    # fixed offset) so a 24h created→reviewed gap can never spill into the
    # previous week regardless of what time of day the suite runs.
    week_start = datetime.combine(_week_start(_NOW), datetime.min.time(), tzinfo=UTC)
    pr = _pr()
    pr.created_at_github = week_start
    pr.first_review_at = week_start + timedelta(hours=24)
    result = _build_pr_trends([pr], now=_NOW, weeks=2)
    assert result.weekly[-1].avg_time_to_first_review_h == pytest.approx(24.0)


def test_build_pr_trends_out_of_window_prs_are_excluded() -> None:
    pr = _pr(created_offset_days=100)
    result = _build_pr_trends([pr], now=_NOW, weeks=4)
    assert all(p.opened == 0 for p in result.weekly)


# ---------------------------------------------------------------------------
# get_pr_trends — service + route
# ---------------------------------------------------------------------------


def test_get_pr_trends_rejects_non_member() -> None:
    service = _service([], org_repo=FakeOrgRepo())  # no membership seeded
    with pytest.raises(AppError) as exc_info:
        asyncio.run(service.get_pr_trends(org_id=ORG_ID, user_id=USER_ID))
    assert exc_info.value.status_code == 403


def test_get_pr_trends_member_without_link_returns_404() -> None:
    service = _service([])
    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            service.get_pr_trends(
                org_id=ORG_ID, user_id=USER_ID, member_user_id=uuid.uuid4()
            )
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "member_not_linked"


def test_get_pr_trends_returns_requested_week_count() -> None:
    service = _service([_pr(created_offset_days=1)])
    result = asyncio.run(service.get_pr_trends(org_id=ORG_ID, user_id=USER_ID, weeks=6))
    assert len(result.weekly) == 6


def test_pr_trends_route_returns_200() -> None:
    prs = [_pr(created_offset_days=1)]
    service = _service(prs)
    app = create_app()
    app.dependency_overrides[get_pr_metrics_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(USER_ID)
    )
    with TestClient(app) as c:
        response = c.get(f"/api/v1/metrics/pr-trends?organization_id={ORG_ID}&weeks=4")
    assert response.status_code == 200
    body = response.json()
    assert len(body["weekly"]) == 4


def test_pr_trends_route_requires_org_param() -> None:
    service = _service([])
    app = create_app()
    app.dependency_overrides[get_pr_metrics_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(USER_ID)
    )
    with TestClient(app) as c:
        response = c.get("/api/v1/metrics/pr-trends")
    assert response.status_code == 422


def test_pr_trends_route_rejects_zero_weeks() -> None:
    service = _service([])
    app = create_app()
    app.dependency_overrides[get_pr_metrics_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(USER_ID)
    )
    with TestClient(app) as c:
        response = c.get(f"/api/v1/metrics/pr-trends?organization_id={ORG_ID}&weeks=0")
    assert response.status_code == 422


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
