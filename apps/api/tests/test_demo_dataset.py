"""Unit tests for the pure demo dataset builder (no database required).

These assert the mechanisms the demo plan calls out as mandatory — a
non-zero, non-longest streak; overdue tasks landing in all three project
health bands; a stale-PR count and review-velocity signal — rather than
exact row counts, since counts are randomized (with a fixed seed) and only
approximate by design.
"""

import uuid
from datetime import UTC, datetime, timedelta

from devflow_api.demo.dataset import DEFAULT_SEED, build_dataset
from devflow_api.demo.ids import det_uuid
from devflow_api.demo.timeline import Timeline

_capture_at = Timeline.at


def test_build_dataset_is_deterministic_given_the_same_timeline_and_seed() -> None:
    now = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    timeline = _capture_at(now)

    first = build_dataset(timeline, seed=DEFAULT_SEED)
    second = build_dataset(timeline, seed=DEFAULT_SEED)

    assert [t["id"] for t in first.tasks] == [t["id"] for t in second.tasks]
    first_pr_ids = [p["id"] for p in first.pull_requests]
    second_pr_ids = [p["id"] for p in second.pull_requests]
    assert first_pr_ids == second_pr_ids


def test_ids_are_stable_across_two_different_now_instants() -> None:
    """A task's id must not depend on when the seed ran — only on its logical
    identity — so bookmarked demo URLs survive a reseed.

    Exact set equality across the two runs isn't guaranteed (weekly density
    is randomized per run), but any given logical entity — "task 0 of the
    web project" — must always resolve to the same id.
    """
    timeline_a = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    timeline_b = _capture_at(datetime(2026, 12, 1, 8, 30, tzinfo=UTC))

    dataset_a = build_dataset(timeline_a)
    dataset_b = build_dataset(timeline_b)

    expected_id = det_uuid("task", "web", "0")
    assert expected_id in {t["id"] for t in dataset_a.tasks}
    assert expected_id in {t["id"] for t in dataset_b.tasks}


def test_all_tasks_are_assigned_except_a_small_fraction() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    assigned = sum(1 for t in dataset.tasks if t["assignee_id"] is not None)
    assert assigned / len(dataset.tasks) > 0.9


def test_demo_user_has_a_current_streak_shorter_than_the_longest() -> None:
    """MetricsService.get_streaks walks distinct completion dates for the
    user; the booster must produce a current run (last 6 days) that is
    shorter than a separate, older 9-day run."""
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    owner_done_dates = {
        t["completed_at"].date()
        for t in dataset.tasks
        if t["assignee_id"] == dataset.demo_user_id and t["status"] == "done"
    }

    def streak_length(anchor_days_ago: int) -> int:
        day = timeline.now.date() - timedelta(days=anchor_days_ago)
        length = 0
        while day in owner_done_dates:
            length += 1
            day -= timedelta(days=1)
        return length

    current = streak_length(0)
    assert current >= 6

    longest_run_start = timeline.now.date() - timedelta(days=60)
    longest = 0
    day = longest_run_start
    while day in owner_done_dates:
        longest += 1
        day += timedelta(days=1)
    assert longest >= 9
    assert longest != current


def test_project_health_bands_cover_healthy_at_risk_and_critical() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    by_project: dict[uuid.UUID, list[dict[str, object]]] = {}
    for task in dataset.tasks:
        by_project.setdefault(task["project_id"], []).append(task)

    def overdue_rate(tasks: list[dict[str, object]]) -> float:
        total = len(tasks)
        if total == 0:
            return 0.0
        overdue = 0
        for t in tasks:
            due_date = t["due_date"]
            if (
                isinstance(due_date, datetime)
                and due_date < timeline.now
                and t["status"] not in ("done", "cancelled")
            ):
                overdue += 1
        return overdue / total * 100

    rates = [overdue_rate(tasks) for tasks in by_project.values()]
    assert any(r < 10 for r in rates)
    assert any(10 <= r <= 30 for r in rates)
    assert any(r > 30 for r in rates)


def test_owner_has_at_least_three_overdue_tasks() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    overdue_owner_tasks = [
        t
        for t in dataset.tasks
        if t["assignee_id"] == dataset.demo_user_id
        and t["due_date"] is not None
        and t["due_date"] < timeline.now
        and t["status"] not in ("done", "cancelled")
    ]
    assert len(overdue_owner_tasks) >= 3


def test_exactly_one_open_work_session() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    open_sessions = [s for s in dataset.work_sessions if s["ended_at"] is None]
    assert len(open_sessions) == 1
    assert open_sessions[0]["user_id"] == dataset.demo_user_id


def test_no_work_session_started_after_it_ended() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    for session in dataset.work_sessions:
        if session["ended_at"] is not None:
            assert session["started_at"] < session["ended_at"]


def test_pull_requests_have_stale_and_recently_reviewed_ones() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    threshold = timedelta(days=5)

    def last_activity(pr: dict[str, object]) -> datetime:
        candidates: list[datetime] = []
        for key in ("created_at_github", "updated_at_github", "first_review_at"):
            value = pr[key]
            if isinstance(value, datetime):
                candidates.append(value)
        return max(candidates)

    stale = [
        pr
        for pr in dataset.pull_requests
        if pr["state"] == "open" and timeline.now - last_activity(pr) > threshold
    ]
    assert len(stale) >= 3

    recent_reviewed = []
    for pr in dataset.pull_requests:
        first_review_at = pr["first_review_at"]
        if not isinstance(first_review_at, datetime):
            continue
        if timeline.now - first_review_at <= timedelta(days=7):
            recent_reviewed.append(pr)
    assert recent_reviewed, "at least one PR must be reviewed within the last 7 days"


def test_pull_request_numbers_are_unique_per_repository() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    seen: dict[tuple[uuid.UUID, int], bool] = {}
    for pr in dataset.pull_requests:
        key = (pr["repository_id"], pr["number"])
        assert key not in seen
        seen[key] = True


def test_earliest_review_matches_pr_first_review_at() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    reviews_by_pr: dict[uuid.UUID, list[dict[str, object]]] = {}
    for review in dataset.pull_request_reviews:
        reviews_by_pr.setdefault(review["pull_request_id"], []).append(review)

    for pr in dataset.pull_requests:
        if pr["first_review_at"] is None:
            continue
        reviews = reviews_by_pr.get(pr["id"], [])
        assert reviews, f"PR {pr['id']} has first_review_at but no review rows"
        submitted_ats = [
            r["submitted_at"]
            for r in reviews
            if isinstance(r["submitted_at"], datetime)
        ]
        assert min(submitted_ats) == pr["first_review_at"]


def test_reports_never_seed_pending_or_generating_status() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    assert dataset.failed_report is not None
    assert dataset.failed_report["status"] == "failed"
    # report_requests go through the real generation pipeline, which sets
    # status itself — the dataset layer only carries the *request*, never a
    # status, so there's nothing here that could be "pending" at insert time.
    assert {r.report_type for r in dataset.report_requests} == {
        "weekly_summary",
        "productivity_overview",
        "project_status",
        "pr_flow_weekly",
    }


def test_pr_flow_weekly_report_request_carries_an_organization_id() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    pr_flow = next(
        r for r in dataset.report_requests if r.report_type == "pr_flow_weekly"
    )
    assert pr_flow.organization_id == dataset.acme_org_id


def test_sprint_start_dates_are_aligned_to_their_org_cadence() -> None:
    """A task's sprint_start_date must fall on an actual sprint boundary for
    its own organization — direct inserts bypass TaskService's validation
    (core/services/task.py:_validate_sprint_start_date), so a misaligned
    value wouldn't error, it would just silently never match a filter."""
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    org_id_by_project = {p["id"]: p["org_id"] for p in dataset.projects}
    side_anchor = timeline.current_monday - timedelta(days=364)
    side_org_id = next(
        o["id"] for o in dataset.organizations if o["id"] != dataset.acme_org_id
    )
    anchor_and_length_by_org = {
        dataset.acme_org_id: (timeline.sprint_anchor, 14),
        side_org_id: (side_anchor, 7),
    }

    aligned_count = 0
    for task in dataset.tasks:
        sprint_start_date = task["sprint_start_date"]
        if sprint_start_date is None:
            continue
        org_id = org_id_by_project[task["project_id"]]
        anchor, length = anchor_and_length_by_org[org_id]
        assert (sprint_start_date - anchor).days % length == 0
        aligned_count += 1

    assert aligned_count > 0


def test_no_pull_request_timestamps_are_in_the_future() -> None:
    """Regression test: week 0's weekday-biased offset used to be able to
    land later in the current week than "today", producing a
    created-in-the-future PR — which silently turned into a *negative*
    review-wait time the moment `first_review_at` was clamped to "now"
    (`min(created_at_github + wait, now)` with `created_at_github > now`).
    Caught by an end-to-end run against a real database — see
    `creation_dates_over_weeks` in timeline.py for the fix."""
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    for pr in dataset.pull_requests:
        assert pr["created_at_github"] <= timeline.now
        if pr["first_review_at"] is not None:
            assert pr["first_review_at"] >= pr["created_at_github"]
        if pr["merged_at"] is not None:
            assert pr["merged_at"] >= pr["created_at_github"]
        if pr["closed_at"] is not None:
            assert pr["closed_at"] >= pr["created_at_github"]


def test_no_task_timestamps_are_in_the_future() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    for task in dataset.tasks:
        assert task["created_at"] <= timeline.now
        assert task["updated_at"] <= timeline.now
        if task["completed_at"] is not None:
            assert task["completed_at"] >= task["created_at"]


def test_status_changes_are_chronologically_monotonic_per_task() -> None:
    """Regression test: a same-day clamp on one endpoint of a status chain
    (Timeline.daytime capping a "today" draw to "now") used to let an
    interpolated intermediate row land *after* the chain's own final row,
    a smaller instance of the same future-timestamp class of bug as the
    PR-review one above."""
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    # Grouping by task_id (without re-sorting) relies on rows for a given
    # task being appended together, in chain order, by the dataset builder.
    by_task: dict[uuid.UUID, list[dict[str, object]]] = {}
    for change in dataset.task_status_changes:
        by_task.setdefault(change["task_id"], []).append(change)

    for rows in by_task.values():
        timestamps = [
            r["changed_at"] for r in rows if isinstance(r["changed_at"], datetime)
        ]
        assert len(timestamps) == len(rows)
        assert timestamps == sorted(timestamps)
        for ts in timestamps:
            assert ts <= timeline.now


def test_no_work_session_ends_in_the_future() -> None:
    timeline = _capture_at(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    dataset = build_dataset(timeline)

    for session in dataset.work_sessions:
        assert session["started_at"] <= timeline.now
        if session["ended_at"] is not None:
            assert session["ended_at"] <= timeline.now
