from __future__ import annotations

import pytest

from capt_runtime.tools.registry import (
    DuplicateToolId,
    InvalidToolDescriptor,
    ToolRegistry,
    UnknownToolId,
)


def _descriptor(tool_id: str = "terminal.local") -> dict:
    return {
        "schemaVersion": "1.0.0",
        "toolId": tool_id,
        "displayName": "Terminal & Processes",
        "family": "terminal",
        "operations": ["terminal.exec"],
        "requiredCapabilities": ["terminal.exec"],
        "operationEffects": [{"operation": "terminal.exec", "effectClass": "durable_local"}],
        "terminalBackends": ["local"],
        "platforms": ["macos", "linux"],
        "supportsTimeout": True,
        "supportsCancellation": True,
        "idempotencySupport": "broker_settled_replay",
        "artifactOutputs": [],
    }


def _available(tool_id: str) -> dict:
    return {"schemaVersion": "1.0.0", "toolId": tool_id, "status": "available", "reason": "ready", "checkedAt": "2026-08-19T10:00:00Z"}


def test_registry_rejects_duplicate_tool_id() -> None:
    reg = ToolRegistry()
    reg.register(_descriptor(), object(), lambda: _available("terminal.local"))
    with pytest.raises(DuplicateToolId):
        reg.register(_descriptor(), object(), lambda: _available("terminal.local"))


def test_probe_failure_is_unavailable_not_pass() -> None:
    reg = ToolRegistry()
    reg.register(_descriptor(), object(), lambda: (_ for _ in ()).throw(OSError("missing executable")))
    readiness = reg.readiness("terminal.local")
    assert readiness["status"] == "unavailable"
    assert "OSError" in readiness["reason"]


def test_missing_probe_is_unverified() -> None:
    reg = ToolRegistry()
    reg.register(_descriptor(), object())
    assert reg.readiness("terminal.local")["status"] == "unverified"


def test_unknown_tool_fails_closed() -> None:
    reg = ToolRegistry()
    with pytest.raises(UnknownToolId):
        reg.require("not.registered")


def test_operation_effects_must_cover_operations_exactly() -> None:
    reg = ToolRegistry()
    desc = _descriptor()
    desc["operationEffects"] = [{"operation": "terminal.other", "effectClass": "ephemeral_external"}]
    with pytest.raises(InvalidToolDescriptor):
        reg.register(desc, object())


def test_descriptor_is_copied_at_registration_boundary() -> None:
    reg = ToolRegistry()
    desc = _descriptor()
    reg.register(desc, object(), lambda: _available("terminal.local"))
    desc["displayName"] = "mutated"
    assert reg.require("terminal.local")["descriptor"]["displayName"] == "Terminal & Processes"


def test_slice_a_builtin_descriptors_are_exact() -> None:
    from capt_runtime.tools.builtins import SLICE_A_DESCRIPTORS

    by_id = {d["toolId"]: d for d in SLICE_A_DESCRIPTORS}
    assert set(by_id) == {"terminal.local", "file.operations", "code.execution"}
    assert by_id["terminal.local"]["operationEffects"] == [
        {"operation": "terminal.exec", "effectClass": "durable_local"}
    ]
    assert by_id["file.operations"]["operationEffects"] == [
        {"operation": "file.read", "effectClass": "pure_read_only"},
        {"operation": "file.write", "effectClass": "durable_local"},
    ]
    assert by_id["code.execution"]["operationEffects"] == [
        {"operation": "code.execute_python", "effectClass": "durable_local"}
    ]
    assert all(d["terminalBackends"] == ["local"] for d in by_id.values())
