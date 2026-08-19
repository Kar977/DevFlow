"""PRMetricsService — computes the GitHub PR-flow KPIs for an organization."""

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.cache import CacheBackend, get_cache
from devflow_api.core.config import get_settings
from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.organization_settings import (
    DEFAULT_SPRINT_LENGTH_DAYS,
    DEFAULT_STALE_PR_THRESHOLD_DAYS,
)
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
from devflow_api.core.services.org_access import require_member, resolve_target_member
from devflow_api.core.services.organization_settings import (
    OrganizationSettingsService,
    OrgMetricSettings,
    get_organization_settings_service,
)
from devflow_api.core.services.period import as_utc as _ensure_aware
from devflow_api.core.services.period import resolve_window
from devflow_api.core.services.period import sprint_window as _sprint_window
from devflow_api.core.services.period import week_start as _week_start

# Rolling window for `review_velocity` — deliberately independent of the
# dashboard's own selected period (sprint or custom range): it's a "how fast
# is review happening right now" snapshot, also reused unchanged by
# `MetricSnapshotService` for the weekly `review_velocity_h` history.
_VELOCITY_WINDOW_DAYS = 7
_DEFAULT_TRENDS_WEEKS = 12
_BOTTLENECK_LIMIT = 5
# `list_for_org` pages in batches of this size until exhausted, rather than a
# single `limit=1000` fetch — that used to silently truncate to the newest
# 1000 PRs by `created_at_github DESC`, which for `stale_pr_count` in
# particular drops exactly the oldest, most-stale PRs first: the ones the
# metric exists to surface.
_FETCH_BATCH_SIZE = 500


class PRMetricsService:
    def __init__(
        self,
        pr_repo: PullRequestRepository,
        org_repo: OrganizationRepository,
        conn_repo: GitHubConnectionRepository,
        user_repo: UserRepository,
        cache: CacheBackend | None = None,
        ttl_seconds: int = 60,
        settings_service: OrganizationSettingsService | None = None,
    ) -> None:
        self._pr_repo = pr_repo
        self._org_repo = org_repo
        self._conn_repo = conn_repo
        self._user_repo = user_repo
        self._cache = cache
        self._ttl_seconds = ttl_seconds
        # Optional: existing call sites (the `pr_flow_weekly` report, and
        # every test that constructs this service directly) don't pass one
        # and get today's hardcoded defaults via `_effective_settings` below
        # — identical to their pre-cadence-settings behaviour.
        self._settings_service = settings_service

    async def _effective_settings(self, org_id: uuid.UUID) -> OrgMetricSettings:
        if self._settings_service is not None:
            return await self._settings_service.get_effective(org_id)
        return OrgMetricSettings(
            sprint_length_days=DEFAULT_SPRINT_LENGTH_DAYS,
            sprint_anchor_date=None,
            stale_pr_threshold_days=DEFAULT_STALE_PR_THRESHOLD_DAYS,
        )

    async def _resolve_author_login(
        self,
        *,
        org_id: uuid.UUID,
        caller_id: uuid.UUID,
        member_user_id: uuid.UUID | None,
    ) -> str | None:
        """Authorize (caller + target both members of ``org_id``) and, when
        a target is given, resolve their GitHub login for the author filter.

        Subsumes the plain ``require_member(org_id, caller_id)`` check every
        call site used to do separately — ``resolve_target_member`` always
        performs it, even when ``member_user_id`` is ``None``.
        """
        target_id = await resolve_target_member(
            self._org_repo, org_id, caller_id, member_user_id
        )
        if member_user_id is None:
            return None
        conn = await self._conn_repo.get_by_user_id(target_id)
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

    async def _fetch_all_prs(
        self, org_id: uuid.UUID, author_login: str | None
    ) -> list[PullRequest]:
        """Every PR in scope, paging to exhaustion (see `_FETCH_BATCH_SIZE`)."""
        prs: list[PullRequest] = []
        offset = 0
        while True:
            batch = await self._pr_repo.list_for_org(
                org_id,
                author_login=author_login,
                limit=_FETCH_BATCH_SIZE,
                offset=offset,
            )
            prs.extend(batch)
            if len(batch) < _FETCH_BATCH_SIZE:
                break
            offset += _FETCH_BATCH_SIZE
        return prs

    async def get_pr_dashboard(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        member_user_id: uuid.UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> PRDashboardResponse:
        # Authorization must never be served from cache.
        author_login = await self._resolve_author_login(
            org_id=org_id, caller_id=user_id, member_user_id=member_user_id
        )
        settings = await self._effective_settings(org_id)
        # Cache key carries every input that changes the computed payload —
        # including the org's cadence settings, so an admin changing the
        # stale threshold or sprint cadence self-heals within one TTL
        # instead of serving stale numbers for up to `ttl_seconds`.
        key = (
            f"pr_metrics:dashboard:v2:{org_id}:{author_login or 'all'}:"
            f"{date_from}:{date_to}:{settings.stale_pr_threshold_days}:"
            f"{settings.sprint_length_days}:{settings.sprint_anchor_date}"
        )
        return await cached(
            self._cache,
            key,
            PRDashboardResponse,
            self._ttl_seconds,
            lambda: self._compute_pr_dashboard(
                org_id=org_id,
                author_login=author_login,
                settings=settings,
                date_from=date_from,
                date_to=date_to,
            ),
        )

    async def _compute_pr_dashboard(
        self,
        *,
        org_id: uuid.UUID,
        author_login: str | None,
        settings: OrgMetricSettings,
        date_from: date | None,
        date_to: date | None,
    ) -> PRDashboardResponse:
        now = datetime.now(UTC)
        if date_from is None and date_to is None:
            # No explicit range -> the org's current sprint (or the plain
            # Monday-anchored ISO week when no cadence is configured).
            start, end = _sprint_window(
                settings.sprint_anchor_date, settings.sprint_length_days, now
            )
        else:
            start, end = resolve_window(
                date_from, date_to, UTC, default_days=settings.sprint_length_days
            )
        prev_start = start - (end - start)

        prs = await self._fetch_all_prs(org_id, author_login)
        stale = _stale_prs(prs, now, threshold_days=settings.stale_pr_threshold_days)
        # Cohort = PRs *opened* in the selected window — same population
        # `get_pr_flow_report` and `/metrics/org-trends` already use for
        # `time_to_first_review`/`review_ratio`, so this dashboard no longer
        # disagrees with them (it used to average/ratio over the org's
        # entire history instead).
        cohort = [
            pr for pr in prs if start <= _ensure_aware(pr.created_at_github) < end
        ]
        prev_cohort = [
            pr
            for pr in prs
            if prev_start <= _ensure_aware(pr.created_at_github) < start
        ]
        awaiting = sum(
            1 for pr in prs if pr.state == "open" and pr.first_review_at is None
        )
        velocity_window_start = now - timedelta(days=_VELOCITY_WINDOW_DAYS)

        return PRDashboardResponse(
            period_from=start,
            period_to=end,
            stale_pr_count=len(stale),
            stale_threshold_days=settings.stale_pr_threshold_days,
            awaiting_first_review=awaiting,
            time_to_first_review=_round_or_none(_time_to_first_review(cohort)),
            time_to_first_review_prev=_round_or_none(
                _time_to_first_review(prev_cohort)
            ),
            review_velocity=_round_or_none(
                _review_velocity(prs, velocity_window_start, now)
            ),
            weekly_throughput=_weekly_throughput(prs, start, end),
            review_ratio=_round_or_none(_review_ratio(cohort)),
            cohort_size=len(cohort),
            reviewed_in_cohort=sum(
                1 for pr in cohort if pr.first_review_at is not None
            ),
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
        settings = await self._effective_settings(org_id)
        now = datetime.now(UTC)
        if date_from is None and date_to is None:
            # `end` stays "now" even when defaulting — only `start` comes
            # from the sprint boundary. Using the *sprint's own* end here
            # instead (which, mid-sprint, is in the future) would inflate
            # every "age since X" reading below, `stale_pr_count` first and
            # worst: a PR reviewed an hour ago would appear to have waited
            # until a sprint end that hasn't happened yet.
            start, _ = _sprint_window(
                settings.sprint_anchor_date, settings.sprint_length_days, now
            )
            end = now
        else:
            end = date_to or now
            start = date_from or (end - timedelta(days=settings.sprint_length_days))
        prs = await self._fetch_all_prs(org_id, None)

        stale = _stale_prs(prs, end, threshold_days=settings.stale_pr_threshold_days)
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
        author_login = await self._resolve_author_login(
            org_id=org_id, caller_id=user_id, member_user_id=member_user_id
        )

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
        prs = await self._fetch_all_prs(org_id, author_login)
        return _build_pr_trends(prs, now=datetime.now(UTC), weeks=weeks)


def _stale_prs(
    prs: list[PullRequest], now: datetime, *, threshold_days: int
) -> list[PullRequest]:
    """Open PRs with no activity more recently than *threshold_days* ago,
    oldest-active first.

    Activity is ``max(created_at_github, updated_at_github, first_review_at)``
    — a PR that was opened long ago but actively reviewed yesterday is not
    stale; one that's technically "young" but has sat untouched past the
    threshold is. ``created_at_github`` is always a safe floor (a PR is
    always at least as active as the moment it was opened) and covers rows
    synced before ``updated_at_github`` existed (nullable, no backfill).
    """
    threshold = timedelta(days=threshold_days)

    def _last_activity(pr: PullRequest) -> datetime:
        candidates = [_ensure_aware(pr.created_at_github)]
        if pr.updated_at_github is not None:
            candidates.append(_ensure_aware(pr.updated_at_github))
        if pr.first_review_at is not None:
            candidates.append(_ensure_aware(pr.first_review_at))
        return max(candidates)

    stale = [
        pr for pr in prs if pr.state == "open" and now - _last_activity(pr) > threshold
    ]
    stale.sort(key=_last_activity)
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
    settings_service: OrganizationSettingsService = Depends(
        get_organization_settings_service
    ),
) -> PRMetricsService:
    settings = get_settings()
    return PRMetricsService(
        pr_repo=PullRequestRepository(session),
        org_repo=OrganizationRepository(session),
        conn_repo=GitHubConnectionRepository(session),
        user_repo=UserRepository(session),
        cache=cache,
        ttl_seconds=settings.metrics_cache_ttl_seconds,
        settings_service=settings_service,
    )
