# DevFlow Insight — Product Requirements

## Product Vision

DevFlow Insight gives developers a single place to manage their work and understand their own productivity. Instead of guessing "am I being effective?", a developer sees real data: how many tasks they closed, how accurately they estimate, and during which hours they are most focused.

**Problem we solve:** Developers lack a tool that simultaneously enables work management and productivity measurement in a personal, contextual way — without the overhead of heavy project management tools.

## Users

### Primary User: Developer

A software developer working individually or in a small team (2–15 people). They want to:
- Know what they're working on and what to do next
- Not waste time on heavy project management tools
- Understand their work pace and areas for improvement
- Optionally: connect with GitHub to avoid duplicating data

### Secondary User: Tech Lead / Engineering Manager

Wants to see team-level aggregates: velocity, work distribution, who is overloaded. Does not need to drill into individual developer task details.

---

## User Stories

### Auth

- As a developer I want to register with email and password so I have a private account
- As a developer I want to log in and receive a JWT token so I can use the API
- As a developer I want to refresh my token without re-logging in so my session doesn't expire unexpectedly
- As a developer I want to log out and invalidate my token so my session is secure
- As a developer I want to update my profile (name, avatar URL)

### Organizations (Workspaces / Teams)

- As a developer I want to create a workspace/organization to group projects together
- As a developer I want to invite other developers to my organization for team collaboration
- As a tech lead I want to assign roles (owner/admin/member) to control permissions
- As a developer I want to belong to multiple organizations (e.g. work + side projects)

### Projects

- As a developer I want to create projects within an organization or as personal projects
- As a developer I want to describe a project (name, description, status: active/archived)
- As a developer I want to optionally link a project to a GitHub repository
- As a developer I want to see project statistics: total tasks, open tasks, overdue tasks

### Tasks + Time Tracking

- As a developer I want to create tasks with title, description, priority, and time estimate
- As a developer I want to change task status: backlog → todo → in_progress → review → done
- As a developer I want to start a timer when I begin working on a task
- As a developer I want to stop the timer when I finish or pause work
- As a developer I want to see the work session history for a task
- As a developer I want to see total time spent on a task vs estimate
- As a developer I want tasks imported from GitHub PR/issues (when GitHub is connected)

### Metrics and Dashboards

- As a developer I want to see a productivity summary for the last 7/30 days
- As a developer I want to see velocity: how many tasks I close per week, with trend
- As a developer I want to see my daily active work hours (from time tracking)
- As a developer I want to see estimation accuracy: how precisely I estimate tasks
- As a developer I want to see an activity streak: how many consecutive days I closed at least 1 task
- As a developer I want to see project health: % overdue tasks per project
- As a tech lead I want to see metrics aggregated across the entire organization

### Reports

- As a developer I want to generate a weekly summary of my work
- As a developer I want to export data to JSON/CSV
- As a tech lead I want project status reports for stakeholders

### GitHub Integration

- As a developer I want to connect my GitHub account via OAuth
- As a developer I want PRs synchronized as tasks (automatically via webhook)
- As a developer I want Issues synchronized as tasks
- As a developer I want to manually trigger synchronization
- As a developer I want to disconnect GitHub and remove connection data

---

## Productivity Metrics

The following metrics are calculated by `MetricsService` from data in the `tasks` and `work_sessions` tables.

### Velocity

```
velocity = number of tasks with status 'done' in a given week
trend = comparison against the previous 4 weeks
```

### Completion Rate

```
completion_rate = done_tasks / (done_tasks + cancelled_tasks + total_open_tasks) * 100
period: last 30 days
```

### Estimation Accuracy

```
accuracy = actual_time_minutes / estimated_time_minutes
- ratio < 0.8  → over-estimated (you budget too much time)
- ratio 0.8–1.2 → accurate
- ratio > 1.2  → under-estimated (you underestimate effort)
calculated only for tasks with status 'done' and a filled estimate
```

### Daily Active Hours

```
active_hours_per_day = sum(work_sessions.duration_minutes) / 60
aggregated daily, displayed as a heatmap or bar chart
```

### Task Streak

```
streak = maximum number of consecutive days on which the developer closed >= 1 task
current_streak = current run
longest_streak = all-time record
```

### Project Health

```
overdue_rate = tasks with due_date < now() and status != 'done' / total_tasks * 100
status: healthy (<10%), at_risk (10–30%), critical (>30%)
```

---

## Feature-to-Module Mapping

| Feature | Router dir | Base path |
|---|---|---|
| Auth | auth | `/api/v1/auth` |
| Workspaces/Teams | organizations | `/api/v1/organizations` |
| Projects | projects | `/api/v1/projects` |
| Tasks + Time Tracking | tasks | `/api/v1/tasks` |
| Metrics + PR-flow KPIs | metrics | `/api/v1/metrics` |
| Reports | reports | `/api/v1/reports` |
| GitHub PR analytics | pull_requests | `/api/v1/pull-requests` |
| GitHub tracked repos | repositories | `/api/v1/repositories` |
| GitHub App + OAuth + sync | integrations/github | `/api/v1/integrations/github` |

**Note:** Projects and Tasks each have their own router directory today.
The `pull_requests` and `repositories` router directories carry a different
domain than their names suggest — they serve org-scoped GitHub PR data
(added later, see `docs/superpowers/specs/2026-06-26-github-pr-analytics-design.md`),
not the task-management Projects/Tasks endpoints. Names kept as-is to
preserve scaffold continuity.

---

## Implementation Priorities (Stage 1 — backend)

Order is driven by technical dependencies:

1. **Auth** — foundation: nothing else works without a user identity
2. **Organizations** — container for projects
3. **Projects** — container for tasks
4. **Tasks + Time Tracking** — core product value
5. **Metrics** — requires data from tasks/work_sessions
6. **GitHub Integration** — optional, requires working task management
7. **Reports** — requires data from metrics/tasks

---

## Non-Functional Requirements

- **Latency:** CRUD endpoints < 200 ms p95, metrics < 500 ms p95 (with cache)
- **Auth:** JWT access token TTL 15 minutes, refresh token TTL 30 days
- **Security:** passwords hashed with bcrypt (cost factor 12), GitHub tokens encrypted at rest
- **Pagination:** all list endpoints support `limit` (max 100) and `offset`
- **Validation:** Pydantic v2 on all inputs; errors in standard format `{"error": {...}}`
- **Tests:** every service and endpoint must have integration tests
