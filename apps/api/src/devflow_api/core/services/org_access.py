"""Shared organization access checks for org-scoped services."""

import uuid

from fastapi import status

from devflow_api.core.errors import AppError
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.repositories.organization import OrganizationRepository

_ADMIN_ROLES = ("owner", "admin")


async def require_member(
    org_repo: OrganizationRepository,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> OrganizationMember:
    """Return the membership row or raise 403 when the user is not a member."""
    member = await org_repo.get_member(org_id, user_id)
    if not member:
        raise AppError(
            code="forbidden",
            message="You are not a member of this organization.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return member


async def require_admin(
    org_repo: OrganizationRepository,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> OrganizationMember:
    """Return the membership row or raise 403 unless the user is owner/admin."""
    member = await require_member(org_repo, org_id, user_id)
    if member.role not in _ADMIN_ROLES:
        raise AppError(
            code="forbidden",
            message="Only owners and admins can perform this action.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return member
