FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml README.md ./
COPY src ./src

RUN uv pip install .

EXPOSE 8000

CMD ["uvicorn", "devflow_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
