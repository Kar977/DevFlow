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


async def resolve_target_member(
    org_repo: OrganizationRepository,
    org_id: uuid.UUID,
    caller_id: uuid.UUID,
    target_user_id: uuid.UUID | None,
) -> uuid.UUID:
    """Authorize and resolve whose data a per-member metrics query should read.

    The caller must belong to ``org_id``. When ``target_user_id`` is given it
    must belong to the *same* org too — any member may view any other
    member's data (no owner/admin gate; a plain member viewing a teammate's
    productivity is not privileged the way editing org settings is), but
    never a stranger's. Returns the effective user id to compute for:
    ``target_user_id`` once authorized, otherwise ``caller_id`` itself.
    """
    await require_member(org_repo, org_id, caller_id)
    if target_user_id is None:
        return caller_id
    await require_member(org_repo, org_id, target_user_id)
    return target_user_id


async def resolve_metrics_subject(
    org_repo: OrganizationRepository,
    *,
    caller_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    member_user_id: uuid.UUID | None,
) -> uuid.UUID:
    """Entry point for user-scoped metrics endpoints that gained an optional
    per-member view (e.g. the Produktywność dashboard tab).

    Without ``member_user_id`` this is a no-op — the endpoint keeps behaving
    exactly as it did before the member filter existed, with no org lookup
    at all. ``member_user_id`` requires ``organization_id`` (422, there's no
    way to check same-org membership otherwise), then delegates to
    ``resolve_target_member`` for the actual authorization.
    """
    if member_user_id is None:
        return caller_id
    if organization_id is None:
        raise AppError(
            code="organization_id_required",
            message="organization_id is required when member_user_id is set.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return await resolve_target_member(
        org_repo, organization_id, caller_id, member_user_id
    )
