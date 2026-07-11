"""Organization service — workspace and membership management."""

import re
import uuid
from datetime import UTC, datetime

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.database import get_session
from devflow_api.core.errors import AppError
from devflow_api.core.models.organization import Organization
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.repositories.organization import OrganizationRepository
from devflow_api.core.repositories.user import UserRepository


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class OrganizationService:
    def __init__(
        self,
        org_repo: OrganizationRepository,
        user_repo: UserRepository,
    ) -> None:
        self._org_repo = org_repo
        self._user_repo = user_repo

    async def create_organization(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        description: str | None = None,
    ) -> Organization:
        slug = _slugify(name)
        existing = await self._org_repo.get_by_slug(slug)
        if existing:
            raise AppError(
                code="slug_conflict",
                message=f"An organization with slug '{slug}' already exists.",
                status_code=status.HTTP_409_CONFLICT,
            )
        org = await self._org_repo.create(
            name=name, slug=slug, description=description, created_by=user_id
        )
        await self._org_repo.add_member(org_id=org.id, user_id=user_id, role="owner")
        return org

    async def get_organization(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> Organization:
        org = await self._org_repo.get_by_id(org_id)
        if not org:
            raise AppError(
                code="not_found",
                message="Organization not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        member = await self._org_repo.get_member(org_id, user_id)
        if not member:
            raise AppError(
                code="forbidden",
                message="You are not a member of this organization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return org

    async def ensure_personal_organization(
        self,
        *,
        user_id: uuid.UUID,
        display_name: str,
    ) -> Organization:
        """Idempotently create (or return) the personal workspace for a user.

        Called on every login so that both new and existing accounts get an org
        without any extra UI step.  The slug ``personal-<user_id_hex[:12]>``
        is globally unique and will never collide with user-chosen slugs
        (which are derived from free-form names).
        """
        existing = await self._org_repo.list_for_user(user_id)
        if existing:
            return existing[0]

        name = f"{display_name}'s Workspace"
        slug = f"personal-{user_id.hex[:12]}"
        org = await self._org_repo.create(
            name=name, slug=slug, description=None, created_by=user_id
        )
        await self._org_repo.add_member(org_id=org.id, user_id=user_id, role="owner")
        return org

    async def list_user_organizations(self, user_id: uuid.UUID) -> list[Organization]:
        return await self._org_repo.list_for_user(user_id)

    async def update_organization(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Organization:
        org = await self.get_organization(org_id=org_id, user_id=user_id)
        member = await self._org_repo.get_member(org_id, user_id)
        if not member or member.role not in ("owner", "admin"):
            raise AppError(
                code="forbidden",
                message="Only owners and admins can update the organization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return await self._org_repo.update(org, name=name, description=description)

    async def delete_organization(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        org = await self.get_organization(org_id=org_id, user_id=user_id)
        member = await self._org_repo.get_member(org_id, user_id)
        if not member or member.role != "owner":
            raise AppError(
                code="forbidden",
                message="Only the owner can delete the organization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        await self._org_repo.soft_delete(org, deleted_at=datetime.now(UTC))

    async def invite_member(
        self,
        *,
        org_id: uuid.UUID,
        inviter_id: uuid.UUID,
        email: str,
        role: str,
    ) -> OrganizationMember:
        await self.get_organization(org_id=org_id, user_id=inviter_id)
        inviter_member = await self._org_repo.get_member(org_id, inviter_id)
        if not inviter_member or inviter_member.role not in ("owner", "admin"):
            raise AppError(
                code="forbidden",
                message="Only owners and admins can invite members.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if role == "owner" and inviter_member.role != "owner":
            raise AppError(
                code="forbidden",
                message="Only owners can grant the owner role.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        target_user = await self._user_repo.get_by_email(email)
        if not target_user:
            raise AppError(
                code="user_not_found",
                message="No user with that email address.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        existing = await self._org_repo.get_member(org_id, target_user.id)
        if existing:
            raise AppError(
                code="already_member",
                message="User is already a member of this organization.",
                status_code=status.HTTP_409_CONFLICT,
            )
        return await self._org_repo.add_member(
            org_id=org_id, user_id=target_user.id, role=role
        )

    async def list_members(
        self, *, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[OrganizationMember]:
        await self.get_organization(org_id=org_id, user_id=user_id)
        return await self._org_repo.list_members(org_id)

    async def remove_member(
        self,
        *,
        org_id: uuid.UUID,
        remover_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> None:
        await self.get_organization(org_id=org_id, user_id=remover_id)
        remover_member = await self._org_repo.get_member(org_id, remover_id)
        if not remover_member or remover_member.role not in ("owner", "admin"):
            raise AppError(
                code="forbidden",
                message="Only owners and admins can remove members.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        target_member = await self._org_repo.get_member(org_id, target_user_id)
        if not target_member:
            raise AppError(
                code="not_found",
                message="Member not found in this organization.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        if target_member.role == "owner":
            raise AppError(
                code="forbidden",
                message="Cannot remove the owner of an organization.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        await self._org_repo.remove_member(target_member)


def get_organization_service(
    session: AsyncSession = Depends(get_session),
) -> OrganizationService:
    return OrganizationService(
        org_repo=OrganizationRepository(session),
        user_repo=UserRepository(session),
    )
