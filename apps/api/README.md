# DevFlow API

FastAPI backend for DevFlow Insight.

## Development

Install and run checks from this directory:

```powershell
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Run the development server:

```powershell
uv run uvicorn devflow_api.main:app --reload
```

## API Contract

- `GET /health` returns service health.
- Versioned routes are mounted under `/api/v1`.

The current scaffold intentionally defines placeholder routers for the main
domain areas without implementing domain workflows yet.
