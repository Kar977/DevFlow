"""Metrics routes — productivity dashboards over tasks and work sessions."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from devflow_api.core.schemas.metrics import (
    CompletionRateResponse,
    EstimationAccuracyResponse,
    PRDashboardMembersResponse,
    PRDashboardResponse,
    ProjectMetricsResponse,
    PRTrendsResponse,
    StreakResponse,
    SummaryResponse,
    TimeTrackingResponse,
    VelocityResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.metrics import MetricsService, get_metrics_service
from devflow_api.core.services.pr_metrics import (
    PRMetricsService,
    get_pr_metrics_service,
)

router = APIRouter()


@router.get("/summary", response_model=SummaryResponse, summary="Productivity summary")
async def get_summary(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: MetricsService = Depends(get_metrics_service),
) -> SummaryResponse:
    return await service.get_summary(
        user_id=subject.user_id, date_from=date_from, date_to=date_to
    )


@router.get("/velocity", response_model=VelocityResponse, summary="Task velocity")
async def get_velocity(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: MetricsService = Depends(get_metrics_service),
) -> VelocityResponse:
    return await service.get_velocity(
        user_id=subject.user_id, date_from=date_from, date_to=date_to
    )


@router.get(
    "/time-tracking",
    response_model=TimeTrackingResponse,
    summary="Daily active hours",
)
async def get_time_tracking(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: MetricsService = Depends(get_metrics_service),
) -> TimeTrackingResponse:
    return await service.get_time_tracking(
        user_id=subject.user_id, date_from=date_from, date_to=date_to
    )


@router.get(
    "/completion-rate",
    response_model=CompletionRateResponse,
    summary="Task completion rate",
)
async def get_completion_rate(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: MetricsService = Depends(get_metrics_service),
) -> CompletionRateResponse:
    return await service.get_completion_rate(
        user_id=subject.user_id, date_from=date_from, date_to=date_to
    )


@router.get(
    "/estimation-accuracy",
    response_model=EstimationAccuracyResponse,
    summary="Estimation accuracy",
)
async def get_estimation_accuracy(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: MetricsService = Depends(get_metrics_service),
) -> EstimationAccuracyResponse:
    return await service.get_estimation_accuracy(
        user_id=subject.user_id, date_from=date_from, date_to=date_to
    )


@router.get("/streaks", response_model=StreakResponse, summary="Activity streaks")
async def get_streaks(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: MetricsService = Depends(get_metrics_service),
) -> StreakResponse:
    return await service.get_streaks(user_id=subject.user_id)


@router.get(
    "/projects/{project_id}",
    response_model=ProjectMetricsResponse,
    summary="Project health metrics",
)
async def get_project_metrics(
    project_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: MetricsService = Depends(get_metrics_service),
) -> ProjectMetricsResponse:
    return await service.get_project_metrics(
        project_id=project_id, user_id=subject.user_id
    )


@router.get(
    "/pr-dashboard",
    response_model=PRDashboardResponse,
    summary="GitHub PR-flow KPI dashboard for an organization",
)
async def get_pr_dashboard(
    organization_id: uuid.UUID = Query(...),
    member_user_id: uuid.UUID | None = Query(default=None),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: PRMetricsService = Depends(get_pr_metrics_service),
) -> PRDashboardResponse:
    return await service.get_pr_dashboard(
        org_id=organization_id,
        user_id=subject.user_id,
        member_user_id=member_user_id,
    )


@router.get(
    "/pr-dashboard/members",
    response_model=PRDashboardMembersResponse,
    summary="Org members with GitHub logins for the PR dashboard filter",
)
async def get_pr_dashboard_members(
    organization_id: uuid.UUID = Query(...),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: PRMetricsService = Depends(get_pr_metrics_service),
) -> PRDashboardMembersResponse:
    return await service.list_members(org_id=organization_id, user_id=subject.user_id)


@router.get(
    "/pr-trends",
    response_model=PRTrendsResponse,
    summary="Weekly PR flow trends for an organization",
)
async def get_pr_trends(
    organization_id: uuid.UUID = Query(...),
    member_user_id: uuid.UUID | None = Query(default=None),
    weeks: int = Query(default=12, ge=1, le=52),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: PRMetricsService = Depends(get_pr_metrics_service),
) -> PRTrendsResponse:
    """Weekly-bucketed PR opened/merged counts and review-latency trend.

    ``opened`` is bucketed by ``created_at_github``; ``merged`` by
    ``merged_at`` (only merged PRs). ``avg_time_to_first_review_h`` is a
    cohort reading — the average review-wait of PRs *opened* in that week
    (not reviewed in that week) — so the most recent 1-2 weeks may look
    faster than they really are, since slow-to-review PRs in those weeks
    have not been reviewed yet.
    """
    return await service.get_pr_trends(
        org_id=organization_id,
        user_id=subject.user_id,
        member_user_id=member_user_id,
        weeks=weeks,
    )
