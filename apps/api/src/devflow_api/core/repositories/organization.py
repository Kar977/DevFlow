"""Organization repository — database access for Organization and OrganizationMember."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.organization import Organization
from devflow_api.core.models.organization_member import OrganizationMember


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        slug: str,
        description: str | None,
        created_by: uuid.UUID,
    ) -> Organization:
        org = Organization(
            name=name, slug=slug, description=description, created_by=created_by
        )
        self._session.add(org)
        await self._session.flush()
        return org

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        stmt = select(Organization).where(
            Organization.id == org_id, Organization.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(
            Organization.slug == slug, Organization.deleted_at.is_(None)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Organization]:
        stmt = (
            select(Organization)
            .join(OrganizationMember, OrganizationMember.org_id == Organization.id)
            .where(
                OrganizationMember.user_id == user_id,
                Organization.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        org: Organization,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Organization:
        if name is not None:
            org.name = name
        if description is not None:
            org.description = description
        await self._session.flush()
        return org

    async def soft_delete(self, org: Organization, deleted_at: datetime) -> None:
        # Mark deleted rather than removing the row, so projects/tasks/work
        # sessions belonging to the organization are preserved. The slug is
        # rewritten so a new organization can reuse it (the unique index on
        # slug is not aware of deleted_at).
        org.deleted_at = deleted_at
        org.slug = f"{org.slug}-deleted-{uuid.uuid4().hex[:8]}"
        await self._session.flush()

    async def add_member(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
    ) -> OrganizationMember:
        member = OrganizationMember(org_id=org_id, user_id=user_id, role=role)
        self._session.add(member)
        await self._session.flush()
        return member

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        stmt = select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_members(self, org_id: uuid.UUID) -> list[OrganizationMember]:
        stmt = select(OrganizationMember).where(OrganizationMember.org_id == org_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def remove_member(self, member: OrganizationMember) -> None:
        await self._session.delete(member)
        await self._session.flush()
