"""Organization routes — workspace and membership management."""

import uuid

from fastapi import APIRouter, Depends, Query, status

from devflow_api.core.schemas.organization_settings import (
    OrganizationSettingsResponse,
    SprintListResponse,
    UpdateOrganizationSettingsRequest,
)
from devflow_api.core.schemas.organizations import (
    CreateOrganizationRequest,
    InviteMemberRequest,
    MemberListResponse,
    MemberResponse,
    OrganizationListResponse,
    OrganizationResponse,
    UpdateMemberRoleRequest,
    UpdateOrganizationRequest,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.organization import (
    OrganizationService,
    get_organization_service,
)
from devflow_api.core.services.organization_settings import (
    OrganizationSettingsService,
    get_organization_settings_service,
)
from devflow_api.core.unset import UNSET

router = APIRouter()


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_organization(
    body: CreateOrganizationRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    org = await service.create_organization(
        user_id=subject.user_id,
        name=body.name,
        description=body.description,
    )
    return OrganizationResponse.model_validate(org)


@router.get(
    "",
    response_model=OrganizationListResponse,
    summary="List organizations for the current user",
)
async def list_organizations(
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationListResponse:
    orgs = await service.list_user_organizations(subject.user_id)
    items = [OrganizationResponse.model_validate(o) for o in orgs]
    return OrganizationListResponse(data=items)


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get a single organization",
)
async def get_organization(
    org_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    org = await service.get_organization(org_id=org_id, user_id=subject.user_id)
    return OrganizationResponse.model_validate(org)


@router.patch(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update an organization",
)
async def update_organization(
    org_id: uuid.UUID,
    body: UpdateOrganizationRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    fields = body.model_fields_set
    org = await service.update_organization(
        org_id=org_id,
        user_id=subject.user_id,
        name=body.name,
        description=body.description if "description" in fields else UNSET,
    )
    return OrganizationResponse.model_validate(org)


@router.delete(
    "/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an organization",
)
async def delete_organization(
    org_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> None:
    await service.delete_organization(org_id=org_id, user_id=subject.user_id)


@router.post(
    "/{org_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a user to the organization",
)
async def invite_member(
    org_id: uuid.UUID,
    body: InviteMemberRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> MemberResponse:
    return await service.invite_member(
        org_id=org_id,
        inviter_id=subject.user_id,
        email=body.email,
        role=body.role,
    )


@router.get(
    "/{org_id}/members",
    response_model=MemberListResponse,
    summary="List members of an organization",
)
async def list_members(
    org_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> MemberListResponse:
    items = await service.list_members(org_id=org_id, user_id=subject.user_id)
    return MemberListResponse(data=items)


@router.delete(
    "/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from an organization",
)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> None:
    await service.remove_member(
        org_id=org_id,
        remover_id=subject.user_id,
        target_user_id=user_id,
    )


@router.patch(
    "/{org_id}/members/{user_id}",
    response_model=MemberResponse,
    summary="Change a member's role",
)
async def update_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationService = Depends(get_organization_service),
) -> MemberResponse:
    return await service.update_member_role(
        org_id=org_id,
        actor_id=subject.user_id,
        target_user_id=user_id,
        role=body.role,
    )


@router.get(
    "/{org_id}/settings",
    response_model=OrganizationSettingsResponse,
    summary="Get the organization's metric cadence settings",
)
async def get_organization_settings(
    org_id: uuid.UUID,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationSettingsService = Depends(get_organization_settings_service),
) -> OrganizationSettingsResponse:
    settings = await service.get(org_id=org_id, user_id=subject.user_id)
    if settings is not None:
        return OrganizationSettingsResponse.model_validate(settings)
    # No row yet — surface the same defaults every metric computation falls
    # back to, so the settings tab shows what's actually in effect.
    effective = await service.get_effective(org_id)
    return OrganizationSettingsResponse(
        organization_id=org_id,
        sprint_length_days=effective.sprint_length_days,
        sprint_anchor_date=effective.sprint_anchor_date,
        stale_pr_threshold_days=effective.stale_pr_threshold_days,
    )


@router.patch(
    "/{org_id}/settings",
    response_model=OrganizationSettingsResponse,
    summary="Update the organization's metric cadence settings",
)
async def update_organization_settings(
    org_id: uuid.UUID,
    body: UpdateOrganizationSettingsRequest,
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationSettingsService = Depends(get_organization_settings_service),
) -> OrganizationSettingsResponse:
    fields = body.model_fields_set
    settings = await service.update(
        org_id=org_id,
        user_id=subject.user_id,
        sprint_length_days=body.sprint_length_days
        if "sprint_length_days" in fields and body.sprint_length_days is not None
        else UNSET,
        sprint_anchor_date=body.sprint_anchor_date
        if "sprint_anchor_date" in fields
        else UNSET,
        stale_pr_threshold_days=body.stale_pr_threshold_days
        if "stale_pr_threshold_days" in fields
        and body.stale_pr_threshold_days is not None
        else UNSET,
    )
    return OrganizationSettingsResponse.model_validate(settings)


@router.get(
    "/{org_id}/sprints",
    response_model=SprintListResponse,
    summary="List sprints around today under the organization's cadence",
)
async def list_organization_sprints(
    org_id: uuid.UUID,
    back: int = Query(default=6, ge=0, le=52),
    forward: int = Query(default=2, ge=0, le=52),
    subject: AuthenticatedSubject = Depends(get_current_subject),
    service: OrganizationSettingsService = Depends(get_organization_settings_service),
) -> SprintListResponse:
    sprints = await service.list_sprints(
        org_id=org_id, user_id=subject.user_id, back=back, forward=forward
    )
    return SprintListResponse(data=sprints)
