"""OrgSyncService tests — org-level PR sync over tracked repositories."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devflow_api.core.errors import AppError
from devflow_api.core.models.github_installation import GitHubInstallation
from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.pull_request import PullRequest
from devflow_api.core.models.pull_request_review import PullRequestReview
from devflow_api.core.models.repository import Repository
from devflow_api.core.models.sync_run import SyncRun
from devflow_api.core.services.org_sync import OrgSyncService

_NOW = datetime.now(UTC)


# ===========================================================================
# Fakes
# ===========================================================================


class FakeOrgRepo:
    def __init__(self) -> None:
        self._members: dict[tuple[uuid.UUID, uuid.UUID], OrganizationMember] = {}

    def seed_member(self, org_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
        self._members[(org_id, user_id)] = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role=role,
            joined_at=_NOW,
        )

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return self._members.get((org_id, user_id))


class FakeInstallationRepo:
    def __init__(self) -> None:
        self.rows: list[GitHubInstallation] = []

    async def list_for_org(self, org_id: uuid.UUID) -> list[GitHubInstallation]:
        return [r for r in self.rows if r.organization_id == org_id]


class FakeRepositoryRepo:
    def __init__(self) -> None:
        self.rows: list[Repository] = []

    async def list_tracked_for_installation(
        self, github_installation_id: uuid.UUID
    ) -> list[Repository]:
        return [
            r
            for r in self.rows
            if r.github_installation_id == github_installation_id and r.tracked
        ]

    async def set_last_synced_at(
        self, repo: Repository, last_synced_at: datetime
    ) -> Repository:
        repo.last_synced_at = last_synced_at
        return repo


class FakePRRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, int], PullRequest] = {}

    async def upsert(self, **kwargs: Any) -> PullRequest:
        key = (kwargs["repository_id"], kwargs["github_pr_id"])
        pr = PullRequest(
            id=self.rows[key].id if key in self.rows else uuid.uuid4(),
            first_review_at=(
                self.rows[key].first_review_at if key in self.rows else None
            ),
            created_at=_NOW,
            updated_at=_NOW,
            **kwargs,
        )
        self.rows[key] = pr
        return pr

    async def set_first_review_at(
        self, pr: PullRequest, first_review_at: datetime
    ) -> PullRequest:
        if pr.first_review_at is None:
            pr.first_review_at = first_review_at
        return pr

    @property
    def prs(self) -> list[PullRequest]:
        return list(self.rows.values())


class FakeReviewRepo:
    def __init__(self) -> None:
        self.rows: list[PullRequestReview] = []

    async def upsert(self, **kwargs: Any) -> PullRequestReview:
        review = PullRequestReview(
            id=uuid.uuid4(), created_at=_NOW, updated_at=_NOW, **kwargs
        )
        self.rows.append(review)
        return review


class FakeSyncRunRepo:
    def __init__(self) -> None:
        self.runs: list[SyncRun] = []

    async def create(
        self, *, organization_id: uuid.UUID, triggered_by: uuid.UUID | None
    ) -> SyncRun:
        run = SyncRun(
            id=uuid.uuid4(),
            organization_id=organization_id,
            triggered_by=triggered_by,
            status="running",
            repos_synced=0,
            prs_synced=0,
            reviews_synced=0,
            started_at=_NOW,
            created_at=_NOW,
            updated_at=_NOW,
        )
        self.runs.append(run)
        return run

    async def complete(
        self,
        run: SyncRun,
        *,
        repos_synced: int,
        prs_synced: int,
        reviews_synced: int,
    ) -> SyncRun:
        run.status = "completed"
        run.repos_synced = repos_synced
        run.prs_synced = prs_synced
        run.reviews_synced = reviews_synced
        run.finished_at = datetime.now(UTC)
        return run

    async def fail(self, run: SyncRun, *, error_message: str) -> SyncRun:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = datetime.now(UTC)
        return run

    async def list_for_org(
        self, org_id: uuid.UUID, *, limit: int = 20
    ) -> list[SyncRun]:
        return [r for r in self.runs if r.organization_id == org_id][:limit]


class FakeApiClient:
    def __init__(
        self,
        pulls_by_repo: dict[str, list[dict[str, Any]]] | None = None,
        reviews: list[dict[str, Any]] | None = None,
    ) -> None:
        self.pulls_by_repo = pulls_by_repo or {}
        self.reviews = reviews or []
        self.pulls_calls: list[str] = []
        self.raise_on_pulls = False

    async def list_repo_pulls(
        self, token: str, owner: str, repo: str, **_: object
    ) -> list[dict[str, Any]]:
        if self.raise_on_pulls:
            raise RuntimeError("github unavailable")
        full_name = f"{owner}/{repo}"
        self.pulls_calls.append(full_name)
        return self.pulls_by_repo.get(full_name, [])

    async def list_pr_reviews(
        self, token: str, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        return self.reviews


class FakeTokenProvider:
    async def get_token(self, installation_id: int) -> str:
        return "ghs_test"


# ===========================================================================
# Fixtures / builders
# ===========================================================================


ORG_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()
MEMBER_ID = uuid.uuid4()


def _pull(
    pr_id: int,
    number: int,
    *,
    merged: bool = False,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": pr_id,
        "number": number,
        "title": f"PR {number}",
        "user": {"login": "octocat"},
        "state": "closed" if merged else "open",
        "created_at": "2026-06-01T10:00:00Z",
        "updated_at": (updated_at or _NOW).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merged_at": "2026-06-02T10:00:00Z" if merged else None,
        "closed_at": "2026-06-02T10:00:00Z" if merged else None,
        "html_url": f"https://github.com/octo-org/api/pull/{number}",
    }


class Env:
    def __init__(self) -> None:
        self.org_repo = FakeOrgRepo()
        self.org_repo.seed_member(ORG_ID, ADMIN_ID, "owner")
        self.org_repo.seed_member(ORG_ID, MEMBER_ID, "member")
        self.installation_repo = FakeInstallationRepo()
        self.repository_repo = FakeRepositoryRepo()
        self.pr_repo = FakePRRepo()
        self.review_repo = FakeReviewRepo()
        self.sync_run_repo = FakeSyncRunRepo()

    def add_installation(self, suspended: bool = False) -> GitHubInstallation:
        row = GitHubInstallation(
            id=uuid.uuid4(),
            organization_id=ORG_ID,
            installation_id=42,
            account_login="octo-org",
            account_type="Organization",
            account_avatar_url=None,
            repository_selection="selected",
            suspended_at=_NOW if suspended else None,
            created_by=ADMIN_ID,
            created_at=_NOW,
            updated_at=_NOW,
        )
        self.installation_repo.rows.append(row)
        return row

    def add_repo(
        self,
        installation: GitHubInstallation,
        full_name: str = "octo-org/api",
        *,
        tracked: bool = True,
        last_synced_at: datetime | None = None,
    ) -> Repository:
        repo = Repository(
            id=uuid.uuid4(),
            organization_id=ORG_ID,
            github_installation_id=installation.id,
            github_repo_id=1000 + len(self.repository_repo.rows),
            full_name=full_name,
            private=False,
            default_branch="main",
            tracked=tracked,
            last_synced_at=last_synced_at,
            created_at=_NOW,
            updated_at=_NOW,
        )
        self.repository_repo.rows.append(repo)
        return repo

    def service(self, api: FakeApiClient) -> OrgSyncService:
        return OrgSyncService(
            installation_repo=self.installation_repo,  # type: ignore[arg-type]
            repository_repo=self.repository_repo,  # type: ignore[arg-type]
            pr_repo=self.pr_repo,  # type: ignore[arg-type]
            review_repo=self.review_repo,  # type: ignore[arg-type]
            sync_run_repo=self.sync_run_repo,  # type: ignore[arg-type]
            org_repo=self.org_repo,  # type: ignore[arg-type]
            api_client=api,  # type: ignore[arg-type]
            token_provider=FakeTokenProvider(),  # type: ignore[arg-type]
        )


# ===========================================================================
# Tests
# ===========================================================================


async def test_sync_requires_admin() -> None:
    env = Env()
    service = env.service(FakeApiClient())
    with pytest.raises(AppError) as exc_info:
        await service.sync(org_id=ORG_ID, user_id=MEMBER_ID)
    assert exc_info.value.status_code == 403


async def test_sync_without_installation_returns_400() -> None:
    env = Env()
    service = env.service(FakeApiClient())
    with pytest.raises(AppError) as exc_info:
        await service.sync(org_id=ORG_ID, user_id=ADMIN_ID)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "no_installation"


async def test_sync_upserts_prs_and_reviews() -> None:
    env = Env()
    installation = env.add_installation()
    repo = env.add_repo(installation)
    api = FakeApiClient(
        pulls_by_repo={
            "octo-org/api": [
                _pull(9001, 1, merged=True),
                _pull(9002, 2),
            ]
        },
        reviews=[
            {
                "id": 501,
                "user": {"login": "reviewer1"},
                "state": "APPROVED",
                "submitted_at": "2026-06-01T12:00:00Z",
            }
        ],
    )
    service = env.service(api)

    result = await service.sync(org_id=ORG_ID, user_id=ADMIN_ID)

    assert result.prs_synced == 2
    assert result.reviews_synced == 2  # one review per PR
    prs = {pr.github_pr_id: pr for pr in env.pr_repo.prs}
    assert prs[9001].state == "merged"
    assert prs[9002].state == "open"
    assert prs[9001].repository_id == repo.id
    assert prs[9001].first_review_at is not None
    assert repo.last_synced_at is not None
    assert env.sync_run_repo.runs[0].status == "completed"
    assert env.sync_run_repo.runs[0].repos_synced == 1


async def test_sync_skips_untracked_repos() -> None:
    env = Env()
    installation = env.add_installation()
    env.add_repo(installation, "octo-org/ignored", tracked=False)
    api = FakeApiClient(pulls_by_repo={"octo-org/ignored": [_pull(9001, 1)]})
    service = env.service(api)

    result = await service.sync(org_id=ORG_ID, user_id=ADMIN_ID)

    assert result.prs_synced == 0
    assert api.pulls_calls == []


async def test_sync_skips_suspended_installations() -> None:
    env = Env()
    installation = env.add_installation(suspended=True)
    env.add_repo(installation)
    api = FakeApiClient(pulls_by_repo={"octo-org/api": [_pull(9001, 1)]})
    service = env.service(api)

    result = await service.sync(org_id=ORG_ID, user_id=ADMIN_ID)

    assert result.prs_synced == 0
    assert api.pulls_calls == []


async def test_sync_stops_at_prs_older_than_last_sync() -> None:
    env = Env()
    installation = env.add_installation()
    env.add_repo(installation, last_synced_at=_NOW - timedelta(days=1))
    api = FakeApiClient(
        pulls_by_repo={
            "octo-org/api": [
                _pull(9002, 2, updated_at=_NOW),  # fresh — synced
                _pull(9001, 1, updated_at=_NOW - timedelta(days=3)),  # stale — stop
            ]
        }
    )
    service = env.service(api)

    result = await service.sync(org_id=ORG_ID, user_id=ADMIN_ID)

    assert result.prs_synced == 1
    assert [pr.github_pr_id for pr in env.pr_repo.prs] == [9002]


async def test_sync_failure_marks_run_failed() -> None:
    env = Env()
    installation = env.add_installation()
    env.add_repo(installation)
    api = FakeApiClient()
    api.raise_on_pulls = True
    service = env.service(api)

    with pytest.raises(RuntimeError):
        await service.sync(org_id=ORG_ID, user_id=ADMIN_ID)

    run = env.sync_run_repo.runs[0]
    assert run.status == "failed"
    assert run.error_message is not None


async def test_list_runs_requires_membership() -> None:
    env = Env()
    service = env.service(FakeApiClient())
    with pytest.raises(AppError) as exc_info:
        await service.list_runs(org_id=ORG_ID, user_id=uuid.uuid4())
    assert exc_info.value.status_code == 403


async def test_list_runs_returns_runs_for_member() -> None:
    env = Env()
    await env.sync_run_repo.create(organization_id=ORG_ID, triggered_by=ADMIN_ID)
    service = env.service(FakeApiClient())
    runs = await service.list_runs(org_id=ORG_ID, user_id=MEMBER_ID)
    assert len(runs) == 1
