"""PullRequestReview repository — upsert and query PR reviews."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.core.models.pull_request_review import PullRequestReview


class PullRequestReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        pull_request_id: uuid.UUID,
        github_review_id: int,
        reviewer_login: str,
        state: str,
        submitted_at: datetime,
    ) -> PullRequestReview:
        stmt = (
            insert(PullRequestReview)
            .values(
                pull_request_id=pull_request_id,
                github_review_id=github_review_id,
                reviewer_login=reviewer_login,
                state=state,
                submitted_at=submitted_at,
            )
            .on_conflict_do_update(
                constraint="uq_pr_reviews_pr_review",
                set_={
                    "reviewer_login": reviewer_login,
                    "state": state,
                    "submitted_at": submitted_at,
                },
            )
            .returning(PullRequestReview)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_min_submitted_at(self, pull_request_id: uuid.UUID) -> datetime | None:
        from sqlalchemy import func

        stmt = select(func.min(PullRequestReview.submitted_at)).where(
            PullRequestReview.pull_request_id == pull_request_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
