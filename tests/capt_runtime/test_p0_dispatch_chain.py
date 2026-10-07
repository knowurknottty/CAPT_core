"""P0.3 integrated actual-chain test.

Proves the real wiring, not a mock of it:

    RuntimeService -> ProviderDriver -> recorder callback
        -> EventStore/durable aggregate -> provider dispatch

Properties proved:
1. request_started is durable in the EventStore BEFORE the external HTTP call.
2. Exactly-once: one dispatch attempt performs one external call.
3. Response and terminal boundaries are recorded durably in order.
4. Exact-duplicate record (same idempotency key) is idempotent: no new event.
5. Conflicting replay (same idempotency key, different boundary) is rejected.
6. Recorder failure aborts dispatch: no external call happens.
7. Restart persistence: a fresh runtime over the same ledger sees the boundary.
8. Backward boundary moves fail closed at the service (IllegalTransition).
"""
from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import pytest

from capt_runtime import commands
from capt_runtime.aggregates import DriverRunAggregate as ServiceDriverRunAggregate
from capt_runtime.composition import create_runtime
from capt_runtime.drivers.provider import (
    DispatchBoundaryError,
    ProviderDriver,
)
from capt_runtime.errors import IllegalTransition

T = "2026-09-28T00:00:00Z"


def _meta(key: str, boundary: str, seq: int = 0) -> dict:
    return commands.command(
        command_id="cmd-%s-%d" % (key, seq),
        idempotency_key="idem-%s-%s-%d" % (key, boundary, seq),
        operation_fingerprint=commands.fingerprint(
            "record_driver_dispatch_boundary",
            {"driverRunId": key, "dispatchBoundary": boundary, "sequence": seq},
        ),
        correlation_id="corr-" + key,
        actor_id="exec-1",
        actor_kind="execution_plane",
        issued_at=T,
        replay_policy="never",
    )


def _make_run(svc, run_id: str) -> None:
    svc.create_driver_run(
        {
            "schemaVersion": "1.0.0",
            "driverRunId": run_id,
            "driverId": "provider",
            "missionId": "m-chain",
            "taskId": "t-chain",
            "workOrderVersion": 1,
            "externalRunId": None,
            "state": "created",
            "reconciliationStatus": "not_required",
            "createdAt": T,
        },
        _meta(run_id, "create"),
    )


def _recorder(svc, run_id: str, seq_box: dict):
    def record(rid: str, boundary: str) -> None:
        seq_box["n"] += 1
        svc.record_driver_dispatch_boundary(
            rid, boundary, _meta(run_id, boundary, seq_box["n"]))
    return record


def _durable_boundary(store, run_id: str):
    stream = ServiceDriverRunAggregate.stream_id(run_id)
    return store.require_state(stream).get("dispatchBoundary")


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _driver(tmp_path: Path, recorder) -> ProviderDriver:
    return ProviderDriver(
        str(tmp_path),
        provider_id="local-test",
        model="test-model",
        base_url="http://127.0.0.1:1",
        boundary_recorder=recorder,
    )


def test_chain_durability_before_dispatch(tmp_path: Path, monkeypatch) -> None:
    """request_started is durable in the EventStore before urlopen is touched."""
    ledger = str(tmp_path / "ledger.db")
    runtime = create_runtime(ledger)
    try:
        svc, store = runtime.service, runtime.store
        run_id = "dr-chain-1"
        _make_run(svc, run_id)
        seq = {"n": 0}
        driver = _driver(tmp_path, _recorder(svc, run_id, seq))

        witnessed = {}

        def fake_urlopen(req, timeout=None):
            # The external call happens HERE. The boundary must already be
            # durable in the store at this instant.
            witnessed["boundary_at_io"] = _durable_boundary(store, run_id)
            witnessed["calls"] = witnessed.get("calls", 0) + 1
            return _FakeResponse({"choices": [{"message": {"content": "ok"}}]})

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        data = driver._post_json(
            run_id, "http://127.0.0.1:1/v1/chat", {"model": "m"}, {})
        assert data["choices"][0]["message"]["content"] == "ok"
        # 1. durability-before-dispatch: proven at the instant of I/O.
        assert witnessed["boundary_at_io"] == "request_started"
        # 2. exactly-once: one dispatch attempt, one external call.
        assert witnessed["calls"] == 1
        # 3. response boundaries recorded durably, in order.
        assert _durable_boundary(store, run_id) == "response_completed"
        stream = ServiceDriverRunAggregate.stream_id(run_id)
        boundaries = [
            e["payload"]["dispatchBoundary"]
            for e in store.read_stream(stream)
            if e.get("payload", {}).get("eventType") == "DriverRunDispatchBoundaryRecorded"
        ]
        assert boundaries == ["request_started", "response_started", "response_completed"]
        # Terminal boundary closes the chain.
        svc.record_driver_dispatch_boundary(
            run_id, "result_persisted", _meta(run_id, "result_persisted", 99))
        assert _durable_boundary(store, run_id) == "result_persisted"
    finally:
        runtime.close()


def test_chain_idempotent_duplicate_and_conflicting_replay(tmp_path: Path) -> None:
    """Exact duplicate is idempotent; conflicting replay is rejected."""
    ledger = str(tmp_path / "ledger.db")
    runtime = create_runtime(ledger)
    try:
        svc, store = runtime.service, runtime.store
        run_id = "dr-chain-2"
        _make_run(svc, run_id)
        stream = ServiceDriverRunAggregate.stream_id(run_id)

        def count_events() -> int:
            return sum(
                1 for e in store.read_stream(stream)
                if e.get("payload", {}).get("eventType") == "DriverRunDispatchBoundaryRecorded"
            )

        meta = _meta(run_id, "request_started", 1)
        r1 = svc.record_driver_dispatch_boundary(run_id, "request_started", meta)
        assert count_events() == 1
        # 4. exact duplicate (same idempotency key + fingerprint): idempotent,
        # no new event, same receipt shape.
        r2 = svc.record_driver_dispatch_boundary(run_id, "request_started", meta)
        assert count_events() == 1
        assert r2.get("status") == "idempotent" and r2.get("replayed") is True
        assert r2["eventIds"] == r1["eventIds"]
        assert _durable_boundary(store, run_id) == "request_started"
        # 5. conflicting replay (same idempotency key, different operation
        # fingerprint): rejected, durable state unchanged.
        conflict_meta = _meta(run_id, "response_started", 1)
        conflict_meta["idempotencyKey"] = meta["idempotencyKey"]
        with pytest.raises(Exception, match="(?i)idempot|conflict|fingerprint"):
            svc.record_driver_dispatch_boundary(
                run_id, "response_started", conflict_meta)
        assert count_events() == 1
        assert _durable_boundary(store, run_id) == "request_started"
    finally:
        runtime.close()


def test_chain_recorder_failure_aborts_dispatch(tmp_path: Path, monkeypatch) -> None:
    """6. Recorder failure -> DispatchBoundaryError, no external call."""
    ledger = str(tmp_path / "ledger.db")
    runtime = create_runtime(ledger)
    try:
        svc = runtime.service
        run_id = "dr-chain-3"
        _make_run(svc, run_id)

        def broken_recorder(rid: str, boundary: str) -> None:
            raise RuntimeError("recorder store unavailable")

        driver = _driver(tmp_path, broken_recorder)
        calls = {"n": 0}

        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            return _FakeResponse({})

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(DispatchBoundaryError, match="not durably recorded"):
            driver._post_json(run_id, "http://127.0.0.1:1/v1/chat", {}, {})
        assert calls["n"] == 0, "external call must not happen when recording fails"
    finally:
        runtime.close()


def test_chain_restart_persists_boundary(tmp_path: Path) -> None:
    """7. A fresh runtime over the same ledger sees the durable boundary."""
    ledger = str(tmp_path / "ledger.db")
    runtime = create_runtime(ledger)
    try:
        svc = runtime.service
        run_id = "dr-chain-4"
        _make_run(svc, run_id)
        seq = {"n": 0}
        rec = _recorder(svc, run_id, seq)
        rec(run_id, "prepared")
        rec(run_id, "request_started")
    finally:
        runtime.close()

    runtime2 = create_runtime(ledger)
    try:
        durable = runtime2.store.require_state(
            ServiceDriverRunAggregate.stream_id(run_id))
        assert durable["dispatchBoundary"] == "request_started"
        # 8. backward moves fail closed at the service after restart too.
        with pytest.raises(IllegalTransition):
            runtime2.service.record_driver_dispatch_boundary(
                run_id, "prepared", _meta(run_id, "prepared", 50))
        assert runtime2.store.require_state(
            ServiceDriverRunAggregate.stream_id(run_id))["dispatchBoundary"] \
            == "request_started"
    finally:
        runtime2.close()
