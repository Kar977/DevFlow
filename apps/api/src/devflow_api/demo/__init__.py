"""Read-only public showcase: fictional data seeding for the demo deployment.

Nothing in this package runs unless ``Settings.demo_mode`` is true — see
``entrypoint.sh`` and ``__main__.py``. It is a maintenance script, not part
of the request path, so — unlike ``api/v1/*`` — it is allowed to reach
straight into ``core.models`` and open its own database session.
"""
