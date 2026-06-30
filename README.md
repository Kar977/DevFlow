# DevFlow Insight

DevFlow Insight is a developer productivity platform. It allows developers to manage projects and tasks, track work time, and measure their productivity through analytics dashboards.

## What is DevFlow Insight?

A developer can log in and:
- Create projects and organize work in teams (organizations)
- Manage tasks: status, priority, time estimates
- Track time spent on tasks (start/stop timer)
- View productivity dashboards: velocity, completion rate, estimation accuracy, activity streaks
- Optionally: connect a GitHub account and sync PRs/issues as tasks

## Roadmap

### Stage 1 — Backend API (current stage)

Backend only (FastAPI REST API). No frontend yet.

Domains to implement (in dependency order):
1. **Auth** — registration, JWT login, token management
2. **Organizations** — workspace/team management with roles
3. **Projects** — developer projects (router: `/repositories`)
4. **Tasks + Time Tracking** — tasks with timer (router: `/pull-requests`)
5. **Metrics** — productivity metrics and dashboards
6. **Reports** — data export (JSON → CSV/PDF)
7. **GitHub Integration** — optional GitHub sync

### Stage 2 — Frontend (planned)

React + TypeScript + Vite application in `apps/web/`. Views:
- Login and registration screens
- Developer metrics dashboard
- Project and task list (Kanban/List view)
- Work time tracker
- Reports and export view

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                  CLIENTS (Stage 2)                   │
│         React App (apps/web)  |  Swagger UI          │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP/REST
┌─────────────────▼───────────────────────────────────┐
│              FastAPI Backend (apps/api)               │
│                                                      │
│  /api/v1/auth          /api/v1/organizations         │
│  /api/v1/projects      /api/v1/tasks                 │
│  /api/v1/metrics       /api/v1/reports               │
│  /api/v1/integrations/github                         │
│                                                      │
│  Core: config | database | security | errors         │
│  Layers: routes → services → repositories → models   │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│              PostgreSQL 18.3                          │
│   users | organizations | projects | tasks           │
│   work_sessions | reports | github_connections       │
└─────────────────────────────────────────────────────┘
```

## Monorepo Layout

```
devflow/
├── apps/
│   └── api/                # FastAPI backend (Stage 1)
│       ├── src/devflow_api/
│       │   ├── api/v1/     # Route handlers per domain
│       │   └── core/       # Config, DB, models, services
│       ├── tests/
│       ├── migrations/     # Alembic migrations
│       └── README.md       # Full API spec
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

# 2. Start the stack
docker compose -f infra/docker-compose.yml up -d

# 3. Run database migrations
docker compose -f infra/docker-compose.yml exec api uv run alembic upgrade head

# 4. Verify it's running
curl http://localhost:8000/health
```

API is available at `http://localhost:8000`. Interactive Swagger docs: `http://localhost:8000/docs`.

## Documentation

- [Backend API](apps/api/README.md) — endpoint spec, data models, development guide
- [Product Requirements](docs/product/README.md) — user stories, metrics, vision
- [Infrastructure](infra/README.md) — Docker, CI/CD, deployment

## Project scope note

The initial product brief (`.local_docs/DevFlow Insight/`) defined a GitHub PR analytics
tool. During implementation the scope pivoted to a developer productivity platform
(projects, tasks, time tracking). The original brief files are preserved as historical
context but are superseded.

- [Reconciliation report](docs/reconciliation-report.md) — full audit of brief vs. implementation
- [Decision log addendum](docs/decision-log-addendum.md) — formal record of the product pivot
