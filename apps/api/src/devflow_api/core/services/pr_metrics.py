"""PRMetricsService — computes the 5 GitHub PR-flow KPIs for an organization."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from devflow_api.core.services.org_access import require_member

_STALE_THRESHOLD_DAYS = 5
_VELOCITY_WINDOW_DAYS = 7
_THROUGHPUT_WINDOW_DAYS = 7


class PRMetricsService:
    def __init__(
        self,
        pr_repo: PullRequestRepository,
        org_repo: OrganizationRepository,
        conn_repo: GitHubConnectionRepository,
        user_repo: UserRepository,
    ) -> None:
        self._pr_repo = pr_repo
        self._org_repo = org_repo
        self._conn_repo = conn_repo
        self._user_repo = user_repo

    async def get_pr_dashboard(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        member_user_id: uuid.UUID | None = None,
    ) -> PRDashboardResponse:
        await require_member(self._org_repo, org_id, user_id)
        author_login: str | None = None
        if member_user_id is not None:
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
            author_login = conn.github_login
        prs = await self._pr_repo.list_for_org(
            org_id, author_login=author_login, limit=1000, offset=0
        )
        now = datetime.now(UTC)
        return PRDashboardResponse(
            stale_pr_count=_stale_pr_count(prs, now),
            time_to_first_review=_time_to_first_review(prs),
            review_velocity=_review_velocity(prs, now),
            weekly_throughput=_weekly_throughput(prs, now),
            review_ratio=_review_ratio(prs),
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
        return PRDashboardMembersResponse(items=items)


def _stale_pr_count(prs: list[PullRequest], now: datetime) -> int:
    threshold = timedelta(days=_STALE_THRESHOLD_DAYS)
    count = 0
    for pr in prs:
        age = now - _ensure_aware(pr.created_at_github)
        if pr.state == "open" and age > threshold:
            count += 1
    return count


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


def _review_velocity(prs: list[PullRequest], now: datetime) -> float | None:
    window_start = now - timedelta(days=_VELOCITY_WINDOW_DAYS)
    total_hours = 0.0
    count = 0
    for pr in prs:
        first = pr.first_review_at
        if first is not None and _ensure_aware(first) >= window_start:
            total_hours += (
                _ensure_aware(first) - _ensure_aware(pr.created_at_github)
            ).total_seconds() / 3600
            count += 1
    return total_hours / count if count else None


def _weekly_throughput(prs: list[PullRequest], now: datetime) -> int:
    window_start = now - timedelta(days=_THROUGHPUT_WINDOW_DAYS)
    count = 0
    for pr in prs:
        if (
            pr.state == "merged"
            and pr.merged_at is not None
            and _ensure_aware(pr.merged_at) >= window_start
        ):
            count += 1
    return count


def _review_ratio(prs: list[PullRequest]) -> float | None:
    if not prs:
        return None
    reviewed = sum(1 for pr in prs if pr.first_review_at is not None)
    return reviewed / len(prs)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def get_pr_metrics_service(
    session: AsyncSession = Depends(get_session),
) -> PRMetricsService:
    return PRMetricsService(
        pr_repo=PullRequestRepository(session),
        org_repo=OrganizationRepository(session),
        conn_repo=GitHubConnectionRepository(session),
        user_repo=UserRepository(session),
    )
