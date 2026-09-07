"""Truncates every demo-relevant table before a reseed.

A single ``TRUNCATE ... CASCADE`` rather than per-table ``DELETE``: it
needs no FK-ordering, has no per-row trigger cost, and — critically — it is
the only thing that reliably clears ``metric_snapshots``, whose rows are
otherwise treated as immutable once captured (see
``core.services.metric_snapshot``'s module docstring). ``alembic_version``
is deliberately not in this list.

``TRUNCATE`` takes an ``ACCESS EXCLUSIVE`` lock, so this must run before
uvicorn starts accepting traffic — never against a live API (see
``entrypoint.sh``).
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_TABLES: tuple[str, ...] = (
    "metric_snapshots",
    "task_status_changes",
    "work_sessions",
    "tasks",
    "projects",
    "pull_request_reviews",
    "pull_requests",
    "repositories",
    "github_installations",
    "sync_runs",
    "reports",
    "github_connections",
    "refresh_tokens",
    "organization_settings",
    "organization_members",
    "organizations",
    "users",
)


async def wipe_all(session: AsyncSession) -> None:
    """Truncate every demo table, resetting identity sequences, cascading FKs."""
    table_list = ", ".join(_TABLES)
    await session.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))
