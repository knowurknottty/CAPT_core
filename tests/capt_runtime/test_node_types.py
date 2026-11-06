from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from capt_runtime.node.types import (
    NodeOperationRequest,
    NodeOperationState,
    OperationCapability,
    canonical_request_digest,
)


def _now() -> datetime:
    return datetime(2026, 9, 8, 19, 30, tzinfo=timezone.utc)


def _capability(**overrides) -> OperationCapability:
    values = {
        "capability_id": "cap-1",
        "bot_id": "bot-builder",
        "mission_id": "mission-node",
        "task_id": "task-1",
        "controller_id": "controller-1",
        "node_id": "node-1",
        "permitted_operations": frozenset({"shell.exec"}),
        "filesystem_roots": ("/tmp/capt-workspace",),
        "issued_at": _now(),
        "expires_at": _now() + timedelta(minutes=5),
    }
    values.update(overrides)
    return OperationCapability(**values)

def test_request_digest_is_canonical_across_argument_order():
    cap = _capability()
    left = NodeOperationRequest(
        operation_id="op-1", capability=cap, operation="shell.exec",
        arguments={"argv": ["echo", "hi"], "cwd": "/tmp/capt-workspace"},
        issued_at=_now(),
    )
    right = NodeOperationRequest(
        operation_id="op-1", capability=cap, operation="shell.exec",
        arguments={"cwd": "/tmp/capt-workspace", "argv": ["echo", "hi"]},
        issued_at=_now(),
    )
    assert canonical_request_digest(left) == canonical_request_digest(right)


def test_capability_enforces_operation_and_expiry():
    cap = _capability()
    cap.require_authorized("shell.exec", node_id="node-1", controller_id="controller-1", at=_now())
    with pytest.raises(PermissionError, match="operation_not_permitted"):
        cap.require_authorized("filesystem.write", node_id="node-1", controller_id="controller-1", at=_now())
    with pytest.raises(PermissionError, match="capability_expired"):
        cap.require_authorized("shell.exec", node_id="node-1", controller_id="controller-1", at=cap.expires_at)


def test_generic_states_are_not_representable():
    assert "error" not in {state.value for state in NodeOperationState}
    assert "unknown" not in {state.value for state in NodeOperationState}
    with pytest.raises(ValueError):
        NodeOperationState("error")


def test_result_requires_specific_state_and_no_generic_error_channel():
    from capt_runtime.node.types import NodeOperationResult

    result = NodeOperationResult(
        operation_id="op-1",
        state=NodeOperationState.FAILED,
        evidence={"exit_code": 2},
        specific_reason="process_exit_nonzero",
    )
    assert result.state is NodeOperationState.FAILED
    assert result.specific_reason == "process_exit_nonzero"


def test_integrity_violation_has_specific_code():
    from capt_runtime.node.integrity import NodeIntegrityViolation

    exc = NodeIntegrityViolation("request_digest_mismatch", operation_id="op-1")
    assert exc.code == "request_digest_mismatch"
    assert exc.operation_id == "op-1"
