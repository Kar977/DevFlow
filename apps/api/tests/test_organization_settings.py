"""OrganizationSettings endpoint + service tests — cadence and stale threshold."""

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from devflow_api.core.models.organization_member import OrganizationMember
from devflow_api.core.models.organization_settings import (
    DEFAULT_SPRINT_LENGTH_DAYS,
    DEFAULT_STALE_PR_THRESHOLD_DAYS,
    OrganizationSettings,
)
from devflow_api.core.security import AuthenticatedSubject, get_current_subject
from devflow_api.core.services.organization_settings import (
    OrganizationSettingsService,
    get_organization_settings_service,
)
from devflow_api.core.unset import UNSET, Unset
from devflow_api.main import create_app

# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeOrganizationRepository:
    """Only the surface org_access.require_member/require_admin touch."""

    def __init__(self) -> None:
        self._members: dict[uuid.UUID, OrganizationMember] = {}

    def seed_member(self, org_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
        member = OrganizationMember(
            id=uuid.uuid4(),
            org_id=org_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(UTC),
        )
        self._members[member.id] = member

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        return next(
            (
                m
                for m in self._members.values()
                if m.org_id == org_id and m.user_id == user_id
            ),
            None,
        )


class FakeOrganizationSettingsRepository:
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, OrganizationSettings] = {}

    async def get_for_org(
        self, organization_id: uuid.UUID
    ) -> OrganizationSettings | None:
        return self._rows.get(organization_id)

    async def upsert_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        sprint_length_days: int | Unset = UNSET,
        sprint_anchor_date: date | None | Unset = UNSET,
        stale_pr_threshold_days: int | Unset = UNSET,
    ) -> OrganizationSettings:
        existing = self._rows.get(organization_id)
        if existing is None:
            existing = OrganizationSettings(
                id=uuid.uuid4(),
                organization_id=organization_id,
                sprint_length_days=DEFAULT_SPRINT_LENGTH_DAYS,
                stale_pr_threshold_days=DEFAULT_STALE_PR_THRESHOLD_DAYS,
            )
        if not isinstance(sprint_length_days, Unset):
            existing.sprint_length_days = sprint_length_days
        if not isinstance(sprint_anchor_date, Unset):
            existing.sprint_anchor_date = sprint_anchor_date
        if not isinstance(stale_pr_threshold_days, Unset):
            existing.stale_pr_threshold_days = stale_pr_threshold_days
        self._rows[organization_id] = existing
        return existing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def owner_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def member_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def outsider_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def org_repo(
    org_id: uuid.UUID, owner_id: uuid.UUID, member_id: uuid.UUID
) -> FakeOrganizationRepository:
    repo = FakeOrganizationRepository()
    repo.seed_member(org_id, owner_id, "owner")
    repo.seed_member(org_id, member_id, "member")
    return repo


@pytest.fixture()
def settings_repo() -> FakeOrganizationSettingsRepository:
    return FakeOrganizationSettingsRepository()


def _client(
    org_repo: FakeOrganizationRepository,
    settings_repo: FakeOrganizationSettingsRepository,
    caller_id: uuid.UUID,
) -> TestClient:
    app = create_app()

    def fake_service() -> OrganizationSettingsService:
        return OrganizationSettingsService(
            settings_repo=settings_repo,  # type: ignore[arg-type]
            org_repo=org_repo,  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_organization_settings_service] = fake_service
    app.dependency_overrides[get_current_subject] = lambda: AuthenticatedSubject(
        subject_id=str(caller_id)
    )
    return TestClient(app)


@pytest.fixture()
def owner_client(
    org_repo: FakeOrganizationRepository,
    settings_repo: FakeOrganizationSettingsRepository,
    owner_id: uuid.UUID,
) -> Iterator[TestClient]:
    with _client(org_repo, settings_repo, owner_id) as c:
        yield c


@pytest.fixture()
def member_client(
    org_repo: FakeOrganizationRepository,
    settings_repo: FakeOrganizationSettingsRepository,
    member_id: uuid.UUID,
) -> Iterator[TestClient]:
    with _client(org_repo, settings_repo, member_id) as c:
        yield c


@pytest.fixture()
def outsider_client(
    org_repo: FakeOrganizationRepository,
    settings_repo: FakeOrganizationSettingsRepository,
    outsider_id: uuid.UUID,
) -> Iterator[TestClient]:
    with _client(org_repo, settings_repo, outsider_id) as c:
        yield c


# ---------------------------------------------------------------------------
# GET — defaults when no row exists
# ---------------------------------------------------------------------------


def test_get_settings_returns_defaults_when_no_row(
    member_client: TestClient, org_id: uuid.UUID
) -> None:
    response = member_client.get(f"/api/v1/organizations/{org_id}/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["sprint_length_days"] == 14
    assert body["sprint_anchor_date"] is None
    assert body["stale_pr_threshold_days"] == 5


def test_get_settings_any_member_can_read(
    member_client: TestClient, org_id: uuid.UUID
) -> None:
    response = member_client.get(f"/api/v1/organizations/{org_id}/settings")
    assert response.status_code == 200


def test_get_settings_non_member_forbidden(
    outsider_client: TestClient, org_id: uuid.UUID
) -> None:
    response = outsider_client.get(f"/api/v1/organizations/{org_id}/settings")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# PATCH — admin only, persists and round-trips
# ---------------------------------------------------------------------------


def test_patch_settings_as_owner_persists(
    owner_client: TestClient, org_id: uuid.UUID
) -> None:
    response = owner_client.patch(
        f"/api/v1/organizations/{org_id}/settings",
        json={
            "sprint_length_days": 10,
            "sprint_anchor_date": "2026-08-05",
            "stale_pr_threshold_days": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sprint_length_days"] == 10
    assert body["sprint_anchor_date"] == "2026-08-05"
    assert body["stale_pr_threshold_days"] == 3

    get_response = owner_client.get(f"/api/v1/organizations/{org_id}/settings")
    assert get_response.json() == body


def test_patch_settings_as_plain_member_forbidden(
    member_client: TestClient, org_id: uuid.UUID
) -> None:
    response = member_client.patch(
        f"/api/v1/organizations/{org_id}/settings",
        json={
            "sprint_length_days": 10,
            "sprint_anchor_date": None,
            "stale_pr_threshold_days": 3,
        },
    )
    assert response.status_code == 403


def test_patch_settings_out_of_range_rejected(
    owner_client: TestClient, org_id: uuid.UUID
) -> None:
    response = owner_client.patch(
        f"/api/v1/organizations/{org_id}/settings",
        json={
            "sprint_length_days": 0,
            "sprint_anchor_date": None,
            "stale_pr_threshold_days": 3,
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# get_effective — internal read used by PRMetricsService
# ---------------------------------------------------------------------------


async def test_get_effective_returns_defaults_when_no_row(
    org_repo: FakeOrganizationRepository,
    settings_repo: FakeOrganizationSettingsRepository,
    org_id: uuid.UUID,
) -> None:
    svc = OrganizationSettingsService(
        settings_repo=settings_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
    )
    effective = await svc.get_effective(org_id)
    assert effective.sprint_length_days == 14
    assert effective.sprint_anchor_date is None
    assert effective.stale_pr_threshold_days == 5


async def test_get_effective_reflects_saved_row(
    org_repo: FakeOrganizationRepository,
    settings_repo: FakeOrganizationSettingsRepository,
    org_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> None:
    svc = OrganizationSettingsService(
        settings_repo=settings_repo,  # type: ignore[arg-type]
        org_repo=org_repo,  # type: ignore[arg-type]
    )
    await svc.update(
        org_id=org_id,
        user_id=owner_id,
        sprint_length_days=21,
        sprint_anchor_date=date(2026, 1, 5),
        stale_pr_threshold_days=7,
    )
    effective = await svc.get_effective(org_id)
    assert effective.sprint_length_days == 21
    assert effective.sprint_anchor_date == date(2026, 1, 5)
    assert effective.stale_pr_threshold_days == 7


# ---------------------------------------------------------------------------
# PATCH — partial update (each settings tab owns a subset of fields)
# ---------------------------------------------------------------------------


def test_patch_settings_partial_does_not_reset_omitted_fields(
    owner_client: TestClient, org_id: uuid.UUID
) -> None:
    owner_client.patch(
        f"/api/v1/organizations/{org_id}/settings",
        json={
            "sprint_length_days": 10,
            "sprint_anchor_date": "2026-08-05",
            "stale_pr_threshold_days": 3,
        },
    )
    # "Metryki" tab only owns stale_pr_threshold_days — a PATCH with just
    # that field must not clobber the cadence set above.
    response = owner_client.patch(
        f"/api/v1/organizations/{org_id}/settings",
        json={"stale_pr_threshold_days": 9},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stale_pr_threshold_days"] == 9
    assert body["sprint_length_days"] == 10
    assert body["sprint_anchor_date"] == "2026-08-05"


def test_patch_settings_partial_can_clear_anchor_date(
    owner_client: TestClient, org_id: uuid.UUID
) -> None:
    owner_client.patch(
        f"/api/v1/organizations/{org_id}/settings",
        json={
            "sprint_length_days": 10,
            "sprint_anchor_date": "2026-08-05",
            "stale_pr_threshold_days": 3,
        },
    )
    # Explicit null clears the anchor; omitting the key would leave it as-is
    # (see the "does not reset" test above) — this is the other half of
    # that null-vs-omitted distinction.
    response = owner_client.patch(
        f"/api/v1/organizations/{org_id}/settings",
        json={"sprint_anchor_date": None},
    )
    assert response.status_code == 200
    assert response.json()["sprint_anchor_date"] is None
    assert response.json()["sprint_length_days"] == 10


# ---------------------------------------------------------------------------
# GET /sprints
# ---------------------------------------------------------------------------


def test_list_sprints_member_sees_numbered_series(
    owner_client: TestClient, org_id: uuid.UUID
) -> None:
    # Anchor on today so the current sprint's boundaries are known exactly,
    # regardless of what "now" happens to be when the test runs.
    anchor = datetime.now(UTC).date()
    owner_client.patch(
        f"/api/v1/organizations/{org_id}/settings",
        json={
            "sprint_length_days": 14,
            "sprint_anchor_date": anchor.isoformat(),
            "stale_pr_threshold_days": 5,
        },
    )
    response = owner_client.get(
        f"/api/v1/organizations/{org_id}/sprints?back=1&forward=1"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 3
    starts = [anchor - timedelta(days=14), anchor, anchor + timedelta(days=14)]
    assert [s["start_date"] for s in data] == [d.isoformat() for d in starts]
    ends = [d + timedelta(days=13) for d in starts]
    assert [s["end_date"] for s in data] == [d.isoformat() for d in ends]
    current = [s for s in data if s["is_current"]]
    assert len(current) == 1
    assert current[0]["start_date"] == anchor.isoformat()


def test_list_sprints_non_member_forbidden(
    outsider_client: TestClient, org_id: uuid.UUID
) -> None:
    response = outsider_client.get(f"/api/v1/organizations/{org_id}/sprints")
    assert response.status_code == 403


def test_list_sprints_no_cadence_falls_back_to_unnumbered_weeks(
    member_client: TestClient, org_id: uuid.UUID
) -> None:
    response = member_client.get(
        f"/api/v1/organizations/{org_id}/sprints?back=0&forward=0"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["number"] is None


def test_list_sprints_out_of_range_query_rejected(
    member_client: TestClient, org_id: uuid.UUID
) -> None:
    response = member_client.get(f"/api/v1/organizations/{org_id}/sprints?back=-1")
    assert response.status_code == 422
