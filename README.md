# DevFlow Insight

DevFlow Insight is a developer productivity platform. It allows developers to manage projects and tasks, track work time, and measure their productivity through analytics dashboards. It also gives teams GitHub PR-flow analytics — stale PR counts, review velocity, throughput — for repositories tracked through a GitHub App or personal OAuth connection.

## What is DevFlow Insight?

A developer can log in and:
- Create projects and organize work in teams (organizations)
- Manage tasks: status, priority, time estimates
- Track time spent on tasks (start/stop timer)
- View productivity dashboards: velocity, completion rate, estimation accuracy, activity streaks
- Connect a GitHub account or install the GitHub App on an organization, track repositories, and view PR-flow metrics (stale PRs, review velocity, weekly throughput, review ratio) alongside the productivity dashboards

## Roadmap

### Stage 1 — Backend API (done)

FastAPI REST API. All domains below are implemented, tested, and mounted under `/api/v1`:
1. **Auth** — registration, JWT login, refresh-token rotation via httpOnly cookie
2. **Organizations** — workspace/team management with roles, soft-deletable
3. **Projects** — developer projects, with a `stats` summary per project
4. **Tasks + Time Tracking** — tasks with a start/stop timer
5. **Metrics** — productivity dashboards (velocity, completion rate, estimation accuracy, streaks) and PR-flow dashboards, both Redis-cached
6. **Reports** — async report generation with JSON, CSV, and PDF export
7. **GitHub Integration** — personal OAuth connection, org-level GitHub App installation, PR/review sync, webhooks

### Stage 2 — Frontend (done)

React + TypeScript + Vite single-page app in `apps/web/`:
- Login and registration screens
- Developer productivity dashboard and PR-flow dashboard
- Project and task views, with a start/stop timer
- Reports view with CSV/PDF export
- GitHub App installation, repository tracking, and PR list/detail views

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                       CLIENTS                        │
│         React App (apps/web)  |  Swagger UI          │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP/REST
┌─────────────────▼───────────────────────────────────┐
│              FastAPI Backend (apps/api)               │
│                                                      │
│  /api/v1/auth          /api/v1/organizations         │
│  /api/v1/projects      /api/v1/tasks                 │
│  /api/v1/metrics       /api/v1/reports               │
│  /api/v1/repositories  /api/v1/pull-requests          │
│  /api/v1/integrations/github                         │
│                                                      │
│  Core: config | database | security | errors | cache │
│  Layers: routes → services → repositories → models   │
└─────────────────┬──────────────────┬─────────────────┘
                  │                  │
┌─────────────────▼───────┐  ┌───────▼───────────────┐
│      PostgreSQL 18.3     │  │        Redis           │
│  users | organizations   │  │   metrics cache         │
│  projects | tasks        │  │   (falls back to        │
│  work_sessions | reports │  │   in-memory when unset) │
│  github_connections      │  └────────────────────────┘
│  repositories | pull_requests | pull_request_reviews  │
│  github_installations | sync_runs                     │
└─────────────────────────────────────────────────────┘
```

`repositories` and `pull_requests` are org-scoped GitHub data (tracked repos, synced PRs and
reviews), distinct from the `projects`/`tasks` productivity domain — see the note in
[Product Requirements](docs/product/README.md#feature-to-module-mapping).

## Monorepo Layout

```
devflow/
├── apps/
│   ├── api/                 # FastAPI backend
│   │   ├── src/devflow_api/
│   │   │   ├── api/v1/      # Route handlers per domain
│   │   │   └── core/        # Config, DB, models, services
│   │   ├── tests/
│   │   ├── migrations/      # Alembic migrations
│   │   └── README.md        # Full API spec
│   └── web/                 # React + TypeScript + Vite frontend
│       └── src/
│           ├── app/         # App shell, router, providers
│           ├── features/    # Feature-sliced pages/components/hooks
│           └── shared/      # API client, stores, UI primitives
├── docs/
│   └── product/
│       └── README.md       # Product requirements and user stories
├── infra/
│   ├── docker-compose.yml  # API + PostgreSQL + Redis
│   └── README.md           # Infrastructure guide
└── README.md               # This file
```

## Quick Start

Requirements: Docker, Docker Compose.

```powershell
# 1. Copy environment config
cp apps/api/.env.example apps/api/.env

# 2. Start the API stack (FastAPI + PostgreSQL + Redis)
docker compose -f infra/docker-compose.yml up -d

# 3. Run database migrations
docker compose -f infra/docker-compose.yml exec api uv run alembic upgrade head

# 4. Verify it's running
curl http://localhost:8000/health
```

API is available at `http://localhost:8000`. Interactive Swagger docs: `http://localhost:8000/docs`.

To run the frontend, from `apps/web/`: `npm install && npm run dev` — it proxies `/api` to the
backend and serves on `http://localhost:5173`.

## Documentation

- [Backend API](apps/api/README.md) — endpoint spec, data models, development guide
- [Product Requirements](docs/product/README.md) — user stories, metrics, vision
- [Infrastructure](infra/README.md) — Docker, CI/CD, deployment

## Project scope note

The initial product brief (`.local_docs/DevFlow Insight/`) defined a GitHub PR analytics
tool. During implementation the scope pivoted to a developer productivity platform
(projects, tasks, time tracking); that pivot is the formal record in
`docs/decision-log-addendum.md`. GitHub PR-flow analytics was later re-added alongside the
productivity domain (org-scoped `repositories`/`pull_requests`/`pull_request_reviews`, the
5 PR-flow KPIs, GitHub App installation) — see
`docs/superpowers/specs/2026-06-26-github-pr-analytics-design.md`. The original brief files
under `.local_docs/` are preserved as historical context but are superseded by
`docs/product/README.md`.

- [Reconciliation report](docs/reconciliation-report.md) — full audit of brief vs. implementation
- [Decision log addendum](docs/decision-log-addendum.md) — formal record of the product pivot
