"""P0.3 regression tests: the durable provider dispatch boundary.

- The boundary vocabulary is forward-monotonic at the aggregate; recording
  ``unknown`` or moving backward fails closed.
- A tool-call loop may legitimately reopen ``request_started`` after a
  completed response; every other backward move is refused.
- The classifier never fabricates certainty: pre-dispatch boundaries are safe
  to retry under fresh authority, in-flight boundaries forbid retry, and
  completed boundaries are harvest-only.
- Boundary progress recorded durably survives process-memory loss: after a
  crash, reconciliation reads the durable marker, never memory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from capt_runtime import commands
from capt_runtime.composition import create_runtime
from capt_runtime.driver_run import DriverRunAggregate
from capt_runtime.reconciliation import classify_dispatch_boundary

T = "2026-09-28T00:00:00Z"


def _illegal():
    return pytest.raises(Exception, match="(?i)illegal|backward|monotonic|unknown|cannot transition")


def test_boundary_vocabulary_validation():
    for boundary in (
        "not_dispatched", "prepared", "request_started", "response_started",
        "response_completed", "result_persisted", "budget_rejected",
    ):
        state = {"driverRunId": "dr-vocab", "dispatchBoundary": "unknown"}
        nxt = DriverRunAggregate.record_dispatch_boundary(state, boundary, T)
        assert nxt["dispatchBoundary"] == boundary
    # Recording "unknown" (or any out-of-vocabulary value) as new progress
    # fails closed. (Re-recording the current value is idempotent, so the
    # bad-value probe starts from a real boundary.)
    for bad in ("unknown", "bogus", ""):
        with _illegal():
            DriverRunAggregate.record_dispatch_boundary(
                {"driverRunId": "dr-vocab", "dispatchBoundary": "not_dispatched"}, bad, T)


def test_boundary_forward_monotonic_matrix():
    state = {"driverRunId": "dr-matrix", "dispatchBoundary": "not_dispatched"}
    # Re-recording the current boundary is idempotent.
    state = DriverRunAggregate.record_dispatch_boundary(state, "not_dispatched", T)
    assert state["dispatchBoundary"] == "not_dispatched"
    state = DriverRunAggregate.record_dispatch_boundary(state, "prepared", T)
    assert state["dispatchBoundary"] == "prepared"
    # Re-recording the current boundary is idempotent.
    state = DriverRunAggregate.record_dispatch_boundary(state, "prepared", T)
    assert state["dispatchBoundary"] == "prepared"
    # Backward moves fail closed.
    with _illegal():
        DriverRunAggregate.record_dispatch_boundary(state, "not_dispatched", T)
    # Unknown is never progress evidence.
    with _illegal():
        DriverRunAggregate.record_dispatch_boundary(state, "unknown", T)
    # Forward through a full dispatch.
    for boundary in ("request_started", "response_started", "response_completed"):
        state = DriverRunAggregate.record_dispatch_boundary(state, boundary, T)
    assert state["dispatchBoundary"] == "response_completed"
    # A tool-call loop legitimately opens a subsequent request round.
    state = DriverRunAggregate.record_dispatch_boundary(state, "request_started", T)
    assert state["dispatchBoundary"] == "request_started"
    # ...but it may not move any other boundary backward.
    with _illegal():
        DriverRunAggregate.record_dispatch_boundary(state, "prepared", T)
    # Terminal: result_persisted admits no further moves.
    state = DriverRunAggregate.record_dispatch_boundary(state, "response_started", T)
    state = DriverRunAggregate.record_dispatch_boundary(state, "response_completed", T)
    state = DriverRunAggregate.record_dispatch_boundary(state, "result_persisted", T)
    with _illegal():
        DriverRunAggregate.record_dispatch_boundary(state, "request_started", T)
    with _illegal():
        DriverRunAggregate.record_dispatch_boundary(state, "response_completed", T)


def test_boundary_budget_rejected_is_pre_dispatch_terminal():
    state = {"driverRunId": "dr-budget"}
    state = DriverRunAggregate.record_dispatch_boundary(state, "budget_rejected", T)
    assert state["dispatchBoundary"] == "budget_rejected"
    # Rejection happens before any dispatch: forward motion is refused.
    with _illegal():
        DriverRunAggregate.record_dispatch_boundary(state, "prepared", T)


def test_classify_dispatch_boundary_matrix():
    assert classify_dispatch_boundary("not_dispatched") == "safe_to_retry"
    assert classify_dispatch_boundary("prepared") == "safe_to_retry"
    assert classify_dispatch_boundary("budget_rejected") == "safe_to_retry"
    assert classify_dispatch_boundary("request_started") == "retry_forbidden"
    assert classify_dispatch_boundary("response_started") == "retry_forbidden"
    assert classify_dispatch_boundary("response_completed") == "reconciled_completed"
    assert classify_dispatch_boundary("result_persisted") == "reconciled_completed"
    # The classifier never fabricates certainty for anything else.
    assert classify_dispatch_boundary("unknown") == "external_state_unknown"
    assert classify_dispatch_boundary("bogus") == "external_state_unknown"


def _boundary_metadata(key: str) -> dict:
    return commands.command(
        command_id="cmd-" + key,
        idempotency_key="idem-" + key,
        operation_fingerprint=commands.fingerprint("p0-boundary", {"key": key}),
        correlation_id="corr-" + key,
        actor_id="exec-1",
        actor_kind="execution_plane",
        issued_at=T,
        replay_policy="never",
    )


def test_durable_boundary_survives_process_memory_loss(tmp_path: Path):
    """Boundary markers recorded durably are visible to a fresh process that
    never saw the in-memory run: reconciliation after a crash reads the
    durable marker, never process memory."""
    ledger = str(tmp_path / "ledger.db")
    runtime = create_runtime(ledger)
    try:
        svc = runtime.service
        run_id = "dr-crash-1"
        svc.create_driver_run(
            {
                "schemaVersion": "1.0.0", "driverRunId": run_id,
                "driverId": "hermes", "missionId": "m-crash", "taskId": "t-crash",
                "workOrderVersion": 1, "externalRunId": None, "state": "created",
                "reconciliationStatus": "not_required",
                "createdAt": "2026-09-28T00:00:00Z",
            },
            _boundary_metadata("p0-create"),
        )
        for seq, boundary in enumerate(("prepared", "request_started")):
            svc.record_driver_dispatch_boundary(
                run_id, boundary, _boundary_metadata("p0-boundary-%d" % seq))
    finally:
        runtime.close()

    # Simulate process loss: a brand-new runtime over the same ledger.
    runtime2 = create_runtime(ledger)
    try:
        durable = runtime2.store.require_state(
            DriverRunAggregate.stream_id(run_id))
        assert durable["dispatchBoundary"] == "request_started"
        # And the classifier treats the recovered marker as in-flight:
        # retry is forbidden, never auto-retried.
        assert classify_dispatch_boundary(durable["dispatchBoundary"]) == "retry_forbidden"
    finally:
        runtime2.close()


def test_repeated_boundary_records_are_distinct_durable_events(tmp_path: Path):
    """A tool loop that re-opens request_started must append a distinct
    durable event each round: reusing one idempotency key per boundary name
    would return the first round's receipt as a duplicate and leave the
    durable marker understated in the unsafe direction."""
    ledger = str(tmp_path / "ledger.db")
    runtime = create_runtime(ledger)
    try:
        svc = runtime.service
        run_id = "dr-loop-1"
        svc.create_driver_run(
            {
                "schemaVersion": "1.0.0", "driverRunId": run_id,
                "driverId": "hermes", "missionId": "m-loop", "taskId": "t-loop",
                "workOrderVersion": 1, "externalRunId": None, "state": "created",
                "reconciliationStatus": "not_required",
                "createdAt": "2026-09-28T00:00:00Z",
            },
            _boundary_metadata("p0-create-loop"),
        )
        stream = DriverRunAggregate.stream_id(run_id)
        # Round 1: full dispatch.
        for seq, boundary in enumerate(
            ("prepared", "request_started", "response_started", "response_completed")
        ):
            svc.record_driver_dispatch_boundary(
                run_id, boundary, _boundary_metadata("p0-loop-r1-%d" % seq))
        # Round 2: the tool loop re-opens the request. Each record carries a
        # fresh sequence so the store appends a distinct event.
        for seq, boundary in enumerate(("request_started", "response_started")):
            svc.record_driver_dispatch_boundary(
                run_id, boundary, _boundary_metadata("p0-loop-r2-%d" % seq))
        durable = runtime.store.require_state(stream)
        assert durable["dispatchBoundary"] == "response_started"
        events = [
            e for e in runtime.store.read_stream(stream)
            if e.get("payload", {}).get("eventType") == "DriverRunDispatchBoundaryRecorded"
        ]
        assert len(events) == 6
        assert [e["payload"]["dispatchBoundary"] for e in events] == [
            "prepared", "request_started", "response_started", "response_completed",
            "request_started", "response_started",
        ]
    finally:
        runtime.close()
