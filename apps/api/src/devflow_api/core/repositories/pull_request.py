"""PullRequest repository — database access for the PR aggregate."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.pull_request_review import PullRequestReview


class PullRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        github_pr_id: int,
        github_repo_full_name: str,
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
                user_id=user_id,
                github_pr_id=github_pr_id,
                github_repo_full_name=github_repo_full_name,
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
                constraint="uq_pull_requests_user_pr",
                set_={
                    "github_repo_full_name": github_repo_full_name,
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
        row = result.scalar_one()
        return row

    async def set_first_review_at(
        self, pr: PullRequest, first_review_at: datetime
    ) -> PullRequest:
        if pr.first_review_at is None:
            pr.first_review_at = first_review_at
            await self._session.flush()
        return pr

    async def get_by_id(
        self, pr_id: uuid.UUID, user_id: uuid.UUID
    ) -> PullRequest | None:
        stmt = select(PullRequest).where(
            PullRequest.id == pr_id,
            PullRequest.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        state: str | None = None,
        author_login: str | None = None,
        repo: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PullRequest]:
        stmt = select(PullRequest).where(PullRequest.user_id == user_id)
        if state is not None:
            stmt = stmt.where(PullRequest.state == state)
        if author_login is not None:
            stmt = stmt.where(PullRequest.author_login == author_login)
        if repo is not None:
            stmt = stmt.where(PullRequest.github_repo_full_name == repo)
        stmt = (
            stmt.order_by(PullRequest.created_at_github.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(
        self,
        user_id: uuid.UUID,
        *,
        state: str | None = None,
        author_login: str | None = None,
        repo: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(PullRequest)
            .where(PullRequest.user_id == user_id)
        )
        if state is not None:
            stmt = stmt.where(PullRequest.state == state)
        if author_login is not None:
            stmt = stmt.where(PullRequest.author_login == author_login)
        if repo is not None:
            stmt = stmt.where(PullRequest.github_repo_full_name == repo)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def list_repos_for_user(self, user_id: uuid.UUID) -> list[str]:
        stmt = (
            select(PullRequest.github_repo_full_name)
            .where(PullRequest.user_id == user_id)
            .distinct()
            .order_by(PullRequest.github_repo_full_name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

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
