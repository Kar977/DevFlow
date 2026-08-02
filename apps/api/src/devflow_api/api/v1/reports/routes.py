"""Reports route handlers — request and retrieve productivity reports."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from devflow_api.core.schemas.pagination import PageMeta
from devflow_api.core.schemas.reports import (
    CreateReportRequest,
    ReportListResponse,
    ReportResponse,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.report import (
    ReportGenerator,
    ReportService,
    get_report_generator,
    get_report_service,
)

router = APIRouter()


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a new report",
)
async def create_report(
    body: CreateReportRequest,
    background_tasks: BackgroundTasks,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ReportService = Depends(get_report_service),
    generator: ReportGenerator = Depends(get_report_generator),
) -> ReportResponse:
    """Create a pending report and enqueue background generation."""
    report = await service.create_report(
        user_id=subject.user_id,
        report_type=body.type,
        fmt=body.format,
        project_id=body.project_id,
    )
    background_tasks.add_task(
        generator,
        report.id,
        user_id=subject.user_id,
        report_type=body.type,
        date_from=body.date_from,
        date_to=body.date_to,
        project_id=body.project_id,
    )
    return ReportResponse.model_validate(report)


@router.get(
    "",
    response_model=ReportListResponse,
    summary="List reports for the authenticated user",
)
async def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ReportService = Depends(get_report_service),
) -> ReportListResponse:
    reports, total = await service.list_reports(
        user_id=subject.user_id, limit=limit, offset=offset
    )
    items = [ReportResponse.model_validate(r) for r in reports]
    return ReportListResponse(
        data=items, meta=PageMeta(total=total, limit=limit, offset=offset)
    )


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get a specific report",
)
async def get_report(
    report_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ReportService = Depends(get_report_service),
) -> ReportResponse:
    report = await service.get_report(report_id=report_id, user_id=subject.user_id)
    return ReportResponse.model_validate(report)


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report",
)
async def delete_report(
    report_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: ReportService = Depends(get_report_service),
) -> None:
    await service.delete_report(report_id=report_id, user_id=subject.user_id)
