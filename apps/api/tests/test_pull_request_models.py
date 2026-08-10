"""Schema-level tests for PullRequest and PullRequestReview models."""

from typing import cast

from sqlalchemy import BigInteger, Table

from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.pull_request_review import PullRequestReview

_PULL_REQUESTS_TABLE = cast("Table", PullRequest.__table__)
_PULL_REQUEST_REVIEWS_TABLE = cast("Table", PullRequestReview.__table__)


def test_pull_request_github_id_is_bigint() -> None:
    table = _PULL_REQUESTS_TABLE
    assert table.name == "pull_requests"
    assert isinstance(table.c.github_pr_id.type, BigInteger)


def test_pull_request_review_github_id_is_bigint() -> None:
    """Regression test for the int32 overflow that crashed every real sync.

    GitHub review ids now routinely exceed 2**31-1, so this column must stay
    BigInteger — narrowing it back to Integer reproduces the asyncpg
    OverflowError that rolled back an entire sync (see migration 0012).
    """
    table = _PULL_REQUEST_REVIEWS_TABLE
    assert table.name == "pull_request_reviews"
    assert isinstance(table.c.github_review_id.type, BigInteger)
