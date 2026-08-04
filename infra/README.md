# Infrastructure

Local and deployment infrastructure configuration for DevFlow Insight.

## Stack

- **API:** FastAPI on port `8000`
- **Database:** PostgreSQL 18.3 on port `5432`
- **Cache:** Redis on port `6379` — used for metrics caching (falls back to an in-memory cache when `DEVFLOW_API_REDIS_URL` is unset)

## Local Development

### Prerequisites

- Docker Desktop
- File `apps/api/.env` (copy from `.env.example` and fill in values)

### First-time Setup

```powershell
# Copy configuration
cp apps/api/.env.example apps/api/.env

# Start the stack (API + PostgreSQL)
docker compose -f infra/docker-compose.yml up -d

# Run database migrations
docker compose -f infra/docker-compose.yml exec api uv run alembic upgrade head

# Verify it's working
curl http://localhost:8000/health
# Expected response: {"status": "ok", "environment": "local"}
```

### Subsequent Starts

```powershell
docker compose -f infra/docker-compose.yml up -d
```

### Stopping

```powershell
docker compose -f infra/docker-compose.yml down
# With data volume removal:
docker compose -f infra/docker-compose.yml down -v
```

## Environment Variables

File `apps/api/.env`:

| Variable | Local value | Description |
|---|---|---|
| `DEVFLOW_API_ENVIRONMENT` | `local` | Environment: local/test/staging/production |
| `DEVFLOW_API_DEBUG` | `true` | Debug mode |
| `DEVFLOW_API_DATABASE_URL` | `postgresql+asyncpg://devflow:devflow@localhost:5432/devflow` | Database URL |
| `DEVFLOW_API_CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Allowed origins |
| `DEVFLOW_API_SECRET_KEY` | *generate random 32+ char string* | JWT signing key |
| `DEVFLOW_API_REDIS_URL` | `redis://localhost:6379/0` | Metrics cache backend; empty = in-memory fallback |
| `DEVFLOW_API_GITHUB_CLIENT_ID` | *from GitHub OAuth App* | GitHub OAuth Client ID (per-member identity link) |
| `DEVFLOW_API_GITHUB_CLIENT_SECRET` | *from GitHub OAuth App* | GitHub OAuth Client Secret |
| `DEVFLOW_API_GITHUB_TOKEN_ENCRYPTION_KEY` | *generate Fernet key* | Encrypts stored GitHub OAuth access tokens |
| `DEVFLOW_API_GITHUB_APP_ID` | *from GitHub App* | GitHub App ID (org-level repo access) |
| `DEVFLOW_API_GITHUB_APP_SLUG` | *from GitHub App* | GitHub App slug, used to build the install URL |
| `DEVFLOW_API_GITHUB_APP_PRIVATE_KEY` | *from GitHub App* | GitHub App private key (PEM) |
| `DEVFLOW_API_GITHUB_WEBHOOK_SECRET` | *generate random string* | GitHub webhook HMAC secret |

**Note:** `DEVFLOW_API_SECRET_KEY`, `DEVFLOW_API_GITHUB_CLIENT_SECRET`, `DEVFLOW_API_GITHUB_TOKEN_ENCRYPTION_KEY`, `DEVFLOW_API_GITHUB_APP_PRIVATE_KEY`, and `DEVFLOW_API_GITHUB_WEBHOOK_SECRET` must never be committed to the repository. `DEVFLOW_API_GITHUB_APP_SLUG` and `DEVFLOW_API_GITHUB_APP_PRIVATE_KEY` are required together once `DEVFLOW_API_GITHUB_APP_ID` is set (the app refuses to start otherwise).

## Docker Compose — Services

```yaml
services:
  api:       # FastAPI on port 8000
  postgres:  # PostgreSQL 18.3 on port 5432
  redis:     # redis:7-alpine on port 6379 — metrics cache
```

## Database Migrations

```powershell
# Create a new migration (after adding ORM models)
docker compose -f infra/docker-compose.yml exec api uv run alembic revision --autogenerate -m "add users table"

# Apply migrations
docker compose -f infra/docker-compose.yml exec api uv run alembic upgrade head

# Roll back the last migration
docker compose -f infra/docker-compose.yml exec api uv run alembic downgrade -1

# View migration history
docker compose -f infra/docker-compose.yml exec api uv run alembic history
```

## CI/CD

### `ci.yml` — PR verification (implemented)

`.github/workflows/ci.yml` runs on every push and PR against `main`,
scoped to `apps/api/`:

1. Checkout code
2. Set up Python 3.14 + uv
3. `uv sync` — install dependencies
4. `uv run ruff check .` — linting
5. `uv run ruff format --check .` — format check
6. `uv run mypy src tests` — type checking
7. `uv run pytest --tb=short` — tests

**Not yet implemented:** a PostgreSQL service container in CI (tests run
against fake in-memory repositories, not a real database — see
`apps/api/tests/README.md`), and `apps/web` is not built or tested in CI.

### `docker.yml` — image build (to be implemented)

Triggered on: push to `main`

Steps:
1. Build Docker image
2. Push to GitHub Container Registry (`ghcr.io`)
3. Tag: `latest` + commit SHA

### `release.yml` — versioning (to be implemented)

Triggered on: tag creation `v*.*.*`

Steps:
1. Build image with version tag
2. Create GitHub Release with changelog

## Production Deployment (planned)

In production each service should be a separate container/pod:
- **API:** horizontally scalable (min. 2 replicas), stateless
- **PostgreSQL:** managed instance (e.g. AWS RDS, Supabase)
- **Redis:** managed instance (e.g. AWS ElastiCache)
- **Secrets:** AWS Secrets Manager or HashiCorp Vault (not environment variables)
