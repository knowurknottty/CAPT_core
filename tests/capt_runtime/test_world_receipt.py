from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.tool_broker import ToolBroker, tool_request_fingerprint
from capt_runtime.tools.adapters.file import FileToolAdapter
from capt_runtime.tools.builtins import FILE_OPERATIONS_DESCRIPTOR
from capt_runtime.tools.registry import ToolRegistry
from capt_runtime.world_receipt import build_effect_intent

NOW = "2026-08-29T20:00:00Z"


class ReceiptRuntime(RuntimeService):
    def __init__(self, store: EventStore) -> None:
        super().__init__(store)
        self.reservations: list[dict] = []
        self.finalizations: list[dict] = []

    def check_lease(self, grant_id, lease_id, operation, scope, now):
        return None
    def reserve_use(self, grant_id, reservation, metadata):
        self.reservations.append(deepcopy(reservation))
        return {"status": "accepted"}

    def finalize_use(self, grant_id, consumption, metadata):
        self.finalizations.append(deepcopy(consumption))
        return {"status": "accepted"}




class ReceiptBroker(ToolBroker):
    """Test broker with explicit fake authority lifetime; production never fabricates it."""

    def _effect_expiry(self, request):
        return "2026-08-29T20:15:00Z"


class CrashAfterReceiptFileAdapter(FileToolAdapter):
    def execute_world_effect(self, request, effect_intent, observe_effect):
        super().execute_world_effect(request, effect_intent, observe_effect)
        raise SystemExit("simulated crash after target receipt, before broker settle")


class CrashBeforeReceiptFileAdapter(FileToolAdapter):
    def _persist_world_receipt(self, receipt_path, receipt):
        raise SystemExit("simulated crash after target mutation, before receipt commit")


def _request(
    root: Path, target: Path, *, idem: str = "wr-file-1", content: str = "after"
) -> dict:
    request = {
        "schemaVersion": "1.0.0",
        "toolRequestId": "tool-request-world-receipt",
        "toolId": "file.operations",
        "operation": "file.write",
        "arguments": [
            {"kind": "path", "name": "path", "value": str(target)},
            {"kind": "string", "name": "content", "value": content},
        ],
        "consequential": True,
        "grantId": "grant-world-receipt",
        "leaseId": "lease-world-receipt",
        "reservationId": None,
        "backendId": "local",
        "targetIdentity": str(target),
        "filesystemScope": str(root),
        "idempotencyKey": idem,
        "operationFingerprint": "sha256:" + "0" * 64,
        "replayPolicy": "never",
        "requestedAt": NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _broker(tmp_path: Path, adapter: FileToolAdapter):
    store = EventStore(str(tmp_path / "runtime.db"))
    runtime = ReceiptRuntime(store)
    registry = ToolRegistry()
    registry.register(
        FILE_OPERATIONS_DESCRIPTOR,
        adapter,
        lambda: {
            "schemaVersion": "1.0.0",
            "toolId": "file.operations",
            "status": "available",
            "reason": "world receipt test adapter ready",
            "checkedAt": NOW,
        },
    )
    return store, runtime, registry, ReceiptBroker(runtime, registry, now=lambda: NOW)


def test_file_effect_settles_only_with_target_local_receipt(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    target.write_text("before", encoding="utf-8")
    store, runtime, _registry, broker = _broker(tmp_path, FileToolAdapter())
    try:
        result = broker.execute(_request(tmp_path, target), operator_id="operator", session_id="session")
        assert result["status"] == "succeeded"
        state = store.require_state("tool_execution-" + result["toolExecutionId"])
        receipt = state["worldReceipt"]
        intent = state["effectIntent"]
        assert state["state"] == "completed"
        assert receipt["intentDigest"] == intent["intentDigest"]
        assert receipt["observedStateDigest"] == intent["receiptSpec"]["expectedPostStateDigest"]
        assert Path(receipt["receiptLocator"]).is_file()
        assert target.read_text(encoding="utf-8") == "after"
        assert runtime.finalizations[-1]["outcome"] == "succeeded"
    finally:
        store.close()


def test_restart_settles_from_receipt_without_redispatch(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    target.write_text("before", encoding="utf-8")
    store, _runtime, _registry, broker = _broker(tmp_path, CrashAfterReceiptFileAdapter())
    request = _request(tmp_path, target, idem="wr-crash")
    try:
        with pytest.raises(SystemExit):
            broker.execute(request, operator_id="operator", session_id="session")
        stranded = store.require_state(
            "tool_execution-" + broker.execution_id(request["idempotencyKey"])
        )
        assert stranded["state"] == "effect_observed"
        assert target.read_text(encoding="utf-8") == "after"

        recovery_runtime = ReceiptRuntime(store)
        recovery_registry = ToolRegistry()
        recovery_registry.register(
            FILE_OPERATIONS_DESCRIPTOR,
            FileToolAdapter(),
            lambda: {
                "schemaVersion": "1.0.0",
                "toolId": "file.operations",
                "status": "available",
                "reason": "recovery adapter ready",
                "checkedAt": NOW,
            },
        )
        recovered = ToolBroker(
            recovery_runtime, recovery_registry, now=lambda: NOW
        ).reconcile_stranded()
        assert len(recovered) == 1
        assert recovered[0]["state"] == "completed"
        assert recovered[0]["result"]["status"] == "succeeded"
        assert recovery_runtime.finalizations[-1]["outcome"] == "succeeded"
    finally:
        store.close()


def test_tampered_target_receipt_never_settles_success(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    target.write_text("before", encoding="utf-8")
    store, _runtime, _registry, broker = _broker(tmp_path, CrashAfterReceiptFileAdapter())
    request = _request(tmp_path, target, idem="wr-tamper")
    try:
        with pytest.raises(SystemExit):
            broker.execute(request, operator_id="operator", session_id="session")
        stranded = store.require_state(
            "tool_execution-" + broker.execution_id(request["idempotencyKey"])
        )
        receipt_path = Path(stranded["effectIntent"]["receiptSpec"]["locator"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["intentDigest"] = "sha256:" + "f" * 64
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        recovery_runtime = ReceiptRuntime(store)
        recovery_registry = ToolRegistry()
        recovery_registry.register(
            FILE_OPERATIONS_DESCRIPTOR,
            FileToolAdapter(),
            lambda: {
                "schemaVersion": "1.0.0", "toolId": "file.operations",
                "status": "available", "reason": "recovery adapter ready",
                "checkedAt": NOW,
            },
        )
        recovered = ToolBroker(
            recovery_runtime, recovery_registry, now=lambda: NOW
        ).reconcile_stranded()
        assert recovered[0]["state"] == "indeterminate"
        assert recovered[0]["settlementStatus"] == "reconciliation_required"
    finally:
        store.close()


def test_effect_intent_refuses_fake_distributed_atomicity() -> None:
    request = {
        "operation": "file.write",
        "arguments": [{"kind": "string", "name": "payload", "value": "x"}],
        "grantId": "grant-test",
        "leaseId": "lease-test",
        "idempotencyKey": "idem-test",
        "requestedAt": NOW,
    }
    preparation = {
        "targetIdentity": "/tmp/a",
        "targetIdentities": ["/tmp/a", "/tmp/b"],
        "basisVersion": "absent",
        "atomicDomain": "fake-global-transaction",
        "coordinationMode": "atomic",
        "rollbackStrategy": "none",
        "reconciliationStrategy": "target_receipt",
        "receiptSpec": {
            "receiptKind": "file_sidecar",
            "targetLocal": True,
            "locator": "/tmp/a.capt-receipt.json",
            "expectedPostStateDigest": "sha256:" + "0" * 64,
        },
    }
    with pytest.raises(AuthorityViolation, match="FAKE_DISTRIBUTED_ATOMICITY"):
        build_effect_intent(
            request, principal_id="operator", preparation=preparation, expires_at=NOW
        )


def test_prepared_execution_resumes_same_intent_and_key(tmp_path: Path) -> None:
    target = tmp_path / "prepared.txt"
    target.write_text("before", encoding="utf-8")
    store, runtime, _registry, broker = _broker(tmp_path, FileToolAdapter())
    request = _request(tmp_path, target, idem="wr-prepared-resume")
    try:
        execution = broker.build_execution(
            request, operator_id="operator", session_id="session"
        )
        original_intent = deepcopy(execution["effectIntent"])
        runtime.prepare_tool_execution(
            execution, broker.metadata(execution["toolExecutionId"], "prepared")
        )
        result = broker.execute(
            request, operator_id="operator", session_id="session"
        )
        state = store.require_state("tool_execution-" + result["toolExecutionId"])
        assert result["status"] == "succeeded"
        assert state["effectIntent"] == original_intent
        assert len(runtime.reservations) == 1
        assert target.read_text(encoding="utf-8") == "after"
    finally:
        store.close()


def test_effect_intent_rejects_caller_target_mismatch(tmp_path: Path) -> None:
    target = tmp_path / "actual.txt"
    other = tmp_path / "offered.txt"
    target.write_text("before", encoding="utf-8")
    request = _request(tmp_path, other, idem="wr-target-mismatch")
    adapter = FileToolAdapter()
    preparation = adapter.prepare_effect(
        {**request, "arguments": [
            {"kind": "path", "name": "path", "value": str(target)},
            {"kind": "string", "name": "content", "value": "after"},
        ]}
    )
    with pytest.raises(AuthorityViolation, match="TARGET_IDENTITY_MISMATCH"):
        build_effect_intent(
            request, principal_id="operator", preparation=preparation, expires_at=NOW
        )


def test_prepared_effect_intent_expiry_denies_before_dispatch(tmp_path: Path) -> None:
    target = tmp_path / "expired.txt"
    target.write_text("before", encoding="utf-8")
    store, runtime, registry, broker = _broker(tmp_path, FileToolAdapter())
    request = _request(tmp_path, target, idem="wr-expired")
    try:
        execution = broker.build_execution(request, operator_id="operator", session_id="session")
        runtime.prepare_tool_execution(
            execution, broker.metadata(execution["toolExecutionId"], "prepared")
        )
        later = ToolBroker(runtime, registry, now=lambda: "2026-08-29T20:15:01Z")
        result = later.execute(request, operator_id="operator", session_id="session")
        assert result["status"] == "denied"
        assert target.read_text(encoding="utf-8") == "before"
        assert runtime.reservations == []
    finally:
        store.close()


def test_plain_file_effect_is_staged_with_real_reversal_escrow(tmp_path: Path) -> None:
    target = tmp_path / "staged.txt"
    target.write_text("before", encoding="utf-8")
    store, _runtime, _registry, broker = _broker(tmp_path, FileToolAdapter())
    try:
        result = broker.execute(
            _request(tmp_path, target, idem="wr-staged"),
            operator_id="operator", session_id="session",
        )
        state = store.require_state("tool_execution-" + result["toolExecutionId"])
        intent = state["effectIntent"]
        receipt = state["worldReceipt"]
        assert intent["coordinationMode"] == "staged"
        assert intent["rollbackStrategy"] == "escrow"
        reversal = Path(intent["reversalHandle"])
        assert reversal.is_file()
        assert reversal.read_text(encoding="utf-8") == "before"
        assert receipt["commitState"] == "committed"
        assert receipt["reversalHandle"] == str(reversal)
    finally:
        store.close()


def test_power_cut_between_target_and_receipt_stays_reversible_not_atomic(tmp_path: Path) -> None:
    target = tmp_path / "power-cut.txt"
    target.write_text("before", encoding="utf-8")
    store, _runtime, registry, broker = _broker(tmp_path, CrashBeforeReceiptFileAdapter())
    request = _request(tmp_path, target, idem="wr-mid-commit")
    try:
        with pytest.raises(SystemExit):
            broker.execute(request, operator_id="operator", session_id="session")
        state = store.require_state(
            "tool_execution-" + broker.execution_id(request["idempotencyKey"])
        )
        intent = state["effectIntent"]
        assert state["state"] == "dispatching"
        assert intent["coordinationMode"] == "staged"
        assert target.read_text(encoding="utf-8") == "after"
        assert not Path(intent["receiptSpec"]["locator"]).exists()
        assert Path(intent["reversalHandle"]).read_text(encoding="utf-8") == "before"

        recovery_runtime = ReceiptRuntime(store)
        recovered = ToolBroker(
            recovery_runtime, registry, now=lambda: NOW
        ).reconcile_stranded()
        assert recovered[0]["state"] == "indeterminate"
        assert recovery_runtime.finalizations[-1]["outcome"] == "indeterminate"
        assert "remains reversible" in recovered[0]["reconciliationReason"]
        assert str(intent["reversalHandle"]) in recovered[0]["reconciliationReason"]

        reversal = FileToolAdapter().reverse_world_effect(request, intent)
        assert reversal["restoredBasisVersion"] == intent["basisVersion"]
        assert target.read_text(encoding="utf-8") == "before"
    finally:
        store.close()


def test_world_receipts_are_unique_per_effect_and_do_not_overwrite_history(tmp_path: Path) -> None:
    target = tmp_path / "history.txt"
    target.write_text("zero", encoding="utf-8")
    store, _runtime, _registry, broker = _broker(tmp_path, FileToolAdapter())
    try:
        first = broker.execute(
            _request(tmp_path, target, idem="wr-history-1", content="one"),
            operator_id="operator", session_id="session",
        )
        first_state = store.require_state("tool_execution-" + first["toolExecutionId"])
        first_receipt = Path(first_state["worldReceipt"]["receiptLocator"])
        first_bytes = first_receipt.read_bytes()

        second = broker.execute(
            _request(tmp_path, target, idem="wr-history-2", content="two"),
            operator_id="operator", session_id="session",
        )
        second_state = store.require_state("tool_execution-" + second["toolExecutionId"])
        second_receipt = Path(second_state["worldReceipt"]["receiptLocator"])
        assert first_receipt != second_receipt
        assert first_receipt.read_bytes() == first_bytes
        assert second_receipt.is_file()
        assert target.read_text(encoding="utf-8") == "two"
    finally:
        store.close()


def test_tampered_receipt_id_is_rejected_during_recovery(tmp_path: Path) -> None:
    target = tmp_path / "receipt-id.txt"
    target.write_text("before", encoding="utf-8")
    store, _runtime, _registry, broker = _broker(tmp_path, CrashAfterReceiptFileAdapter())
    request = _request(tmp_path, target, idem="wr-receipt-id")
    try:
        with pytest.raises(SystemExit):
            broker.execute(request, operator_id="operator", session_id="session")
        stranded = store.require_state(
            "tool_execution-" + broker.execution_id(request["idempotencyKey"])
        )
        receipt_path = Path(stranded["effectIntent"]["receiptSpec"]["locator"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["receiptId"] = "world-receipt-forged"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        recovery_runtime = ReceiptRuntime(store)
        recovery_registry = ToolRegistry()
        recovery_registry.register(
            FILE_OPERATIONS_DESCRIPTOR,
            FileToolAdapter(),
            lambda: {
                "schemaVersion": "1.0.0", "toolId": "file.operations",
                "status": "available", "reason": "recovery adapter ready",
                "checkedAt": NOW,
            },
        )
        recovered = ToolBroker(
            recovery_runtime, recovery_registry, now=lambda: NOW
        ).reconcile_stranded()
        assert recovered[0]["state"] == "indeterminate"
        assert "RECEIPTID_MISMATCH" in recovered[0]["reconciliationReason"]
    finally:
        store.close()


def test_effect_intent_expiry_compares_timestamp_instants_not_strings(tmp_path: Path) -> None:
    target = tmp_path / "offset-expiry.txt"
    target.write_text("before", encoding="utf-8")
    request = _request(tmp_path, target, idem="wr-offset-expiry")
    preparation = FileToolAdapter().prepare_effect(request)
    # 15:00 at UTC-05:00 is exactly 20:00Z, so it is not a usable future window.
    with pytest.raises(AuthorityViolation, match="INTENT_EXPIRED_AT_PREPARE"):
        build_effect_intent(
            request,
            principal_id="operator",
            preparation=preparation,
            expires_at="2026-08-29T15:00:00-05:00",
        )
