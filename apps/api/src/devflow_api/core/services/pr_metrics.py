"""PRMetricsService — computes the 5 GitHub PR-flow KPIs for an organization."""

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.cache import CacheBackend, get_cache
from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.repositories.github_connection import (
    GitHubConnectionRepository,
)
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.pull_request import PullRequestRepository
from devflow_api.core.repositories.user import UserRepository
from devflow_api.core.schemas.metrics import (
    PRDashboardMemberResponse,
    PRDashboardMembersResponse,
    PRDashboardResponse,
    PRFlowBottlenecksResponse,
    PRFlowReportResponse,
    PRTrendPointResponse,
    PRTrendsResponse,
    SlowReviewBottleneckResponse,
    StalePRBottleneckResponse,
)
from devflow_api.core.services.cache_aside import cached
from devflow_api.core.services.org_access import require_member

_STALE_THRESHOLD_DAYS = 5
_VELOCITY_WINDOW_DAYS = 7
_THROUGHPUT_WINDOW_DAYS = 7
_DEFAULT_TRENDS_WEEKS = 12
_BOTTLENECK_LIMIT = 5


class PRMetricsService:
    def __init__(
        self,
        pr_repo: PullRequestRepository,
        org_repo: OrganizationRepository,
        conn_repo: GitHubConnectionRepository,
        user_repo: UserRepository,
        cache: CacheBackend | None = None,
        ttl_seconds: int = 60,
    ) -> None:
        self._pr_repo = pr_repo
        self._org_repo = org_repo
        self._conn_repo = conn_repo
        self._user_repo = user_repo
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    async def _resolve_author_login(
        self, member_user_id: uuid.UUID | None
    ) -> str | None:
        if member_user_id is None:
            return None
        conn = await self._conn_repo.get_by_user_id(member_user_id)
        if conn is None:
            raise AppError(
                code="member_not_linked",
                message=(
                    "This member has not linked a GitHub account, "
                    "so their PRs cannot be attributed."
                ),
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return conn.github_login

    async def get_pr_dashboard(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        member_user_id: uuid.UUID | None = None,
    ) -> PRDashboardResponse:
        await require_member(self._org_repo, org_id, user_id)
        author_login = await self._resolve_author_login(member_user_id)
        prs = await self._pr_repo.list_for_org(
            org_id, author_login=author_login, limit=1000, offset=0
        )
        now = datetime.now(UTC)
        window_start = now - timedelta(days=_VELOCITY_WINDOW_DAYS)
        return PRDashboardResponse(
            stale_pr_count=len(_stale_prs(prs, now)),
            time_to_first_review=_time_to_first_review(prs),
            review_velocity=_review_velocity(prs, window_start, now),
            weekly_throughput=_weekly_throughput(prs, window_start, now),
            review_ratio=_review_ratio(prs),
        )

    async def get_pr_flow_report(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> PRFlowReportResponse:
        """Period-aware PR-flow KPIs + bottlenecks for the pr_flow_weekly report.

        Unlike ``get_pr_dashboard`` (always "now"), every window here is
        anchored to the explicit report period so the numbers match what the
        report claims to cover. See ``PRFlowReportResponse`` field docs for
        each KPI's exact window semantics.
        """
        await require_member(self._org_repo, org_id, user_id)
        end = date_to or datetime.now(UTC)
        start = date_from or (end - timedelta(days=_VELOCITY_WINDOW_DAYS))
        prs = await self._pr_repo.list_for_org(org_id, limit=1000, offset=0)

        stale = _stale_prs(prs, end)
        slow = _slowest_first_review(prs, limit=_BOTTLENECK_LIMIT)
        cohort = [
            pr for pr in prs if start <= _ensure_aware(pr.created_at_github) <= end
        ]

        return PRFlowReportResponse(
            period_from=start,
            period_to=end,
            stale_pr_count=len(stale),
            time_to_first_review_h=_time_to_first_review(cohort),
            review_velocity_h=_review_velocity(prs, start, end),
            throughput=_weekly_throughput(prs, start, end),
            review_ratio=_review_ratio(cohort),
            bottlenecks=PRFlowBottlenecksResponse(
                stale_open=[
                    StalePRBottleneckResponse(
                        number=pr.number,
                        title=pr.title,
                        author_login=pr.author_login,
                        html_url=pr.html_url,
                        age_days=round(
                            (end - _ensure_aware(pr.created_at_github)).total_seconds()
                            / 86400,
                            1,
                        ),
                    )
                    for pr in stale[:_BOTTLENECK_LIMIT]
                ],
                slowest_first_review=[
                    SlowReviewBottleneckResponse(
                        number=pr.number,
                        title=pr.title,
                        author_login=pr.author_login,
                        html_url=pr.html_url,
                        wait_hours=round(
                            (
                                _ensure_aware(pr.first_review_at)  # type: ignore[arg-type]
                                - _ensure_aware(pr.created_at_github)
                            ).total_seconds()
                            / 3600,
                            1,
                        ),
                    )
                    for pr in slow
                ],
            ),
        )

    async def list_members(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> PRDashboardMembersResponse:
        """Return org members with their GitHub logins for the metric filter."""
        await require_member(self._org_repo, org_id, user_id)
        members = await self._org_repo.list_members(org_id)
        items: list[PRDashboardMemberResponse] = []
        for member in members:
            user = await self._user_repo.get_by_id(member.user_id)
            conn = await self._conn_repo.get_by_user_id(member.user_id)
            display_name = ""
            if user is not None:
                display_name = user.full_name or user.email
            items.append(
                PRDashboardMemberResponse(
                    user_id=member.user_id,
                    display_name=display_name,
                    github_login=conn.github_login if conn else None,
                )
            )
        return PRDashboardMembersResponse(data=items)

    async def get_pr_trends(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        member_user_id: uuid.UUID | None = None,
        weeks: int = _DEFAULT_TRENDS_WEEKS,
    ) -> PRTrendsResponse:
        # Authorization must never be served from cache.
        await require_member(self._org_repo, org_id, user_id)
        author_login = await self._resolve_author_login(member_user_id)

        # Cache key is scoped by org_id + author_login, not user_id — the
        # payload is identical for every member, so keying by user would
        # produce N× cache entries for no benefit.
        key = f"pr_metrics:trends:v1:{org_id}:{author_login or 'all'}:{weeks}"
        return await cached(
            self._cache,
            key,
            PRTrendsResponse,
            self._ttl_seconds,
            lambda: self._compute_pr_trends(org_id, author_login, weeks),
        )

    async def _compute_pr_trends(
        self, org_id: uuid.UUID, author_login: str | None, weeks: int
    ) -> PRTrendsResponse:
        prs = await self._pr_repo.list_for_org(
            org_id, author_login=author_login, limit=1000, offset=0
        )
        return _build_pr_trends(prs, now=datetime.now(UTC), weeks=weeks)


def _stale_prs(prs: list[PullRequest], now: datetime) -> list[PullRequest]:
    """Open PRs older than the stale threshold, oldest first."""
    threshold = timedelta(days=_STALE_THRESHOLD_DAYS)

    def _age(pr: PullRequest) -> timedelta:
        return now - _ensure_aware(pr.created_at_github)

    stale = [pr for pr in prs if pr.state == "open" and _age(pr) > threshold]
    stale.sort(key=lambda pr: _ensure_aware(pr.created_at_github))
    return stale


def _time_to_first_review(prs: list[PullRequest]) -> float | None:
    total_hours = 0.0
    count = 0
    for pr in prs:
        if pr.first_review_at is not None:
            total_hours += (
                _ensure_aware(pr.first_review_at) - _ensure_aware(pr.created_at_github)
            ).total_seconds() / 3600
            count += 1
    return total_hours / count if count else None


def _review_velocity(
    prs: list[PullRequest], window_start: datetime, window_end: datetime
) -> float | None:
    total_hours = 0.0
    count = 0
    for pr in prs:
        first = pr.first_review_at
        if first is not None and window_start <= _ensure_aware(first) <= window_end:
            total_hours += (
                _ensure_aware(first) - _ensure_aware(pr.created_at_github)
            ).total_seconds() / 3600
            count += 1
    return total_hours / count if count else None


def _weekly_throughput(
    prs: list[PullRequest], window_start: datetime, window_end: datetime
) -> int:
    count = 0
    for pr in prs:
        if (
            pr.state == "merged"
            and pr.merged_at is not None
            and window_start <= _ensure_aware(pr.merged_at) <= window_end
        ):
            count += 1
    return count


def _review_ratio(prs: list[PullRequest]) -> float | None:
    if not prs:
        return None
    reviewed = sum(1 for pr in prs if pr.first_review_at is not None)
    return reviewed / len(prs)


def _slowest_first_review(prs: list[PullRequest], *, limit: int) -> list[PullRequest]:
    """PRs with a first review, sorted by review wait descending."""
    reviewed = [pr for pr in prs if pr.first_review_at is not None]
    reviewed.sort(
        key=lambda pr: (
            _ensure_aware(pr.first_review_at)  # type: ignore[arg-type]
            - _ensure_aware(pr.created_at_github)
        ),
        reverse=True,
    )
    return reviewed[:limit]


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _week_start(moment: datetime) -> date:
    """Monday of the ISO week containing *moment*, in UTC."""
    day = _ensure_aware(moment).date()
    return day - timedelta(days=day.weekday())


def _build_pr_trends(
    prs: list[PullRequest], *, now: datetime, weeks: int
) -> PRTrendsResponse:
    """Bucket PRs into *weeks* zero-filled ISO weeks ending at ``now``.

    ``opened`` buckets by ``created_at_github``; ``merged`` buckets by
    ``merged_at`` (mirrors ``_weekly_throughput``'s state check). The average
    review-wait per week is a *cohort* reading — the average wait of PRs
    opened in that week, not reviewed in that week — reusing
    ``_time_to_first_review`` per bucket.
    """
    last = _week_start(now)
    first = last - timedelta(weeks=weeks - 1)

    opened: dict[date, int] = {}
    merged: dict[date, int] = {}
    cohort: dict[date, list[PullRequest]] = {}
    cursor = first
    while cursor <= last:
        opened[cursor] = 0
        merged[cursor] = 0
        cohort[cursor] = []
        cursor += timedelta(days=7)

    for pr in prs:
        created_week = _week_start(pr.created_at_github)
        if created_week in opened:
            opened[created_week] += 1
            cohort[created_week].append(pr)
        if pr.state == "merged" and pr.merged_at is not None:
            merged_week = _week_start(pr.merged_at)
            if merged_week in merged:
                merged[merged_week] += 1

    weekly = [
        PRTrendPointResponse(
            week_start=day,
            opened=opened[day],
            merged=merged[day],
            avg_time_to_first_review_h=_round_or_none(
                _time_to_first_review(cohort[day])
            ),
        )
        for day in sorted(opened)
    ]
    return PRTrendsResponse(
        period_from=datetime.combine(first, datetime.min.time(), tzinfo=UTC),
        period_to=_ensure_aware(now),
        weekly=weekly,
    )


def _round_or_none(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def get_pr_metrics_service(
    session: AsyncSession = Depends(get_session),
    cache: CacheBackend = Depends(get_cache),
) -> PRMetricsService:
    settings = get_settings()
    return PRMetricsService(
        pr_repo=PullRequestRepository(session),
        org_repo=OrganizationRepository(session),
        conn_repo=GitHubConnectionRepository(session),
        user_repo=UserRepository(session),
        cache=cache,
        ttl_seconds=settings.metrics_cache_ttl_seconds,
    )
