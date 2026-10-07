"""P0.1 regression tests: the command-carried timestamp is untrusted provenance.

- Preparation fails closed on a missing / malformed / stale (>300s skew)
  command timestamp instead of trusting it as the authorization clock.
- Admission consumes authority at authoritative wall-clock time: ``consumedAt``
  is the runtime's own clock, the command timestamp is retained as evidence
  only, and expiry is enforced against the wall clock -- a stale command time
  cannot extend an expired approval.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from capt_runtime import commands
from capt_runtime.composition import create_runtime
from capt_runtime.errors import AuthorityViolation
from desktop.capt_runtime_service import (
    _COMMAND_TIMESTAMP_SKEW_BOUND_SECONDS,
    _check_command_timestamp_skew,
)
from desktop.m1_command_service import RuntimeCommandService


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- prepare-level skew gate -------------------------------------------

def test_missing_command_timestamp_fails_closed():
    with pytest.raises(AuthorityViolation, match="MODEL_COMMAND_TIMESTAMP_MISSING"):
        _check_command_timestamp_skew(None, _rfc3339(_now()))
    with pytest.raises(AuthorityViolation, match="MODEL_COMMAND_TIMESTAMP_MISSING"):
        _check_command_timestamp_skew("", _rfc3339(_now()))


def test_malformed_command_timestamp_fails_closed():
    with pytest.raises(AuthorityViolation, match="MODEL_COMMAND_TIMESTAMP_MALFORMED"):
        _check_command_timestamp_skew("not-a-time", _rfc3339(_now()))


def test_stale_command_timestamp_fails_closed():
    stale = _rfc3339(_now() - timedelta(seconds=_COMMAND_TIMESTAMP_SKEW_BOUND_SECONDS + 1))
    with pytest.raises(AuthorityViolation, match="MODEL_COMMAND_TIMESTAMP_SKEW"):
        _check_command_timestamp_skew(stale, _rfc3339(_now()))


def test_future_command_timestamp_fails_closed():
    future = _rfc3339(_now() + timedelta(seconds=_COMMAND_TIMESTAMP_SKEW_BOUND_SECONDS + 1))
    with pytest.raises(AuthorityViolation, match="MODEL_COMMAND_TIMESTAMP_SKEW"):
        _check_command_timestamp_skew(future, _rfc3339(_now()))


def test_fresh_command_timestamp_passes():
    fresh = _rfc3339(_now() - timedelta(seconds=60))
    _check_command_timestamp_skew(fresh, _rfc3339(_now()))  # must not raise


# ---- admission-level authoritative consumption ---------------------------

def _envelope(op: str, payload: dict, *, key: str, timestamp: str) -> dict:
    return {
        "commandId": "cmd-" + key,
        "operatorId": "operator-p0",
        "sessionId": "sess-p0",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-" + key,
        "idempotencyKey": "idem-" + key,
        "timestamp": timestamp,
        "op": op,
        "payload": payload,
    }


def _approved_plan(svc: RuntimeCommandService, key: str, *, expires_at: str) -> dict:
    request = svc.execute(_envelope(
        "request_model_prompt_approval",
        {"objective": "p0 objective", "targetRoot": "/tmp", "expiresAt": expires_at},
        key=key + "-request", timestamp=_rfc3339(_now()),
    ))
    assert request["status"] == "accepted", request
    planned = request["result"]
    decision = svc.execute(_envelope(
        "submit_approval_decision",
        {"requestId": planned["requestId"], "decision": "approve"},
        key=key + "-decision", timestamp=_rfc3339(_now()),
    ))
    assert decision["status"] == "accepted", decision
    return planned


def _admit_metadata(key: str) -> dict:
    return commands.command(
        command_id="cmd-" + key,
        idempotency_key="idem-" + key,
        operation_fingerprint=commands.fingerprint("p0-admit", {"key": key}),
        correlation_id="corr-" + key,
        actor_id="exec-1",
        actor_kind="execution_plane",
        issued_at=_rfc3339(_now()),
        replay_policy="never",
    )


def test_admission_consumes_at_authoritative_wall_clock(tmp_path: Path):
    """consumedAt is the runtime clock, not the command's stale issued_at."""
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(
            runtime.store, "operator-p0", "sess-p0", runtime_service=runtime.service)
        planned = _approved_plan(
            svc, "p0-wallclock",
            expires_at=_rfc3339(_now() + timedelta(days=1)))
        approval = svc.store.require_state("human_approval-" + planned["requestId"])
        stale_issued_at = _rfc3339(_now() - timedelta(minutes=10))
        receipt = runtime.service.admit_approved_model_execution(
            planned["requestId"],
            approval["promptAssemblyDigest"],
            approval["operation"],
            mission_id=planned["missionId"],
            task_id=planned["taskId"],
            driver_run_id=planned["driverRunId"],
            resource=approval["resource"],
            use_id="use-p0-wallclock",
            now=stale_issued_at,
            metadata=_admit_metadata("p0-wallclock"),
        )
        assert receipt["driverRunId"] == planned["driverRunId"]
        state = svc.store.require_state("human_approval-" + planned["requestId"])
        assert state["state"] == "consumed"
        assert state["consumedBy"] == "use-p0-wallclock"
        # The durable consumption time is authoritative wall-clock time...
        skew = abs(
            (datetime.fromisoformat(state["consumedAt"].replace("Z", "+00:00"))
             - _now()).total_seconds())
        assert skew < 120, state["consumedAt"]
        # ...not the stale command-carried timestamp, which is kept as evidence
        # on the HumanApprovalConsumed event (not the aggregate state).
        assert state["consumedAt"] != stale_issued_at
        events = svc.store.read_stream("human_approval-" + planned["requestId"])
        consumed = [e for e in events
                    if e.get("payload", {}).get("eventType") == "HumanApprovalConsumed"]
        assert len(consumed) == 1
        assert consumed[0]["payload"]["consumption"]["commandIssuedAt"] == stale_issued_at
    finally:
        runtime.close()


def test_admission_rejects_wall_clock_expired_approval(tmp_path: Path):
    """An approval expired by the wall clock cannot be revived by a stale
    command timestamp that predates the expiry (the P0.1 vulnerability).

    The approval is approved while valid, then allowed to expire by the wall
    clock. The command carries a timestamp from before the expiry -- the old
    code trusted that timestamp and admitted; the fixed code enforces expiry
    against authoritative wall-clock time.
    """
    import time

    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        svc = RuntimeCommandService(
            runtime.store, "operator-p0", "sess-p0", runtime_service=runtime.service)
        planned = _approved_plan(
            svc, "p0-expired",
            expires_at=_rfc3339(_now() + timedelta(seconds=10)))
        approval = svc.store.require_state("human_approval-" + planned["requestId"])
        # The command claims it was issued before the approval expired.
        stale_issued_at = _rfc3339(_now() - timedelta(seconds=60))
        # Let the approval expire by the wall clock.
        time.sleep(11)
        with pytest.raises(AuthorityViolation, match="MODEL_PROMPT_APPROVAL_EXPIRED"):
            runtime.service.admit_approved_model_execution(
                planned["requestId"],
                approval["promptAssemblyDigest"],
                approval["operation"],
                mission_id=planned["missionId"],
                task_id=planned["taskId"],
                driver_run_id=planned["driverRunId"],
                resource=approval["resource"],
                use_id="use-p0-expired",
                now=stale_issued_at,
                metadata=_admit_metadata("p0-expired"),
            )
        # The approval is untouched: still approved, never consumed.
        state = svc.store.require_state("human_approval-" + planned["requestId"])
        assert state["state"] == "approved"
    finally:
        runtime.close()
