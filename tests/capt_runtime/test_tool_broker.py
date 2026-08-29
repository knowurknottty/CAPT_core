from __future__ import annotations

from copy import deepcopy

import pytest

from capt_runtime.errors import (
    AuthorityViolation,
    CapabilityDenied,
    IdempotencyConflict,
)
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
        self.preflight_calls = 0
        self.preflight_error = None
        self.status = "succeeded"

    def preflight(self, request: dict) -> None:
        self.preflight_calls += 1
        if self.preflight_error is not None:
            raise self.preflight_error

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


def test_request_specific_preflight_denial_happens_before_reservation_or_dispatch(tmp_path) -> None:
    store, runtime, _registry, adapter, broker = _broker(tmp_path)
    try:
        adapter.preflight_error = AuthorityViolation("SSH network policy denied target")
        result = broker.execute(
            _request(operation="test.write", with_lease=True), operator_id="op", session_id="s"
        )
        assert result["status"] == "denied"
        assert adapter.preflight_calls == 1
        assert adapter.calls == 0
        assert runtime.reservations == []
        assert runtime.finalizations == []
        state = store.require_state("tool_execution-" + result["toolExecutionId"])
        assert state["state"] == "failed"
        assert state["dispatchBoundary"] == "not_started"
        assert state["reservationId"] is None
    finally:
        store.close()


class EffectObservedCrashAdapter(FakeAdapter):
    adapter_id = "adapter-effect-observed-crash"

    def execute_observed(self, request: dict, observe_effect) -> dict:
        self.calls += 1
        observe_effect('{"containerId":"ctr-test-1","imageId":"sha256:image-test-1"}')
        raise RuntimeError("crash after durable external identity became known")


def test_effect_identity_is_durable_before_adapter_returns_or_crashes(tmp_path) -> None:
    store = EventStore(str(tmp_path / "runtime.db"))
    runtime = SpyRuntime(store)
    registry = ToolRegistry()
    adapter = EffectObservedCrashAdapter()
    registry.register(
        _descriptor(),
        adapter,
        lambda: {
            "schemaVersion": "1.0.0",
            "toolId": "test.tool",
            "status": "available",
            "reason": "observed-effect adapter ready",
            "checkedAt": NOW,
        },
    )
    broker = ToolBroker(runtime, registry, now=lambda: NOW)
    try:
        result = broker.execute(
            _request(operation="test.write", with_lease=True),
            operator_id="op",
            session_id="s",
        )
        assert result["status"] == "indeterminate"
        state = store.require_state("tool_execution-" + result["toolExecutionId"])
        assert state["state"] == "indeterminate"
        assert state["dispatchBoundary"] == "effect_observed"
        assert state["sideEffectIdentity"] == '{"containerId":"ctr-test-1","imageId":"sha256:image-test-1"}'
        assert result["result"]["sideEffectIdentity"] == state["sideEffectIdentity"]
        assert runtime.finalizations[0]["sideEffectIdentity"] == state["sideEffectIdentity"]
    finally:
        store.close()


def test_missing_tool_during_recovery_does_not_block_other_stranded_executions(tmp_path) -> None:
    store, runtime, _registry, adapter, broker = _broker(tmp_path)
    try:
        missing_request = _request(idem="idem-missing-tool")
        missing = broker.build_execution(
            missing_request, operator_id="op", session_id="s"
        )
        missing["toolId"] = "missing.tool"
        missing["adapterId"] = "adapter-missing-tool"
        runtime.prepare_tool_execution(
            missing, broker.metadata(missing["toolExecutionId"], "prepared")
        )
        runtime.transition_tool_execution(
            missing["toolExecutionId"], "admitted", {},
            broker.metadata(missing["toolExecutionId"], "admitted"),
        )
        runtime.transition_tool_execution(
            missing["toolExecutionId"], "dispatching", {"dispatchBoundary": "started"},
            broker.metadata(missing["toolExecutionId"], "dispatching"),
        )

        known_request = _request(idem="idem-known-tool")
        known = broker.build_execution(known_request, operator_id="op", session_id="s")
        runtime.prepare_tool_execution(
            known, broker.metadata(known["toolExecutionId"], "prepared")
        )
        runtime.transition_tool_execution(
            known["toolExecutionId"], "admitted", {},
            broker.metadata(known["toolExecutionId"], "admitted"),
        )
        runtime.transition_tool_execution(
            known["toolExecutionId"], "dispatching", {"dispatchBoundary": "started"},
            broker.metadata(known["toolExecutionId"], "dispatching"),
        )

        recovered = broker.reconcile_stranded()
        by_id = {state["toolExecutionId"]: state for state in recovered}
        assert by_id[missing["toolExecutionId"]]["state"] == "indeterminate"
        assert "not available for reconciliation" in by_id[missing["toolExecutionId"]]["reconciliationReason"]
        assert by_id[known["toolExecutionId"]]["state"] == "indeterminate"
        assert adapter.calls == 0
    finally:
        store.close()
