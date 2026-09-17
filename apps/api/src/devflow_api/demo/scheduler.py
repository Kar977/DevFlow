"""Background loop that resets demo data to its seeded baseline on a timer.

Started from ``main.py``'s lifespan when ``Settings.demo_mode`` is on and
``demo_reset_interval_minutes`` is positive, and cancelled on shutdown. This
is what lets a public demo deployment stay editable for visitors while never
drifting far from a clean, presentable state — see ``runner.run_seed`` for
why the reset itself is safe to run against a live API.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from devflow_api.demo.runner import run_seed

logger = logging.getLogger(__name__)

# Written only by run_reset_loop, read by the /demo/status endpoint. A plain
# module global is fine here: asyncio is single-threaded, there is at most
# one loop per process, and the only consumer is a best-effort status read.
_next_reset_at: datetime | None = None


def get_next_reset_at() -> datetime | None:
    """Return the UTC time of the next scheduled reset, or ``None`` if idle."""
    return _next_reset_at


async def run_reset_loop(interval_minutes: int) -> None:
    """Reset demo data to its seeded baseline every ``interval_minutes``, forever.

    Runs as a background asyncio task for the lifetime of the app. A failed
    reset is logged and swallowed rather than propagated — one bad cycle
    must not kill the loop, since the next cycle will simply try again.
    """
    global _next_reset_at
    interval = timedelta(minutes=interval_minutes)
    try:
        while True:
            _next_reset_at = datetime.now(UTC) + interval
            await asyncio.sleep(interval.total_seconds())
            try:
                counts = await run_seed()
                logger.info("Demo reset complete: %s", counts)
            except Exception:
                logger.exception("Demo reset failed — will retry next interval")
    except asyncio.CancelledError:
        _next_reset_at = None
        logger.info("Demo reset loop cancelled")
        raise
