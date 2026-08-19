from __future__ import annotations

from copy import deepcopy

import pytest

from capt_runtime.errors import CapabilityDenied, IdempotencyConflict
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.tool_broker import ToolBroker, tool_request_fingerprint
from capt_runtime.tools.registry import ToolRegistry

NOW = "2026-08-19T10:00:00Z"


class FakeAdapter:
    adapter_id = "adapter-test-tool"
    supports_reconciliation = False

    def __init__(self) -> None:
        self.calls = 0
        self.reconcile_calls = 0
        self.status = "succeeded"

    def execute(self, request: dict) -> dict:
        self.calls += 1
        return {
            "status": self.status,
            "exitCode": 0 if self.status == "succeeded" else None,
            "output": [{"kind": "string", "name": "message", "value": "hello"}],
            "sideEffectIdentity": "effect-test-1" if self.status != "indeterminate" else None,
            "error": None,
            "reconciliationReason": "adapter could not determine effect" if self.status == "indeterminate" else None,
        }


class SpyRuntime(RuntimeService):
    def __init__(self, store: EventStore) -> None:
        super().__init__(store)
        self.checks: list[tuple] = []
        self.reservations: list[dict] = []
        self.finalizations: list[dict] = []
        self.deny_checks = False

    def check_lease(self, grant_id, lease_id, operation, scope, now):
        self.checks.append((grant_id, lease_id, operation, deepcopy(scope), now))
        if self.deny_checks:
            raise CapabilityDenied("revoked", lease_id)

    def reserve_use(self, grant_id, reservation, metadata):
        self.reservations.append(deepcopy(reservation))
        return {"status": "accepted"}

    def finalize_use(self, grant_id, consumption, metadata):
        self.finalizations.append(deepcopy(consumption))
        return {"status": "accepted"}


def _descriptor() -> dict:
    return {
        "schemaVersion": "1.0.0", "toolId": "test.tool", "displayName": "Test Tool",
        "family": "test", "operations": ["test.read", "test.write"],
        "requiredCapabilities": ["test.read", "test.write"],
        "operationEffects": [
            {"operation": "test.read", "effectClass": "pure_read_only"},
            {"operation": "test.write", "effectClass": "durable_local"},
        ],
        "terminalBackends": ["local"], "platforms": ["macos", "linux"],
        "supportsTimeout": True, "supportsCancellation": True,
        "idempotencySupport": "broker_settled_replay", "artifactOutputs": [],
    }


def _request(operation: str = "test.read", *, idem: str = "idem-test-1", with_lease: bool = True) -> dict:
    consequential = operation == "test.write"
    request = {
        "schemaVersion": "1.0.0", "toolRequestId": "tool-request-1",
        "toolId": "test.tool", "operation": operation,
        "arguments": [{"kind": "string", "name": "payload", "value": "hello"}],
        "consequential": consequential,
        "grantId": "grant-test-1" if with_lease else None,
        "leaseId": "lease-test-1" if with_lease else None,
        "reservationId": None, "backendId": "local",
        "targetIdentity": "/tmp/work/file.txt", "filesystemScope": "/tmp/work",
        "idempotencyKey": idem, "operationFingerprint": "sha256:" + "0" * 64,
        "replayPolicy": "never", "requestedAt": NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _broker(tmp_path):
    store = EventStore(str(tmp_path / "runtime.db"))
    runtime = SpyRuntime(store)
    registry = ToolRegistry()
    adapter = FakeAdapter()
    registry.register(
        _descriptor(), adapter,
        lambda: {"schemaVersion": "1.0.0", "toolId": "test.tool", "status": "available", "reason": "test adapter ready", "checkedAt": NOW},
    )
    broker = ToolBroker(runtime, registry, now=lambda: NOW)
    return store, runtime, registry, adapter, broker


def test_exact_settled_replay_never_invokes_adapter_twice(tmp_path) -> None:
    store, _runtime, _registry, adapter, broker = _broker(tmp_path)
    try:
        first = broker.execute(_request(), operator_id="op", session_id="s")
        second = broker.execute(_request(), operator_id="op", session_id="s")
        assert first["toolExecutionId"] == second["toolExecutionId"]
        assert first["result"] == second["result"]
        assert second["replayed"] is True
        assert adapter.calls == 1
        state = store.require_state("tool_execution-" + first["toolExecutionId"])
        assert state["operatorId"] == "op" and state["sessionId"] == "s"
    finally:
        store.close()


def test_same_idempotency_key_changed_request_fails_closed(tmp_path) -> None:
    store, _runtime, _registry, adapter, broker = _broker(tmp_path)
    try:
        broker.execute(_request(), operator_id="op", session_id="s")
        changed = _request(operation="test.write", idem="idem-test-1", with_lease=True)
        with pytest.raises(IdempotencyConflict):
            broker.execute(changed, operator_id="op", session_id="s")
        assert adapter.calls == 1
    finally:
        store.close()


def test_consequential_tool_requires_bound_lease_before_dispatch(tmp_path) -> None:
    store, runtime, _registry, adapter, broker = _broker(tmp_path)
    try:
        with pytest.raises(CapabilityDenied):
            broker.execute(_request(operation="test.write", with_lease=False), operator_id="op", session_id="s")
        assert runtime.checks == []
        assert adapter.calls == 0
    finally:
        store.close()


def test_consequential_tool_checks_reserves_and_finalizes_live_lease(tmp_path) -> None:
    store, runtime, _registry, adapter, broker = _broker(tmp_path)
    try:
        result = broker.execute(
            _request(operation="test.write", with_lease=True), operator_id="op", session_id="s"
        )
        assert result["status"] == "succeeded"
        assert len(runtime.checks) == 1
        assert len(runtime.reservations) == 1
        assert runtime.reservations[0]["state"] == "open"
        assert runtime.finalizations[0]["outcome"] == "succeeded"
        assert adapter.calls == 1
    finally:
        store.close()


def test_indeterminate_result_consumes_reservation_without_redispatch(tmp_path) -> None:
    store, runtime, _registry, adapter, broker = _broker(tmp_path)
    try:
        adapter.status = "indeterminate"
        request = _request(operation="test.write", with_lease=True)
        result = broker.execute(request, operator_id="op", session_id="s")
        assert result["status"] == "indeterminate"
        assert runtime.finalizations[0]["outcome"] == "indeterminate"
        replay = broker.execute(request, operator_id="op", session_id="s")
        assert replay["status"] == "indeterminate"
        assert replay["replayed"] is True
        assert adapter.calls == 1
    finally:
        store.close()


def test_restart_never_blindly_redispatches_dispatching_execution(tmp_path) -> None:
    store, runtime, registry, adapter, broker = _broker(tmp_path)
    try:
        request = _request()
        execution = broker.build_execution(request, operator_id="op", session_id="s")
        runtime.prepare_tool_execution(execution, broker.metadata(execution["toolExecutionId"], "prepared"))
        runtime.transition_tool_execution(
            execution["toolExecutionId"], "admitted", {}, broker.metadata(execution["toolExecutionId"], "admitted")
        )
        runtime.transition_tool_execution(
            execution["toolExecutionId"], "dispatching", {"dispatchBoundary": "started"},
            broker.metadata(execution["toolExecutionId"], "dispatching"),
        )
        restarted = ToolBroker(SpyRuntime(store), registry, now=lambda: NOW)
        recovered = restarted.reconcile_stranded()
        assert recovered[0]["state"] == "indeterminate"
        assert adapter.calls == 0
        state = store.require_state("tool_execution-" + execution["toolExecutionId"])
        assert state["state"] == "indeterminate"
    finally:
        store.close()


def test_live_lease_denial_never_reaches_adapter(tmp_path) -> None:
    store, runtime, _registry, adapter, broker = _broker(tmp_path)
    try:
        runtime.deny_checks = True
        result = broker.execute(
            _request(operation="test.write", with_lease=True), operator_id="op", session_id="s"
        )
        assert result["status"] == "denied"
        assert adapter.calls == 0
        assert runtime.reservations == []
        replay = broker.execute(
            _request(operation="test.write", with_lease=True), operator_id="op", session_id="s"
        )
        assert replay["status"] == "denied"
        assert replay["replayed"] is True
    finally:
        store.close()
