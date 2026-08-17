"""PullRequest repository — org/repository-scoped access to the PR aggregate."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.pull_request_review import PullRequestReview
from devflow_api.core.models.repository import Repository


class PullRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        repository_id: uuid.UUID,
        github_pr_id: int,
        number: int,
        title: str,
        author_login: str,
        state: str,
        created_at_github: datetime,
        merged_at: datetime | None,
        closed_at: datetime | None,
        html_url: str,
        last_synced_at: datetime,
    ) -> PullRequest:
        stmt = (
            insert(PullRequest)
            .values(
                repository_id=repository_id,
                github_pr_id=github_pr_id,
                number=number,
                title=title,
                author_login=author_login,
                state=state,
                created_at_github=created_at_github,
                merged_at=merged_at,
                closed_at=closed_at,
                html_url=html_url,
                last_synced_at=last_synced_at,
            )
            .on_conflict_do_update(
                constraint="uq_pull_requests_repo_pr",
                set_={
                    "number": number,
                    "title": title,
                    "author_login": author_login,
                    "state": state,
                    "created_at_github": created_at_github,
                    "merged_at": merged_at,
                    "closed_at": closed_at,
                    "html_url": html_url,
                    "last_synced_at": last_synced_at,
                },
            )
            .returning(PullRequest)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def set_first_review_at(
        self, pr: PullRequest, first_review_at: datetime
    ) -> PullRequest:
        if pr.first_review_at is None:
            pr.first_review_at = first_review_at
            await self._session.flush()
        return pr

    async def get_by_id_for_org(
        self, pr_id: uuid.UUID, org_id: uuid.UUID
    ) -> PullRequest | None:
        stmt = (
            select(PullRequest)
            .join(Repository, PullRequest.repository_id == Repository.id)
            .where(
                PullRequest.id == pr_id,
                Repository.organization_id == org_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_org(
        self,
        org_id: uuid.UUID,
        *,
        repository_id: uuid.UUID | None = None,
        state: str | None = None,
        author_login: str | None = None,
        sort: str = "newest",
        limit: int = 50,
        offset: int = 0,
    ) -> list[PullRequest]:
        stmt = (
            select(PullRequest)
            .join(Repository, PullRequest.repository_id == Repository.id)
            .where(Repository.organization_id == org_id)
        )
        if repository_id is not None:
            stmt = stmt.where(PullRequest.repository_id == repository_id)
        if state is not None:
            stmt = stmt.where(PullRequest.state == state)
        if author_login is not None:
            stmt = stmt.where(PullRequest.author_login == author_login)
        order = (
            PullRequest.created_at_github.asc()
            if sort == "oldest"
            else PullRequest.created_at_github.desc()
        )
        stmt = stmt.order_by(order, PullRequest.id).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_org(
        self,
        org_id: uuid.UUID,
        *,
        repository_id: uuid.UUID | None = None,
        state: str | None = None,
        author_login: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(PullRequest)
            .join(Repository, PullRequest.repository_id == Repository.id)
            .where(Repository.organization_id == org_id)
        )
        if repository_id is not None:
            stmt = stmt.where(PullRequest.repository_id == repository_id)
        if state is not None:
            stmt = stmt.where(PullRequest.state == state)
        if author_login is not None:
            stmt = stmt.where(PullRequest.author_login == author_login)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def list_reviews_for_pr(
        self, pull_request_id: uuid.UUID
    ) -> list[PullRequestReview]:
        stmt = (
            select(PullRequestReview)
            .where(PullRequestReview.pull_request_id == pull_request_id)
            .order_by(PullRequestReview.submitted_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
