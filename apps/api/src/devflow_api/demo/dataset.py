"""Pure construction of the demo dataset — no I/O, fully unit-testable.

Every function here takes a :class:`~devflow_api.demo.timeline.Timeline` and
a seeded ``random.Random`` and returns plain dict rows keyed by ORM column
name, ready for ``runner.py`` to either bulk-insert (large tables) or wrap
in an ORM object (small tables). Keeping this layer free of any database
access is what makes the *shape* of the dataset — counts, distributions, and
the handful of mandatory guarantees called out below — assertable in tests
without a running Postgres.

Content is deliberately fictional and plain-ASCII throughout (a wholly
invented "Acme" org, English task/PR titles) — partly for realism ("don't
name real companies or people"), partly because ``render_pdf`` only
supports latin-1 (see ``core/services/report_export.py``) and PR titles
flow into the ``pr_flow_weekly`` report's bottleneck lists.

Three things are guaranteed rather than left to chance, because each drives
a UI panel that would otherwise show up empty or flat:

* a non-zero, non-longest current completion streak for the demo user
  (:func:`_streak_booster_tasks`);
* all three project-health bands (healthy / at_risk / critical) appearing
  across the seeded projects (:func:`_apply_overdue_target`);
* at least one pull request with ``first_review_at`` inside the trailing
  7 days, so ``review_velocity`` isn't null (built into the recent PR batch
  in :func:`_build_pull_requests`).
"""

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from devflow_api.core.security import hash_password
from devflow_api.core.services.period import sprint_start_for
from devflow_api.demo.ids import det_uuid
from devflow_api.demo.timeline import (
    DEMO_TIMEZONE,
    HORIZON_WEEKS,
    SPRINT_LENGTH_DAYS,
    STALE_PR_THRESHOLD_DAYS,
    Timeline,
    creation_dates_over_weeks,
)

Row = dict[str, Any]

DEFAULT_SEED = 20260907
DEMO_USER_EMAIL = "demo@devflow.app"
DEMO_USER_PASSWORD = "DevFlowDemo2026!"  # noqa: S105 - public demo credential, not a secret

_STATUS_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("done", 60),
    ("in_progress", 11),
    ("review", 7),
    ("todo", 11),
    ("backlog", 7),
    ("cancelled", 4),
)
_PRIORITY_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("low", 20),
    ("medium", 45),
    ("high", 25),
    ("urgent", 10),
)
_ESTIMATES: tuple[int, ...] = (30, 60, 90, 120, 180, 240, 360, 480)

_TASK_TITLE_POOL: tuple[str, ...] = (
    "Fix flaky {area} test",
    "Add pagination to {area} list",
    "Refactor {area} service layer",
    "Improve {area} error messages",
    "Write integration tests for {area}",
    "Optimize {area} database queries",
    "Add caching to {area} endpoint",
    "Update {area} dependencies",
    "Fix timezone bug in {area}",
    "Add rate limiting to {area}",
    "Migrate {area} to new schema",
    "Add audit log to {area}",
    "Improve {area} loading state",
    "Fix memory leak in {area} worker",
    "Add retry logic to {area} client",
    "Document {area} API",
    "Add feature flag for {area}",
    "Clean up dead code in {area}",
    "Add monitoring to {area}",
    "Fix accessibility issue in {area}",
)
_TASK_AREAS: tuple[str, ...] = (
    "auth",
    "billing",
    "dashboard",
    "onboarding",
    "notifications",
    "search",
    "settings",
    "webhook",
    "export",
    "sync",
)

_PR_TITLE_POOL: tuple[str, ...] = (
    "Fix {area} race condition",
    "Add {area} pagination",
    "Refactor {area} module",
    "Improve {area} test coverage",
    "Add {area} rate limiting",
    "Fix {area} null pointer",
    "Update {area} dependency versions",
    "Add {area} caching layer",
    "Fix {area} timezone handling",
    "Add {area} audit logging",
)


def _pick_weighted(rng: random.Random, weights: tuple[tuple[str, int], ...]) -> str:
    options = [w[0] for w in weights]
    counts = [w[1] for w in weights]
    return rng.choices(options, weights=counts, k=1)[0]


def _task_title(rng: random.Random) -> str:
    template = rng.choice(_TASK_TITLE_POOL)
    return template.format(area=rng.choice(_TASK_AREAS))


def _pr_title(rng: random.Random, number: int) -> str:
    template = rng.choice(_PR_TITLE_POOL)
    return f"#{number} " + template.format(area=rng.choice(_TASK_AREAS))


# ---------------------------------------------------------------------------
# Static roster — fixed content, only dates/random fields vary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _UserSpec:
    key: str
    email: str
    full_name: str
    github_login: str | None


_USER_SPECS: tuple[_UserSpec, ...] = (
    _UserSpec("owner", DEMO_USER_EMAIL, "Demo Account", "demo-owner"),
    _UserSpec("admin", "priya.admin@devflow.app", "Priya Admin", "demo-priya"),
    _UserSpec("member1", "anna.dev@devflow.app", "Anna Chen", "demo-anna"),
    _UserSpec("member2", "bartek.dev@devflow.app", "Bartek Nowak", "demo-bartek"),
    _UserSpec("member3", "kasia.dev@devflow.app", "Kasia Wolski", "demo-kasia"),
    _UserSpec("member4", "marek.dev@devflow.app", "Marek Ito", "demo-marek"),
    _UserSpec("member5", "zofia.dev@devflow.app", "Zofia Reyes", None),
)


@dataclass(frozen=True)
class _RepoSpec:
    key: str
    full_name: str
    tracked: bool
    private: bool
    github_repo_id: int


_REPO_SPECS: tuple[_RepoSpec, ...] = (
    _RepoSpec("web-app", "acme-inc/web-app", True, True, 700_001),
    _RepoSpec("api-service", "acme-inc/api-service", True, True, 700_002),
    _RepoSpec("infra-terraform", "acme-inc/infra-terraform", True, True, 700_003),
    _RepoSpec("design-tokens", "acme-inc/design-tokens", False, False, 700_004),
)


@dataclass(frozen=True)
class _ProjectSpec:
    key: str
    org_key: str
    name: str
    status: str
    repo_key: str | None
    overdue_target: float  # 0..1 — post-processed so overdue_rate lands here
    density_recent: tuple[int, int]
    density_older: tuple[int, int]


_PROJECT_SPECS: tuple[_ProjectSpec, ...] = (
    _ProjectSpec(
        "web", "acme", "Web Platform", "active", "web-app", 0.06, (1, 2), (0, 1)
    ),
    _ProjectSpec(
        "api", "acme", "Payments API", "active", "api-service", 0.18, (1, 2), (0, 1)
    ),
    _ProjectSpec(
        "infra",
        "acme",
        "Infrastructure & DevOps",
        "active",
        "infra-terraform",
        0.34,
        (1, 1),
        (0, 1),
    ),
    _ProjectSpec(
        "blog", "side", "Engineering Blog", "active", None, 0.10, (0, 1), (0, 1)
    ),
)


@dataclass(frozen=True)
class ReportRequest:
    """A report to generate through the real `_do_generate_report` pipeline."""

    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID | None
    report_type: str
    project_id: uuid.UUID | None
    created_at: datetime


@dataclass
class DemoDataset:
    """Every row the seeder needs to write, plus report-generation requests."""

    demo_user_id: uuid.UUID = field(init=False)
    acme_org_id: uuid.UUID = field(init=False)
    api_project_id: uuid.UUID = field(init=False)

    users: list[Row] = field(default_factory=list)
    organizations: list[Row] = field(default_factory=list)
    organization_members: list[Row] = field(default_factory=list)
    organization_settings: list[Row] = field(default_factory=list)
    projects: list[Row] = field(default_factory=list)
    tasks: list[Row] = field(default_factory=list)
    task_status_changes: list[Row] = field(default_factory=list)
    work_sessions: list[Row] = field(default_factory=list)
    github_installations: list[Row] = field(default_factory=list)
    github_connections: list[Row] = field(default_factory=list)
    repositories: list[Row] = field(default_factory=list)
    sync_runs: list[Row] = field(default_factory=list)
    pull_requests: list[Row] = field(default_factory=list)
    pull_request_reviews: list[Row] = field(default_factory=list)
    report_requests: list[ReportRequest] = field(default_factory=list)
    failed_report: Row | None = None


# ---------------------------------------------------------------------------
# Users, organizations, settings, GitHub scaffolding, projects
# ---------------------------------------------------------------------------


def _build_users(timeline: Timeline) -> tuple[list[Row], dict[str, uuid.UUID]]:
    password_hash = hash_password(DEMO_USER_PASSWORD)
    created = timeline.now - timedelta(days=400)
    users: list[Row] = []
    ids: dict[str, uuid.UUID] = {}
    for spec in _USER_SPECS:
        user_id = det_uuid("user", spec.key)
        ids[spec.key] = user_id
        users.append(
            {
                "id": user_id,
                "email": spec.email,
                "hashed_password": password_hash,
                "full_name": spec.full_name,
                "avatar_url": None,
                "timezone": DEMO_TIMEZONE,
                "created_at": created,
                "updated_at": created,
            }
        )
    return users, ids


def _build_organizations_and_members(
    timeline: Timeline, user_ids: dict[str, uuid.UUID]
) -> tuple[list[Row], list[Row], dict[str, uuid.UUID]]:
    created = timeline.now - timedelta(days=395)
    owner = user_ids["owner"]
    org_ids = {
        "acme": det_uuid("org", "acme-product-team"),
        "side": det_uuid("org", "side-projects"),
    }
    organizations = [
        {
            "id": org_ids["acme"],
            "name": "Acme Product Team",
            "slug": "acme-product-team",
            "description": "Product engineering workspace for the Acme showcase.",
            "created_by": owner,
            "created_at": created,
            "updated_at": created,
            "deleted_at": None,
        },
        {
            "id": org_ids["side"],
            "name": "Side Projects",
            "slug": "side-projects",
            "description": None,
            "created_by": owner,
            "created_at": created,
            "updated_at": created,
            "deleted_at": None,
        },
    ]

    members: list[Row] = []
    join_base = created + timedelta(days=1)
    acme_roles = (
        ("owner", "owner"),
        ("admin", "admin"),
        ("member1", "member"),
        ("member2", "member"),
        ("member3", "member"),
        ("member4", "member"),
        ("member5", "member"),
    )
    for i, (key, role) in enumerate(acme_roles):
        members.append(
            {
                "id": det_uuid("member", "acme", key),
                "org_id": org_ids["acme"],
                "user_id": user_ids[key],
                "role": role,
                "joined_at": join_base + timedelta(days=i * 3),
            }
        )
    members.append(
        {
            "id": det_uuid("member", "side", "owner"),
            "org_id": org_ids["side"],
            "user_id": owner,
            "role": "owner",
            "joined_at": join_base,
        }
    )
    return organizations, members, org_ids


def _build_org_settings(timeline: Timeline, org_ids: dict[str, uuid.UUID]) -> list[Row]:
    return [
        {
            "id": det_uuid("org-settings", "acme"),
            "organization_id": org_ids["acme"],
            "sprint_length_days": SPRINT_LENGTH_DAYS,
            "sprint_anchor_date": timeline.sprint_anchor,
            "stale_pr_threshold_days": STALE_PR_THRESHOLD_DAYS,
        },
        {
            "id": det_uuid("org-settings", "side"),
            "organization_id": org_ids["side"],
            "sprint_length_days": 7,
            "sprint_anchor_date": timeline.current_monday - timedelta(days=364),
            "stale_pr_threshold_days": STALE_PR_THRESHOLD_DAYS,
        },
    ]


def _build_github_scaffolding(
    timeline: Timeline, org_ids: dict[str, uuid.UUID], user_ids: dict[str, uuid.UUID]
) -> tuple[list[Row], list[Row], list[Row], list[Row], dict[str, uuid.UUID]]:
    installation_id = det_uuid("gh-installation", "acme")
    installations = [
        {
            "id": installation_id,
            "organization_id": org_ids["acme"],
            "installation_id": 90_000_001,
            "account_login": "acme-inc",
            "account_type": "Organization",
            "account_avatar_url": None,
            "repository_selection": "selected",
            "suspended_at": None,
            "created_by": user_ids["owner"],
            "created_at": timeline.now - timedelta(days=390),
            "updated_at": timeline.now - timedelta(days=390),
        }
    ]

    repositories: list[Row] = []
    repo_ids: dict[str, uuid.UUID] = {}
    for spec in _REPO_SPECS:
        repo_id = det_uuid("repo", spec.full_name)
        repo_ids[spec.key] = repo_id
        repositories.append(
            {
                "id": repo_id,
                "organization_id": org_ids["acme"],
                "github_installation_id": installation_id,
                "github_repo_id": spec.github_repo_id,
                "full_name": spec.full_name,
                "private": spec.private,
                "default_branch": "main",
                "tracked": spec.tracked,
                "last_synced_at": (
                    timeline.now - timedelta(minutes=12) if spec.tracked else None
                ),
                "created_at": timeline.now - timedelta(days=388),
                "updated_at": timeline.now - timedelta(minutes=12),
            }
        )

    connections: list[Row] = []
    for user_spec in _USER_SPECS:
        if user_spec.github_login is None:
            continue
        connected = timeline.now - timedelta(days=380)
        connections.append(
            {
                "id": det_uuid("gh-connection", user_spec.key),
                "user_id": user_ids[user_spec.key],
                "github_user_id": str(1_000_000 + abs(hash(user_spec.key)) % 900_000),
                "github_login": user_spec.github_login,
                "access_token_encrypted": "seed-placeholder-not-a-token",
                "scopes": "read:user",
                "connected_at": connected,
                "updated_at": connected,
            }
        )

    sync_runs = [
        {
            "id": det_uuid("sync-run", "1"),
            "organization_id": org_ids["acme"],
            "triggered_by": user_ids["owner"],
            "status": "success",
            "repos_synced": 3,
            "prs_synced": 90,
            "reviews_synced": 140,
            "error_message": None,
            "started_at": timeline.now - timedelta(minutes=12),
            "finished_at": timeline.now - timedelta(minutes=11),
        },
        {
            "id": det_uuid("sync-run", "2"),
            "organization_id": org_ids["acme"],
            "triggered_by": user_ids["owner"],
            "status": "success",
            "repos_synced": 3,
            "prs_synced": 4,
            "reviews_synced": 6,
            "error_message": None,
            "started_at": timeline.now - timedelta(days=1),
            "finished_at": timeline.now - timedelta(days=1) + timedelta(minutes=2),
        },
        {
            "id": det_uuid("sync-run", "3"),
            "organization_id": org_ids["acme"],
            "triggered_by": user_ids["owner"],
            "status": "failed",
            "repos_synced": 0,
            "prs_synced": 0,
            "reviews_synced": 0,
            "error_message": "GitHub API rate limit exceeded",
            "started_at": timeline.now - timedelta(days=3),
            "finished_at": timeline.now - timedelta(days=3) + timedelta(minutes=1),
        },
    ]
    return installations, repositories, connections, sync_runs, repo_ids


def _build_projects(
    timeline: Timeline, org_ids: dict[str, uuid.UUID], user_ids: dict[str, uuid.UUID]
) -> tuple[list[Row], dict[str, uuid.UUID]]:
    created_base = timeline.now - timedelta(days=370)
    owner = user_ids["owner"]
    projects: list[Row] = []
    project_ids: dict[str, uuid.UUID] = {}
    for i, spec in enumerate(_PROJECT_SPECS):
        project_id = det_uuid("project", spec.key)
        project_ids[spec.key] = project_id
        repo_url = f"https://github.com/{spec.repo_key and ''}" if False else None
        if spec.repo_key is not None:
            full_name = next(r.full_name for r in _REPO_SPECS if r.key == spec.repo_key)
            repo_url = f"https://github.com/{full_name}"
        created = created_base + timedelta(days=i * 5)
        projects.append(
            {
                "id": project_id,
                "org_id": org_ids[spec.org_key],
                "name": spec.name,
                "description": f"{spec.name} - demo showcase project.",
                "status": spec.status,
                "github_repo_url": repo_url,
                "created_by": owner,
                "created_at": created,
                "updated_at": created,
            }
        )
    archived_id = det_uuid("project", "onboarding")
    project_ids["onboarding"] = archived_id
    projects.append(
        {
            "id": archived_id,
            "org_id": org_ids["acme"],
            "name": "Customer Onboarding",
            "description": "Wrapped-up onboarding revamp, kept for history.",
            "status": "archived",
            "github_repo_url": None,
            "created_by": owner,
            "created_at": timeline.now - timedelta(days=420),
            "updated_at": timeline.now - timedelta(days=200),
        }
    )
    return projects, project_ids


# ---------------------------------------------------------------------------
# Tasks, status-change history, work sessions
# ---------------------------------------------------------------------------


def _status_chain(
    status: str, created_at: datetime, end_at: datetime, rng: random.Random
) -> list[tuple[str | None, str, datetime]]:
    """Transition rows spanning task creation to *end_at*.

    ``end_at`` is used exactly for the row that reaches *status* — matching
    ``task.completed_at``/``task.updated_at`` exactly, which is what lets a
    "stuck task" reading equal its status_changes' last row, and a
    cycle-time pair equal the true dwell time. Intermediate stage
    boundaries are interpolated proportionally between creation and that
    endpoint, jittered so many tasks average out to plausible per-stage
    dwell times without every task taking an identical shape.
    """
    if status == "cancelled":
        return [(None, "backlog", created_at), ("backlog", "cancelled", end_at)]
    if status == "backlog":
        return [(None, "backlog", created_at)]

    depth = {"todo": 1, "in_progress": 2, "review": 3, "done": 4}[status]
    stage_names = ("todo", "in_progress", "review", "done")

    total_seconds = max((end_at - created_at).total_seconds(), 60.0)
    weights = (0.35, 0.25, 0.25, 0.15)
    jittered = [w * rng.uniform(0.7, 1.3) for w in weights]
    total_weight = sum(jittered)
    fractions = [w / total_weight for w in jittered]

    rows: list[tuple[str | None, str, datetime]] = [(None, "backlog", created_at)]
    acc = 0.0
    prev_status: str | None = "backlog"
    for i in range(depth):
        acc += fractions[i]
        moment = (
            end_at
            if i == depth - 1
            else min(created_at + timedelta(seconds=total_seconds * acc), end_at)
        )
        rows.append((prev_status, stage_names[i], moment))
        prev_status = stage_names[i]
    return rows


def _completed_delay_days(rng: random.Random) -> int:
    days = int(rng.lognormvariate(1.6, 0.7))
    return max(1, min(days, 60))


def _bump_after(moment: datetime, timeline: Timeline) -> datetime:
    """One hour after *moment*, clamped so it never exceeds "now".

    Used whenever a same-day draw for an end timestamp landed at or before
    its start timestamp — nudging it forward must not reintroduce a
    created-in-the-future row when *moment* is already within an hour of
    "now" (see the regression ``Timeline.daytime`` itself guards against).
    """
    return min(moment + timedelta(hours=1), timeline.now)


def _closed_session(
    started_at: datetime, minutes: int, timeline: Timeline
) -> tuple[datetime, datetime, int]:
    """``(started_at, ended_at, duration_seconds)`` for a *minutes*-long session.

    ``started_at`` can itself already equal "now" (see ``Timeline.daytime``'s
    same-day clamp) — clamping only ``ended_at`` in that case would produce
    a zero-duration session. Instead the whole session is pulled earlier so
    it keeps its full, realistic length and still never ends in the future.
    """
    ended_at = started_at + timedelta(minutes=minutes)
    if ended_at > timeline.now:
        started_at = timeline.now - timedelta(minutes=minutes)
        ended_at = timeline.now
    return started_at, ended_at, minutes * 60


def _generate_sessions_for_task(
    rng: random.Random,
    timeline: Timeline,
    *,
    task_id: uuid.UUID,
    task_key: str,
    user_id: uuid.UUID,
    estimate_minutes: int,
    created_at: datetime,
    completed_at: datetime,
) -> list[Row]:
    roll = rng.random()
    if roll < 0.45:
        ratio = rng.uniform(0.85, 1.15)
    elif roll < 0.75:
        ratio = rng.uniform(1.25, 2.2)
    else:
        ratio = rng.uniform(0.4, 0.75)
    total_minutes = max(5, round(estimate_minutes * ratio))

    span_days = max((completed_at.date() - created_at.date()).days, 0)
    session_count = rng.randint(1, min(4, span_days + 1))
    shares = [rng.random() + 0.2 for _ in range(session_count)]
    share_sum = sum(shares)

    sessions: list[Row] = []
    remaining_minutes = total_minutes
    for seq in range(session_count):
        minutes = max(5, round(total_minutes * shares[seq] / share_sum))
        # The `remaining_minutes` budget can already be exhausted by earlier
        # (ceiling-biased) shares — floor at 5 regardless, a zero-minute
        # session is a zero-duration row (started_at == ended_at), not a
        # merely-small one.
        minutes = max(min(minutes, 240, remaining_minutes), 5)
        remaining_minutes = max(remaining_minutes - minutes, 0)

        day_offset = rng.randint(0, span_days) if span_days else 0
        day = created_at.date() + timedelta(days=day_offset)
        started_at = timeline.daytime(day, rng, early_hour=8, late_hour=14)
        started_at, ended_at, duration_seconds = _closed_session(
            started_at, minutes, timeline
        )
        sessions.append(
            {
                "id": det_uuid("session", task_key, str(seq)),
                "task_id": task_id,
                "user_id": user_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": duration_seconds,
                "created_at": started_at,
            }
        )
    return sessions


def _generate_topup_sessions(
    rng: random.Random,
    timeline: Timeline,
    *,
    task_id: uuid.UUID,
    task_key: str,
    user_id: uuid.UUID,
) -> list[Row]:
    sessions: list[Row] = []
    for seq in range(rng.randint(1, 2)):
        day = timeline.now.date() - timedelta(days=rng.randint(0, 21))
        started_at = timeline.daytime(day, rng, early_hour=8, late_hour=14)
        minutes = rng.randint(30, 180)
        started_at, ended_at, duration_seconds = _closed_session(
            started_at, minutes, timeline
        )
        sessions.append(
            {
                "id": det_uuid("topup-session", task_key, str(seq)),
                "task_id": task_id,
                "user_id": user_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": duration_seconds,
                "created_at": started_at,
            }
        )
    return sessions


def _generate_regular_tasks(
    rng: random.Random,
    timeline: Timeline,
    *,
    project_key: str,
    project_id: uuid.UUID,
    creator_id: uuid.UUID,
    assignee_pool: list[uuid.UUID],
    sprint_anchor: date,
    sprint_length: int,
    creation_dates: list[date],
) -> tuple[list[Row], list[Row], list[Row]]:
    tasks: list[Row] = []
    status_changes: list[Row] = []
    sessions: list[Row] = []
    recent_cutoff = timeline.now.date() - timedelta(days=4 * sprint_length)

    for i, created_day in enumerate(creation_dates):
        task_id = det_uuid("task", project_key, str(i))
        status = _pick_weighted(rng, _STATUS_WEIGHTS)
        priority = _pick_weighted(rng, _PRIORITY_WEIGHTS)
        assignee_id = rng.choice(assignee_pool) if rng.random() > 0.04 else None
        changed_by = assignee_id or creator_id
        created_at = timeline.daytime(created_day, rng)
        estimate = rng.choice(_ESTIMATES) if rng.random() < 0.8 else None

        completed_at: datetime | None = None
        if status == "done":
            completed_day = min(
                created_day + timedelta(days=_completed_delay_days(rng)),
                timeline.now.date(),
            )
            completed_at = timeline.daytime(completed_day, rng)
            if completed_at <= created_at:
                completed_at = _bump_after(created_at, timeline)
            end_at = completed_at
        elif status == "cancelled":
            cancelled_day = min(
                created_day + timedelta(days=rng.randint(1, 15)), timeline.now.date()
            )
            end_at = timeline.daytime(cancelled_day, rng)
            if end_at <= created_at:
                end_at = _bump_after(created_at, timeline)
        else:
            total_available_hours = max(
                (timeline.now - created_at).total_seconds() / 3600, 1.0
            )
            if status in ("in_progress", "review") and rng.random() < 0.06:
                stuck_hours = rng.uniform(12, 25) * 24
                offset_hours = max(total_available_hours - stuck_hours, 1.0)
            else:
                cap_hours = min(total_available_hours, 12 * 24)
                offset_hours = rng.uniform(1, max(cap_hours, 1.0))
            end_at = min(created_at + timedelta(hours=offset_hours), timeline.now)

        sprint_start_date: date | None = None
        if created_day >= recent_cutoff and rng.random() < 0.75:
            sprint_start_date = sprint_start_for(
                sprint_anchor, sprint_length, created_day
            )

        tasks.append(
            {
                "id": task_id,
                "project_id": project_id,
                "title": _task_title(rng),
                "description": None,
                "status": status,
                "priority": priority,
                "estimate_minutes": estimate,
                "assignee_id": assignee_id,
                "due_date": None,
                "completed_at": completed_at,
                "github_pr_url": None,
                "created_by": creator_id,
                "sprint_start_date": sprint_start_date,
                "created_at": created_at,
                "updated_at": end_at,
            }
        )

        for seq, (from_status, to_status, changed_at) in enumerate(
            _status_chain(status, created_at, end_at, rng)
        ):
            status_changes.append(
                {
                    "id": det_uuid("status-change", project_key, str(i), str(seq)),
                    "task_id": task_id,
                    "from_status": from_status,
                    "to_status": to_status,
                    "changed_by": changed_by,
                    "changed_at": changed_at,
                }
            )

        if (
            status == "done"
            and assignee_id is not None
            and estimate
            and rng.random() < 0.9
            and completed_at is not None
        ):
            sessions.extend(
                _generate_sessions_for_task(
                    rng,
                    timeline,
                    task_id=task_id,
                    task_key=f"{project_key}-{i}",
                    user_id=assignee_id,
                    estimate_minutes=estimate,
                    created_at=created_at,
                    completed_at=completed_at,
                )
            )
        elif (
            status in ("in_progress", "review")
            and assignee_id is not None
            and rng.random() < 0.5
        ):
            sessions.extend(
                _generate_topup_sessions(
                    rng,
                    timeline,
                    task_id=task_id,
                    task_key=f"{project_key}-{i}",
                    user_id=assignee_id,
                )
            )

    # A handful of tasks already tagged for the *next* sprint, so the
    # forward-looking sprint filter isn't empty.
    next_sprint_start = sprint_start_for(
        sprint_anchor, sprint_length, timeline.now.date()
    ) + timedelta(days=sprint_length)
    for j in range(rng.randint(2, 3)):
        idx = len(creation_dates) + j
        task_id = det_uuid("task", project_key, str(idx))
        created_day = timeline.now.date() - timedelta(days=rng.randint(0, 3))
        created_at = timeline.daytime(created_day, rng)
        assignee_id = rng.choice(assignee_pool)
        status = "backlog" if rng.random() < 0.5 else "todo"
        end_at = (
            created_at
            if status == "backlog"
            else min(created_at + timedelta(hours=2), timeline.now)
        )
        tasks.append(
            {
                "id": task_id,
                "project_id": project_id,
                "title": _task_title(rng),
                "description": None,
                "status": status,
                "priority": _pick_weighted(rng, _PRIORITY_WEIGHTS),
                "estimate_minutes": (
                    rng.choice(_ESTIMATES) if rng.random() < 0.8 else None
                ),
                "assignee_id": assignee_id,
                "due_date": None,
                "completed_at": None,
                "github_pr_url": None,
                "created_by": creator_id,
                "sprint_start_date": next_sprint_start,
                "created_at": created_at,
                "updated_at": end_at,
            }
        )
        for seq, (from_status, to_status, changed_at) in enumerate(
            _status_chain(status, created_at, end_at, rng)
        ):
            status_changes.append(
                {
                    "id": det_uuid("status-change", project_key, str(idx), str(seq)),
                    "task_id": task_id,
                    "from_status": from_status,
                    "to_status": to_status,
                    "changed_by": assignee_id,
                    "changed_at": changed_at,
                }
            )

    return tasks, status_changes, sessions


def _generate_archived_tasks(
    rng: random.Random,
    timeline: Timeline,
    *,
    project_id: uuid.UUID,
    creator_id: uuid.UUID,
    assignee_pool: list[uuid.UUID],
) -> tuple[list[Row], list[Row]]:
    """A wound-down project: old tasks, all done or cancelled, no recent activity."""
    tasks: list[Row] = []
    status_changes: list[Row] = []
    for i in range(24):
        created_day = timeline.now.date() - timedelta(days=rng.randint(220, 400))
        status = "done" if rng.random() < 0.85 else "cancelled"
        assignee_id = rng.choice(assignee_pool)
        created_at = timeline.daytime(created_day, rng)
        end_day = created_day + timedelta(days=rng.randint(2, 20))
        end_at = timeline.daytime(min(end_day, timeline.now.date()), rng)
        if end_at <= created_at:
            end_at = _bump_after(created_at, timeline)
        task_id = det_uuid("task", "onboarding", str(i))
        tasks.append(
            {
                "id": task_id,
                "project_id": project_id,
                "title": _task_title(rng),
                "description": None,
                "status": status,
                "priority": _pick_weighted(rng, _PRIORITY_WEIGHTS),
                "estimate_minutes": (
                    rng.choice(_ESTIMATES) if rng.random() < 0.8 else None
                ),
                "assignee_id": assignee_id,
                "due_date": None,
                "completed_at": end_at if status == "done" else None,
                "github_pr_url": None,
                "created_by": creator_id,
                "sprint_start_date": None,
                "created_at": created_at,
                "updated_at": end_at,
            }
        )
        for seq, (from_status, to_status, changed_at) in enumerate(
            _status_chain(status, created_at, end_at, rng)
        ):
            status_changes.append(
                {
                    "id": det_uuid("status-change", "onboarding", str(i), str(seq)),
                    "task_id": task_id,
                    "from_status": from_status,
                    "to_status": to_status,
                    "changed_by": assignee_id,
                    "changed_at": changed_at,
                }
            )
    return tasks, status_changes


def _owner_overdue_booster(
    rng: random.Random, timeline: Timeline, project_id: uuid.UUID, owner_id: uuid.UUID
) -> tuple[list[Row], list[Row]]:
    """>=3 overdue, non-terminal tasks for the demo user — see OverdueTasksBanner."""
    tasks: list[Row] = []
    status_changes: list[Row] = []
    for n in range(3):
        task_id = det_uuid("booster", "owner-overdue", str(n))
        created_at = timeline.now - timedelta(days=30 + n * 5)
        due = timeline.now - timedelta(days=5 + n * 3)
        end_at = timeline.now - timedelta(days=2)
        tasks.append(
            {
                "id": task_id,
                "project_id": project_id,
                "title": f"Overdue follow-up #{n + 1}",
                "description": None,
                "status": "in_progress",
                "priority": "high",
                "estimate_minutes": 120,
                "assignee_id": owner_id,
                "due_date": due,
                "completed_at": None,
                "github_pr_url": None,
                "created_by": owner_id,
                "sprint_start_date": None,
                "created_at": created_at,
                "updated_at": end_at,
            }
        )
        for seq, (from_status, to_status, changed_at) in enumerate(
            _status_chain("in_progress", created_at, end_at, rng)
        ):
            status_changes.append(
                {
                    "id": det_uuid("booster-status", "owner-overdue", str(n), str(seq)),
                    "task_id": task_id,
                    "from_status": from_status,
                    "to_status": to_status,
                    "changed_by": owner_id,
                    "changed_at": changed_at,
                }
            )
    return tasks, status_changes


def _streak_and_overdue_booster(
    rng: random.Random,
    timeline: Timeline,
    *,
    project_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> tuple[list[Row], list[Row], list[Row]]:
    """Guarantees a non-zero current streak, distinct from the longest one.

    Six done tasks on each of the last six days give the demo user a
    current streak; a separate nine-day unbroken run about eight weeks back
    (with a gap before it) becomes the longest streak — see
    ``MetricsService.get_streaks``.
    """
    tasks: list[Row] = []
    status_changes: list[Row] = []
    sessions: list[Row] = []

    def add_run(group: str, days: list[date]) -> None:
        for n, day in enumerate(days):
            task_id = det_uuid("booster", group, str(n))
            created_at = timeline.daytime(day - timedelta(days=1), rng)
            completed_at = timeline.daytime(day, rng)
            tasks.append(
                {
                    "id": task_id,
                    "project_id": project_id,
                    "title": f"Daily sync notes #{n + 1} ({group})",
                    "description": None,
                    "status": "done",
                    "priority": "low",
                    "estimate_minutes": 30,
                    "assignee_id": owner_id,
                    "due_date": None,
                    "completed_at": completed_at,
                    "github_pr_url": None,
                    "created_by": owner_id,
                    "sprint_start_date": None,
                    "created_at": created_at,
                    "updated_at": completed_at,
                }
            )
            for seq, (from_status, to_status, changed_at) in enumerate(
                _status_chain("done", created_at, completed_at, rng)
            ):
                status_changes.append(
                    {
                        "id": det_uuid("booster-status", group, str(n), str(seq)),
                        "task_id": task_id,
                        "from_status": from_status,
                        "to_status": to_status,
                        "changed_by": owner_id,
                        "changed_at": changed_at,
                    }
                )
            started = completed_at - timedelta(minutes=25)
            sessions.append(
                {
                    "id": det_uuid("booster-session", group, str(n)),
                    "task_id": task_id,
                    "user_id": owner_id,
                    "started_at": started,
                    "ended_at": completed_at,
                    "duration_seconds": 25 * 60,
                    "created_at": started,
                }
            )

    add_run("streak-current", [timeline.days_ago(n) for n in range(5, -1, -1)])
    run_start = timeline.days_ago(60)
    add_run("streak-longest", [run_start + timedelta(days=n) for n in range(9)])

    return tasks, status_changes, sessions


def _apply_overdue_target(
    rng: random.Random, timeline: Timeline, tasks: list[Row], target_rate: float
) -> None:
    """Mutates *tasks* in place so ``overdue / total`` lands near *target_rate*.

    Skips tasks that already carry a ``due_date`` (set by a booster) so
    pre-seeded overdue tasks still count toward the total without being
    double-assigned or overwritten.
    """
    total = len(tasks)
    if total == 0:
        return
    desired_total_overdue = round(target_rate * total)
    already_overdue = sum(
        1
        for t in tasks
        if t["due_date"] is not None
        and t["due_date"] < timeline.now
        and t["status"] not in ("done", "cancelled")
    )
    need = max(desired_total_overdue - already_overdue, 0)

    eligible = [
        t
        for t in tasks
        if t["status"] not in ("done", "cancelled") and t["due_date"] is None
    ]
    rng.shuffle(eligible)
    for t in eligible[:need]:
        t["due_date"] = timeline.now - timedelta(days=rng.randint(1, 45))

    remaining = eligible[need:]
    for t in remaining[: max(1, len(remaining) // 6)]:
        t["due_date"] = timeline.now + timedelta(days=rng.randint(1, 21))


# ---------------------------------------------------------------------------
# Pull requests and reviews
# ---------------------------------------------------------------------------


def _lognormal_hours(
    rng: random.Random, *, median_hours: float, sigma: float, cap: float
) -> float:
    return min(rng.lognormvariate(math.log(median_hours), sigma), cap)


def _build_reviews_for_pr(
    rng: random.Random,
    pr_id: uuid.UUID,
    first_review_at: datetime,
    end_moment: datetime,
    author_login: str,
    logins: list[str],
    counter: int,
) -> tuple[list[Row], int]:
    reviewers = [login for login in logins if login != author_login] or list(logins)
    count = rng.randint(1, 3)
    rows: list[Row] = []
    moment = first_review_at
    for seq in range(count):
        state = _pick_weighted(
            rng, (("APPROVED", 70), ("CHANGES_REQUESTED", 20), ("COMMENTED", 10))
        )
        counter += 1
        rows.append(
            {
                "id": det_uuid("review", str(pr_id), str(seq)),
                "pull_request_id": pr_id,
                "github_review_id": 5_000_000 + counter,
                "reviewer_login": rng.choice(reviewers),
                "state": state,
                "submitted_at": moment,
            }
        )
        if seq < count - 1:
            gap_hours = rng.uniform(
                1, max((end_moment - moment).total_seconds() / 3600, 1)
            )
            moment = min(moment + timedelta(hours=gap_hours), end_moment)
    return rows, counter


def _build_historical_prs(
    rng: random.Random,
    timeline: Timeline,
    repo_ids: dict[str, uuid.UUID],
    logins: list[str],
) -> tuple[list[Row], list[Row], dict[str, int]]:
    prs: list[Row] = []
    reviews: list[Row] = []
    review_counter = 0
    repo_names = list(repo_ids.keys())
    per_repo_numbers = dict.fromkeys(repo_names, 0)

    dates = creation_dates_over_weeks(
        rng,
        timeline,
        weeks=HORIZON_WEEKS,
        recent_weeks=26,
        recent_per_week=(1, 2),
        older_per_week=(0, 1),
    )
    for created_day in dates:
        repo_full_name = rng.choice(repo_names)
        per_repo_numbers[repo_full_name] += 1
        number = per_repo_numbers[repo_full_name]
        repo_index = repo_names.index(repo_full_name) + 1
        github_pr_id = repo_index * 100_000 + number
        author = rng.choice(logins)
        created_at_github = timeline.daytime(
            created_day, rng, early_hour=7, late_hour=19
        )

        reviewed = rng.random() < 0.9
        first_review_at: datetime | None = None
        if reviewed:
            wait_hours = _lognormal_hours(rng, median_hours=6, sigma=1.0, cap=96)
            first_review_at = min(
                created_at_github + timedelta(hours=wait_hours), timeline.now
            )

        merged = rng.random() < (0.85 if reviewed else 0.5)
        base_for_close = first_review_at or created_at_github
        closed_moment = min(
            base_for_close + timedelta(hours=rng.uniform(2, 72)), timeline.now
        )
        if closed_moment <= created_at_github:
            closed_moment = _bump_after(created_at_github, timeline)

        pr_id = det_uuid("pr", repo_full_name, str(number))
        prs.append(
            {
                "id": pr_id,
                "repository_id": repo_ids[repo_full_name],
                "github_pr_id": github_pr_id,
                "number": number,
                "title": _pr_title(rng, number),
                "author_login": author,
                "state": "merged" if merged else "closed",
                "created_at_github": created_at_github,
                "updated_at_github": closed_moment,
                "merged_at": closed_moment if merged else None,
                "closed_at": closed_moment,
                "first_review_at": first_review_at,
                "html_url": f"https://github.com/{repo_full_name}/pull/{number}",
                "last_synced_at": timeline.now - timedelta(minutes=12),
            }
        )

        if reviewed and first_review_at is not None:
            review_rows, review_counter = _build_reviews_for_pr(
                rng,
                pr_id,
                first_review_at,
                closed_moment,
                author,
                logins,
                review_counter,
            )
            reviews.extend(review_rows)

    return prs, reviews, per_repo_numbers


def _build_recent_prs(
    rng: random.Random,
    timeline: Timeline,
    repo_ids: dict[str, uuid.UUID],
    logins: list[str],
    start_numbers: dict[str, int],
) -> tuple[list[Row], list[Row]]:
    """Hand-placed open/recent PRs so staleness, review-velocity and the
    dashboard's cohort (PRs opened in the current sprint) are never empty.
    """
    prs: list[Row] = []
    reviews: list[Row] = []
    review_counter = 100_000
    repo_names = list(repo_ids.keys())

    def make_pr(
        repo_full_name: str,
        created_at_github: datetime,
        updated_at_github: datetime,
        first_review_at: datetime | None,
    ) -> tuple[uuid.UUID, str, Row]:
        start_numbers[repo_full_name] += 1
        number = start_numbers[repo_full_name]
        repo_index = repo_names.index(repo_full_name) + 1
        github_pr_id = repo_index * 100_000 + number
        author = rng.choice(logins)
        pr_id = det_uuid("pr", repo_full_name, str(number))
        row: Row = {
            "id": pr_id,
            "repository_id": repo_ids[repo_full_name],
            "github_pr_id": github_pr_id,
            "number": number,
            "title": _pr_title(rng, number),
            "author_login": author,
            "state": "open",
            "created_at_github": created_at_github,
            "updated_at_github": updated_at_github,
            "merged_at": None,
            "closed_at": None,
            "first_review_at": first_review_at,
            "html_url": f"https://github.com/{repo_full_name}/pull/{number}",
            "last_synced_at": timeline.now - timedelta(minutes=12),
        }
        return pr_id, author, row

    # 6 open, healthy — recent, mostly (4/6) reviewed, one inside the
    # trailing 7 days so `review_velocity` is never null.
    for i in range(6):
        repo_full_name = rng.choice(repo_names)
        created_at = timeline.now - timedelta(hours=rng.uniform(24, 96))
        updated_at = created_at + (timeline.now - created_at) * rng.uniform(0.6, 1.0)
        reviewed = i < 4
        first_review = None
        if reviewed:
            first_review = created_at + (updated_at - created_at) * rng.uniform(
                0.3, 0.9
            )
        pr_id, author, row = make_pr(
            repo_full_name, created_at, updated_at, first_review
        )
        prs.append(row)
        if reviewed and first_review is not None:
            review_rows, review_counter = _build_reviews_for_pr(
                rng, pr_id, first_review, updated_at, author, logins, review_counter
            )
            reviews.extend(review_rows)

    # 3 open, stale and never reviewed.
    for _ in range(3):
        repo_full_name = rng.choice(repo_names)
        created_at = timeline.now - timedelta(hours=rng.uniform(288, 720))
        updated_at = created_at + (timeline.now - created_at) * rng.uniform(0.1, 0.5)
        _, _, row = make_pr(repo_full_name, created_at, updated_at, None)
        prs.append(row)

    # 2 open, stale despite a review a week-plus ago.
    for _ in range(2):
        repo_full_name = rng.choice(repo_names)
        created_at = timeline.now - timedelta(hours=rng.uniform(360, 840))
        first_review = timeline.now - timedelta(hours=rng.uniform(168, 216))
        pr_id, author, row = make_pr(
            repo_full_name, created_at, first_review, first_review
        )
        prs.append(row)
        review_rows, review_counter = _build_reviews_for_pr(
            rng, pr_id, first_review, timeline.now, author, logins, review_counter
        )
        reviews.extend(review_rows)

    return prs, reviews


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _build_reports(
    timeline: Timeline,
    demo_user_id: uuid.UUID,
    acme_org_id: uuid.UUID,
    api_project_id: uuid.UUID,
) -> tuple[list[ReportRequest], Row]:
    requests = [
        ReportRequest(
            id=det_uuid("report", "1"),
            user_id=demo_user_id,
            organization_id=None,
            report_type="weekly_summary",
            project_id=None,
            created_at=timeline.now - timedelta(hours=2),
        ),
        ReportRequest(
            id=det_uuid("report", "2"),
            user_id=demo_user_id,
            organization_id=None,
            report_type="productivity_overview",
            project_id=None,
            created_at=timeline.now - timedelta(days=1),
        ),
        ReportRequest(
            id=det_uuid("report", "3"),
            user_id=demo_user_id,
            organization_id=None,
            report_type="project_status",
            project_id=api_project_id,
            created_at=timeline.now - timedelta(days=3),
        ),
        ReportRequest(
            id=det_uuid("report", "4"),
            user_id=demo_user_id,
            organization_id=acme_org_id,
            report_type="pr_flow_weekly",
            project_id=None,
            created_at=timeline.now - timedelta(days=5),
        ),
    ]
    failed_report: Row = {
        "id": det_uuid("report", "5"),
        "user_id": demo_user_id,
        "organization_id": None,
        "type": "weekly_summary",
        "format": "json",
        "status": "failed",
        "payload": None,
        "error_message": "generation_failed",
        "generated_at": None,
        "created_at": timeline.now - timedelta(days=9),
    }
    return requests, failed_report


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def build_dataset(timeline: Timeline, seed: int = DEFAULT_SEED) -> DemoDataset:
    """Build the full, internally-consistent demo dataset for one seed run."""
    rng = random.Random(seed)
    dataset = DemoDataset()

    users, user_ids = _build_users(timeline)
    dataset.users = users
    dataset.demo_user_id = user_ids["owner"]

    organizations, members, org_ids = _build_organizations_and_members(
        timeline, user_ids
    )
    dataset.organizations = organizations
    dataset.organization_members = members
    dataset.acme_org_id = org_ids["acme"]

    dataset.organization_settings = _build_org_settings(timeline, org_ids)

    installations, repositories, connections, sync_runs, repo_ids_by_key = (
        _build_github_scaffolding(timeline, org_ids, user_ids)
    )
    dataset.github_installations = installations
    dataset.repositories = repositories
    dataset.github_connections = connections
    dataset.sync_runs = sync_runs

    projects, project_ids = _build_projects(timeline, org_ids, user_ids)
    dataset.projects = projects
    dataset.api_project_id = project_ids["api"]

    member_pool_by_org = {
        "acme": [
            user_ids[k]
            for k in (
                "owner",
                "admin",
                "member1",
                "member2",
                "member3",
                "member4",
                "member5",
            )
        ],
        "side": [user_ids["owner"]],
    }

    all_tasks: list[Row] = []
    all_status_changes: list[Row] = []
    all_sessions: list[Row] = []
    side_anchor = timeline.current_monday - timedelta(days=364)

    for spec in _PROJECT_SPECS:
        anchor = timeline.sprint_anchor if spec.org_key == "acme" else side_anchor
        length = SPRINT_LENGTH_DAYS if spec.org_key == "acme" else 7
        dates = creation_dates_over_weeks(
            rng,
            timeline,
            weeks=HORIZON_WEEKS,
            recent_weeks=26,
            recent_per_week=spec.density_recent,
            older_per_week=spec.density_older,
        )
        tasks, changes, sessions = _generate_regular_tasks(
            rng,
            timeline,
            project_key=spec.key,
            project_id=project_ids[spec.key],
            creator_id=user_ids["owner"],
            assignee_pool=member_pool_by_org[spec.org_key],
            sprint_anchor=anchor,
            sprint_length=length,
            creation_dates=dates,
        )
        if spec.key == "web":
            owner_overdue_tasks, owner_overdue_changes = _owner_overdue_booster(
                rng, timeline, project_ids["web"], user_ids["owner"]
            )
            tasks.extend(owner_overdue_tasks)
            changes.extend(owner_overdue_changes)
            streak_tasks, streak_changes, streak_sessions = _streak_and_overdue_booster(
                rng, timeline, project_id=project_ids["web"], owner_id=user_ids["owner"]
            )
            tasks.extend(streak_tasks)
            changes.extend(streak_changes)
            sessions.extend(streak_sessions)

        _apply_overdue_target(rng, timeline, tasks, spec.overdue_target)
        all_tasks.extend(tasks)
        all_status_changes.extend(changes)
        all_sessions.extend(sessions)

    archived_tasks, archived_changes = _generate_archived_tasks(
        rng,
        timeline,
        project_id=project_ids["onboarding"],
        creator_id=user_ids["owner"],
        assignee_pool=member_pool_by_org["acme"],
    )
    all_tasks.extend(archived_tasks)
    all_status_changes.extend(archived_changes)

    open_candidates = [
        t
        for t in all_tasks
        if t["assignee_id"] == user_ids["owner"] and t["status"] == "in_progress"
    ]
    if open_candidates:
        target = rng.choice(open_candidates)
        started = timeline.now - timedelta(minutes=25)
        all_sessions.append(
            {
                "id": det_uuid("open-session", "owner"),
                "task_id": target["id"],
                "user_id": user_ids["owner"],
                "started_at": started,
                "ended_at": None,
                "duration_seconds": None,
                "created_at": started,
            }
        )

    dataset.tasks = all_tasks
    dataset.task_status_changes = all_status_changes
    dataset.work_sessions = all_sessions

    tracked_repo_ids = {
        spec.full_name: repo_ids_by_key[spec.key]
        for spec in _REPO_SPECS
        if spec.tracked
    }
    logins = [
        spec.github_login for spec in _USER_SPECS if spec.github_login is not None
    ]

    historical_prs, historical_reviews, per_repo_numbers = _build_historical_prs(
        rng, timeline, tracked_repo_ids, logins
    )
    recent_prs, recent_reviews = _build_recent_prs(
        rng, timeline, tracked_repo_ids, logins, per_repo_numbers
    )
    dataset.pull_requests = historical_prs + recent_prs
    dataset.pull_request_reviews = historical_reviews + recent_reviews

    report_requests, failed_report = _build_reports(
        timeline, user_ids["owner"], org_ids["acme"], project_ids["api"]
    )
    dataset.report_requests = report_requests
    dataset.failed_report = failed_report

    return dataset
