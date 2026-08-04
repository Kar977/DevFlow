"""Organization routes — workspace and membership management."""

import uuid

from fastapi import APIRouter, Depends, status

from devflow_api.core.schemas.organizations import (
    CreateOrganizationRequest,
    InviteMemberRequest,
    MemberListResponse,
    MemberResponse,
    OrganizationListResponse,
    OrganizationResponse,
    UpdateOrganizationRequest,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.organization import (
    OrganizationService,
    get_organization_service,
)

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
    return OrganizationListResponse(items=items, total=len(items))


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
    org = await service.update_organization(
        org_id=org_id,
        user_id=subject.user_id,
        name=body.name,
        description=body.description,
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
    return MemberListResponse(items=items, total=len(items))


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
