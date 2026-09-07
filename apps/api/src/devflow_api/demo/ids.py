"""Deterministic UUIDs for seeded demo rows.

Every reseed (see ``entrypoint.sh``, on every container start) truncates and
rebuilds the whole dataset from scratch. Using ``uuid5`` instead of ``uuid4``
means a given logical entity — "the third task in the Platforma Web
project", say — gets the *same* primary key across restarts, so a bookmarked
demo URL like ``/projects/<id>`` or ``/pull-requests/<id>`` keeps working.

Only the *identity* is stable. The content behind it (dates, counts) still
shifts on every run, because it is computed relative to "now" — see
``timeline.py``.
"""

import uuid

# Fixed, arbitrary constant — never regenerate this, or every previously
# stable demo URL changes.
_SEED_NAMESPACE = uuid.UUID("6f2a0c9e-4b17-5d3a-9c81-0e2f7a15b4d0")


def det_uuid(*parts: str) -> uuid.UUID:
    """Return a stable uuid5 derived from *parts*, joined with '|'."""
    return uuid.uuid5(_SEED_NAMESPACE, "|".join(parts))
