# DevFlow Insight

DevFlow Insight is a monorepo-ready workspace for building product and engineering
analytics around developer flow.

The first implementation stage focuses on the FastAPI backend in `apps/api`.
Frontend applications and broader automation can be added under `apps/` in later
stages.

## Layout

- `apps/` - deployable applications.
- `docs/` - product, architecture, and operating documentation.
- `infra/` - local infrastructure and deployment foundations.

## Backend

The API service lives in `apps/api` and exposes versioned routes under `/api/v1`
plus a root health probe at `/health`.
