"""Entry point for ``python -m devflow_api.demo`` — see entrypoint.sh.

Refuses to run unless ``Settings.demo_mode`` is true. This is the only
thing standing between a misconfigured deployment and a wiped production
database — the seeder truncates every domain table (see ``demo/wipe.py``)
before rebuilding it from scratch.
"""

import asyncio
import logging
import sys

from devflow_api.core.config import get_settings
from devflow_api.core.database import engine
from devflow_api.demo.runner import run_seed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _main() -> None:
    settings = get_settings()
    if not settings.demo_mode:
        logger.error(
            "Refusing to seed: DEVFLOW_API_DEMO_MODE is not enabled. "
            "This command truncates the database — never run it against "
            "a database holding real data."
        )
        sys.exit(1)

    counts = await run_seed()
    logger.info("Demo seed complete: %s", counts)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
