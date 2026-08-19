from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.aggregates.tool_execution import ToolExecutionAggregate
from capt_runtime.contracts import digest
from capt_runtime.errors import AuthorityViolation, IllegalTransition
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore

NOW = "2026-08-19T10:00:00Z"


def _execution() -> dict:
    return {
        "schemaVersion": "1.0.0", "toolExecutionId": "tool-exec-1",
        "toolRequestId": "tool-req-1", "operatorId": "operator-1", "sessionId": "session-1", "toolId": "terminal.local",
        "operation": "terminal.exec",
        "operationFingerprint": digest({"operation": "terminal.exec", "argv": ["echo", "ok"]}),
        "descriptorDigest": digest({"toolId": "terminal.local"}),
        "adapterId": "adapter-terminal-local", "backendId": "local",
        "effectClass": "ephemeral_external", "consequential": False,
        "grantId": None, "leaseId": None, "reservationId": None,
        "state": "prepared", "dispatchBoundary": "not_started",
        "result": None, "resultDigest": None, "sideEffectIdentity": None,
        "settlementStatus": "not_settled", "reconciliationReason": None,
        "preparedAt": NOW, "updatedAt": NOW,
    }

def _metadata(command_id: str, actor_kind: str = "execution_plane") -> dict:
    return commands.command(
        command_id=command_id,
        idempotency_key=command_id,
        operation_fingerprint=commands.fingerprint(command_id, {"execution": "tool-exec-1"}),
        correlation_id="corr-tool-1",
        actor_id="exec-tool-1",
        actor_kind=actor_kind,
        issued_at=NOW,
    )


def _tool_result() -> dict:
    output = [{"kind": "string", "name": "stdout", "value": "ok"}]
    return {
        "schemaVersion": "1.0.0", "toolResultId": "tool-result-1",
        "toolRequestId": "tool-req-1", "status": "succeeded", "output": output,
        "exitCode": 0, "outputDigest": digest(output), "sideEffectIdentity": None,
        "error": None, "completedAt": NOW,
    }


def _settle(state: dict, result_digest: str) -> dict:
    result = _tool_result()
    state = ToolExecutionAggregate.transition(state, "settling", {
        "result": result, "resultDigest": result_digest, "settlementStatus": "settling",
        "dispatchBoundary": "response_completed",
    })
    return ToolExecutionAggregate.transition(state, "completed", {
        "result": result, "resultDigest": result_digest, "settlementStatus": "settled",
        "dispatchBoundary": "response_completed",
    })


def test_tool_execution_lifecycle_is_monotonic() -> None:
    result_digest = digest({"status": "succeeded"})
    state = ToolExecutionAggregate.create(_execution())
    state = ToolExecutionAggregate.transition(state, "admitted", {})
    state = ToolExecutionAggregate.transition(state, "dispatching", {"dispatchBoundary": "started"})
    state = _settle(state, result_digest)
    assert state["state"] == "completed"
    with pytest.raises(IllegalTransition):
        ToolExecutionAggregate.transition(state, "dispatching", {})

def test_dispatching_execution_can_be_marked_indeterminate() -> None:
    state = ToolExecutionAggregate.create(_execution())
    state = ToolExecutionAggregate.transition(state, "admitted", {})
    state = ToolExecutionAggregate.transition(state, "dispatching", {"dispatchBoundary": "started"})
    state = ToolExecutionAggregate.transition(state, "indeterminate", {
        "settlementStatus": "reconciliation_required",
        "reconciliationReason": "runtime restarted after dispatch boundary",
    })
    assert state["state"] == "indeterminate"


def test_completed_requires_persisted_settled_result() -> None:
    state = ToolExecutionAggregate.create(_execution())
    state = ToolExecutionAggregate.transition(state, "admitted", {})
    state = ToolExecutionAggregate.transition(state, "dispatching", {"dispatchBoundary": "started"})
    result_digest = digest({"status": "succeeded"})
    state = ToolExecutionAggregate.transition(state, "settling", {
        "resultDigest": result_digest, "settlementStatus": "settling",
    })
    with pytest.raises(IllegalTransition):
        ToolExecutionAggregate.transition(state, "completed", {
            "resultDigest": result_digest, "settlementStatus": "settled",
        })


def test_identity_fields_cannot_be_patched_during_transition() -> None:
    state = ToolExecutionAggregate.create(_execution())
    with pytest.raises(IllegalTransition):
        ToolExecutionAggregate.transition(state, "admitted", {"toolId": "file.operations"})


def test_runtime_service_persists_tool_execution_events(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db"))
    service = RuntimeService(store)
    try:
        execution = _execution()
        service.prepare_tool_execution(execution, _metadata("tool-prepare"))
        service.transition_tool_execution("tool-exec-1", "admitted", {}, _metadata("tool-admit"))
        service.transition_tool_execution(
            "tool-exec-1", "dispatching", {"dispatchBoundary": "started"}, _metadata("tool-dispatch")
        )
        state = store.require_state("tool_execution-tool-exec-1")
        assert state["state"] == "dispatching"
        assert [event["eventType"] for event in store.read_stream("tool_execution-tool-exec-1")] == [
            "ToolExecutionPrepared", "ToolExecutionAdmitted", "ToolExecutionDispatching",
        ]
    finally:
        store.close()


def test_runtime_service_tool_execution_requires_execution_authority(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db"))
    service = RuntimeService(store)
    try:
        with pytest.raises(AuthorityViolation):
            service.prepare_tool_execution(_execution(), _metadata("tool-human", "human"))
        assert store.head_sequence() == 0
    finally:
        store.close()
