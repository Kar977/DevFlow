"""Tests for the demo reset background loop (devflow_api.demo.scheduler).

Uses a fake ``asyncio`` namespace whose ``sleep`` yields control (via a real
zero-length ``asyncio.sleep(0)``) instead of actually waiting out the
interval, so the loop can be driven through several iterations instantly.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

import devflow_api.demo.scheduler as scheduler_module
from devflow_api.demo.scheduler import get_next_reset_at, run_reset_loop


class _FakeAsyncio:
    """Stands in for the `asyncio` module inside scheduler.py.

    `sleep` never actually waits, but still yields once to the real event
    loop (a real zero-length `asyncio.sleep(0)`) so cancellation and other
    tasks can interleave — a coroutine that returns without awaiting
    anything would let a `while True` loop spin forever without ever
    handing control back to the test.
    """

    CancelledError = asyncio.CancelledError

    @staticmethod
    async def sleep(_seconds: float) -> None:
        await asyncio.sleep(0)


async def _wait_until(predicate: object, *, timeout: float = 2.0) -> None:
    async def _poll() -> None:
        while not predicate():  # type: ignore[operator]
            await asyncio.sleep(0)

    await asyncio.wait_for(_poll(), timeout=timeout)


@pytest.fixture(autouse=True)
def _fake_asyncio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler_module, "asyncio", _FakeAsyncio())


async def test_loop_resets_repeatedly_and_tracks_next_reset_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def fake_run_seed() -> dict[str, int]:
        calls.append(len(calls))
        return {"tasks": 1}

    monkeypatch.setattr(scheduler_module, "run_seed", fake_run_seed)

    task = asyncio.create_task(run_reset_loop(30))
    try:
        await _wait_until(lambda: len(calls) >= 3)
        assert get_next_reset_at() is not None
        assert get_next_reset_at() > datetime.now(UTC)  # type: ignore[operator]
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # Cancellation clears the published next-reset time.
    assert get_next_reset_at() is None


async def test_loop_survives_a_failed_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def flaky_run_seed() -> dict[str, int]:
        calls.append("attempt")
        if len(calls) == 1:
            raise RuntimeError("boom")
        return {"tasks": 1}

    monkeypatch.setattr(scheduler_module, "run_seed", flaky_run_seed)

    task = asyncio.create_task(run_reset_loop(30))
    try:
        # A second attempt only happens if the first failure was swallowed.
        await _wait_until(lambda: len(calls) >= 2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_next_reset_at_is_none_when_loop_has_not_started() -> None:
    assert get_next_reset_at() is None


async def test_interval_is_respected_in_next_reset_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_seed() -> dict[str, int]:
        return {}

    monkeypatch.setattr(scheduler_module, "run_seed", fake_run_seed)

    before = datetime.now(UTC)
    task = asyncio.create_task(run_reset_loop(45))
    try:
        await _wait_until(lambda: get_next_reset_at() is not None)
        next_reset = get_next_reset_at()
        assert next_reset is not None
        assert next_reset - before >= timedelta(minutes=45) - timedelta(seconds=5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
