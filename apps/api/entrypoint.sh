#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

if [ "$DEVFLOW_API_DEMO_MODE" = "true" ]; then
    echo "Seeding demo data..."
    python -m devflow_api.demo
fi

echo "Starting API server..."
exec uvicorn devflow_api.main:app --host 0.0.0.0 --port 8000
