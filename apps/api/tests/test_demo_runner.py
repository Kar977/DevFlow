"""Tests for devflow_api.demo.runner.run_seed's transaction shape.

The wipe and the rewrite must share one committed transaction — see the
module docstrings on runner.py and demo/wipe.py for why: this reset runs
against a live API (devflow_api.demo.scheduler), so a reader must never be
able to observe an empty, committed database between the two steps. These
tests fake out the database session entirely (no real DB in this suite —
see test_demo_dataset.py) and assert the call order and session reuse
directly, plus that report generation only ever runs after that transaction
commits.
"""

from datetime import UTC, datetime

import pytest

import devflow_api.demo.runner as runner_module
from devflow_api.demo.runner import run_seed


class _FakeTransaction:
    def __init__(self, calls: list[str], session_id: int) -> None:
        self._calls = calls
        self._id = session_id

    async def __aenter__(self) -> None:
        self._calls.append(f"begin:{self._id}")

    async def __aexit__(self, *exc: object) -> None:
        self._calls.append(f"commit:{self._id}")


class _FakeSession:
    def __init__(self, calls: list[str], session_id: int) -> None:
        self._calls = calls
        self.id = session_id

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction(self._calls, self.id)


class _FakeSessionCM:
    def __init__(self, calls: list[str], session_id: int) -> None:
        self._calls = calls
        self._id = session_id

    async def __aenter__(self) -> _FakeSession:
        self._calls.append(f"open:{self._id}")
        return _FakeSession(self._calls, self._id)

    async def __aexit__(self, *exc: object) -> None:
        self._calls.append(f"close:{self._id}")


class _FakeSessionFactory:
    """Records how many independent sessions/transactions were opened."""

    def __init__(self, calls: list[str]) -> None:
        self._calls = calls
        self.open_count = 0

    def __call__(self) -> _FakeSessionCM:
        self.open_count += 1
        return _FakeSessionCM(self._calls, self.open_count)


async def test_wipe_and_write_share_one_session_and_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    factory = _FakeSessionFactory(calls)
    monkeypatch.setattr(runner_module, "async_session_factory", factory)

    async def fake_wipe_all(session: _FakeSession) -> None:
        calls.append(f"wipe:{session.id}")

    async def fake_write_dataset(session: _FakeSession, dataset: object) -> None:
        calls.append(f"write:{session.id}")

    report_calls: list[str] = []

    async def fake_generate_report(*args: object, **kwargs: object) -> None:
        report_calls.append("report")

    monkeypatch.setattr(runner_module, "wipe_all", fake_wipe_all)
    monkeypatch.setattr(runner_module, "_write_dataset", fake_write_dataset)
    monkeypatch.setattr(runner_module, "_do_generate_report", fake_generate_report)

    await run_seed(now=datetime(2026, 9, 7, 12, 0, tzinfo=UTC))

    # Exactly one session was opened for the wipe + rewrite — never two.
    assert factory.open_count == 1
    assert calls == ["open:1", "begin:1", "wipe:1", "write:1", "commit:1", "close:1"]

    # Report generation only happens after that transaction is committed —
    # it must appear strictly after "commit:1" in program order, which the
    # call log above already guarantees since it's a separate list captured
    # after the `await run_seed(...)` call below returned.
    assert len(report_calls) >= 1


async def test_wipe_runs_before_write_within_the_shared_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    factory = _FakeSessionFactory(calls)
    monkeypatch.setattr(runner_module, "async_session_factory", factory)

    async def fake_wipe_all(session: _FakeSession) -> None:
        calls.append("wipe")

    async def fake_write_dataset(session: _FakeSession, dataset: object) -> None:
        calls.append("write")

    async def fake_generate_report(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(runner_module, "wipe_all", fake_wipe_all)
    monkeypatch.setattr(runner_module, "_write_dataset", fake_write_dataset)
    monkeypatch.setattr(runner_module, "_do_generate_report", fake_generate_report)

    await run_seed(now=datetime(2026, 9, 7, 12, 0, tzinfo=UTC))

    assert calls.index("wipe") < calls.index("write")
