# Infrastructure

Local and deployment infrastructure configuration for DevFlow Insight.

## Stack

- **API:** FastAPI on port `8000`
- **Database:** PostgreSQL 18.3 on port `5432`
- **Cache** *(to be added)*: Redis on port `6379` — needed for metrics caching

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
| `DEVFLOW_API_GITHUB_CLIENT_ID` | *from GitHub OAuth App* | GitHub OAuth Client ID |
| `DEVFLOW_API_GITHUB_CLIENT_SECRET` | *from GitHub OAuth App* | GitHub OAuth Client Secret |
| `DEVFLOW_API_GITHUB_WEBHOOK_SECRET` | *generate random string* | GitHub webhook HMAC secret |

**Note:** `DEVFLOW_API_SECRET_KEY`, `DEVFLOW_API_GITHUB_CLIENT_SECRET`, and `DEVFLOW_API_GITHUB_WEBHOOK_SECRET` must never be committed to the repository.

## Docker Compose — Services

### Current State

```yaml
services:
  api:       # FastAPI on port 8000
  postgres:  # PostgreSQL 18.3 on port 5432
```

### To Add: Redis (metrics cache)

A Redis service should be added to `docker-compose.yml` once `MetricsService` with caching is implemented:

```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - devflow-redis-data:/data
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

## CI/CD (to be implemented)

Create the following GitHub Actions workflows in `.github/workflows/`:

### `ci.yml` — PR verification

Triggered on: every push to a branch + PR open/update

Steps:
1. Checkout code
2. Set up Python 3.14 + uv
3. `uv sync` — install dependencies
4. `uv run ruff format --check .` — format check
5. `uv run ruff check .` — linting
6. `uv run mypy src tests` — type checking
7. Start PostgreSQL (service container)
8. `uv run pytest` — integration tests

### `docker.yml` — image build

Triggered on: push to `main`

Steps:
1. Build Docker image
2. Push to GitHub Container Registry (`ghcr.io`)
3. Tag: `latest` + commit SHA

### `release.yml` — versioning

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
