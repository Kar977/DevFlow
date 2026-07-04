"""PRMetricsService unit tests — 5 KPI formulas and edge cases."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.pull_request import PullRequest
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


def _pr(
    user_id: uuid.UUID,
    *,
    state: str = "open",
    created_offset_days: int = 0,
    merged_at: datetime | None = None,
    first_review_at: datetime | None = None,
) -> PullRequest:
    created = _NOW - timedelta(days=created_offset_days)
    return PullRequest(
        id=uuid.uuid4(),
        user_id=user_id,
        github_pr_id=uuid.uuid4().int % 100000,
        github_repo_full_name="owner/repo",
        number=1,
        title="PR",
        author_login="dev",
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


class FakePRRepo:
    def __init__(self, prs: list[PullRequest]) -> None:
        self._prs = prs

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0, **_: object
    ) -> list[PullRequest]:
        return self._prs


def _run(user_id: uuid.UUID, prs: list[PullRequest]) -> PRDashboardResponse:
    service = PRMetricsService(pr_repo=FakePRRepo(prs))  # type: ignore[arg-type]
    return asyncio.run(service.get_pr_dashboard(user_id=user_id))


# ---------------------------------------------------------------------------
# stale_pr_count
# ---------------------------------------------------------------------------


def test_stale_pr_count_zero_when_no_prs() -> None:
    result = _run(uuid.uuid4(), [])
    assert result.stale_pr_count == 0


def test_stale_pr_count_counts_open_older_than_5_days() -> None:
    user_id = uuid.uuid4()
    prs = [
        _pr(user_id, state="open", created_offset_days=6),  # stale
        _pr(user_id, state="open", created_offset_days=4),  # not stale
        _pr(user_id, state="merged", created_offset_days=10),  # not open
    ]
    result = _run(user_id, prs)
    assert result.stale_pr_count == 1


# ---------------------------------------------------------------------------
# time_to_first_review
# ---------------------------------------------------------------------------


def test_time_to_first_review_none_when_no_reviews() -> None:
    user_id = uuid.uuid4()
    result = _run(user_id, [_pr(user_id, state="open", created_offset_days=1)])
    assert result.time_to_first_review is None


def test_time_to_first_review_calculates_average() -> None:
    user_id = uuid.uuid4()
    # 2 hours and 4 hours → average 3 hours
    pr1 = _pr(user_id, state="open")
    pr1.created_at_github = _NOW - timedelta(hours=10)
    pr1.first_review_at = _NOW - timedelta(hours=8)

    pr2 = _pr(user_id, state="open")
    pr2.created_at_github = _NOW - timedelta(hours=6)
    pr2.first_review_at = _NOW - timedelta(hours=2)

    result = _run(user_id, [pr1, pr2])
    assert result.time_to_first_review == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# review_velocity
# ---------------------------------------------------------------------------


def test_review_velocity_none_when_no_recent_reviews() -> None:
    user_id = uuid.uuid4()
    old_review_at = _NOW - timedelta(days=10)
    pr = _pr(
        user_id, state="merged", created_offset_days=15, first_review_at=old_review_at
    )
    result = _run(user_id, [pr])
    assert result.review_velocity is None


# ---------------------------------------------------------------------------
# weekly_throughput
# ---------------------------------------------------------------------------


def test_weekly_throughput_counts_merged_in_window() -> None:
    user_id = uuid.uuid4()
    prs = [
        _pr(user_id, state="merged", merged_at=_NOW - timedelta(days=3)),
        _pr(user_id, state="merged", merged_at=_NOW - timedelta(days=3)),
        _pr(user_id, state="merged", merged_at=_NOW - timedelta(days=10)),  # outside
        _pr(user_id, state="open"),
    ]
    result = _run(user_id, prs)
    assert result.weekly_throughput == 2


# ---------------------------------------------------------------------------
# review_ratio
# ---------------------------------------------------------------------------


def test_review_ratio_none_when_no_prs() -> None:
    result = _run(uuid.uuid4(), [])
    assert result.review_ratio is None


def test_review_ratio_zero_when_no_reviews() -> None:
    user_id = uuid.uuid4()
    result = _run(user_id, [_pr(user_id), _pr(user_id)])
    assert result.review_ratio == pytest.approx(0.0)


def test_review_ratio_calculates_fraction() -> None:
    user_id = uuid.uuid4()
    reviewed = _pr(user_id, first_review_at=_NOW - timedelta(hours=2))
    unreviewed = _pr(user_id)
    result = _run(user_id, [reviewed, unreviewed])
    assert result.review_ratio == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Route test
# ---------------------------------------------------------------------------


def test_pr_dashboard_route_returns_200() -> None:
    user_id = uuid.uuid4()
    prs = [_pr(user_id, state="merged", merged_at=_NOW - timedelta(days=2))]
    service = PRMetricsService(pr_repo=FakePRRepo(prs))  # type: ignore[arg-type]
    app = create_app()
    app.dependency_overrides[get_pr_metrics_service] = lambda: service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(user_id)
    )
    with TestClient(app) as c:
        response = c.get("/api/v1/metrics/pr-dashboard")
    assert response.status_code == 200
    body = response.json()
    assert "stale_pr_count" in body
    assert "weekly_throughput" in body
    assert body["weekly_throughput"] == 1
