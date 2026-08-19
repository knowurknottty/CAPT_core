from __future__ import annotations

import pytest

from capt_runtime.contracts import digest, known_types, require
from capt_runtime.errors import ContractViolation


def _descriptor() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "toolId": "terminal.local",
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


def test_tool_broker_contract_types_exist() -> None:
    names = set(known_types())
    assert {"ToolDescriptor", "ToolReadiness", "ToolEffectClass", "ToolExecutionState", "ToolExecution"} <= names

def test_tool_descriptor_is_closed_and_validated() -> None:
    require("ToolDescriptor", _descriptor())
    with pytest.raises(ContractViolation):
        require("ToolDescriptor", {**_descriptor(), "surpriseAuthority": True})


def test_tool_readiness_is_truthful_closed_enum() -> None:
    require("ToolReadiness", {
        "schemaVersion": "1.0.0", "toolId": "terminal.local",
        "status": "available", "reason": "local process backend ready",
        "checkedAt": "2026-08-19T10:00:00Z",
    })
    with pytest.raises(ContractViolation):
        require("ToolReadiness", {
            "schemaVersion": "1.0.0", "toolId": "terminal.local",
            "status": "probably_fine", "reason": "guess",
            "checkedAt": "2026-08-19T10:00:00Z",
        })


def _execution(state: str = "prepared") -> dict:
    return {
        "schemaVersion": "1.0.0",
        "toolExecutionId": "tool-exec-1",
        "toolRequestId": "tool-req-1",
        "operatorId": "operator-1", "sessionId": "session-1",
        "toolId": "terminal.local",
        "operation": "terminal.exec",
        "operationFingerprint": digest({"operation": "terminal.exec", "argv": ["echo", "ok"]}),
        "descriptorDigest": digest(_descriptor()),
        "adapterId": "adapter-terminal-local",
        "backendId": "local",
        "effectClass": "ephemeral_external",
        "consequential": False,
        "grantId": None,
        "leaseId": None,
        "reservationId": None,
        "state": state,
        "dispatchBoundary": "not_started",
        "result": None,
        "resultDigest": None,
        "sideEffectIdentity": None,
        "settlementStatus": "not_settled",
        "reconciliationReason": None,
        "preparedAt": "2026-08-19T10:00:00Z",
        "updatedAt": "2026-08-19T10:00:00Z",
    }


def test_tool_execution_state_is_closed() -> None:
    require("ToolExecution", _execution())
    with pytest.raises(ContractViolation):
        require("ToolExecution", _execution("trust_me_done"))


def test_tool_request_accepts_broker_authority_bindings() -> None:
    request = {
        "schemaVersion": "1.0.0", "toolRequestId": "tool-req-1", "toolId": "file.operations",
        "operation": "file.write", "arguments": [{"kind": "path", "name": "path", "value": "/tmp/x"}],
        "consequential": True, "grantId": "grant-1", "leaseId": "lease-1", "reservationId": None,
        "backendId": "local", "targetIdentity": "/tmp/x",
        "filesystemScope": "/tmp", "idempotencyKey": "tool-idem-1",
        "operationFingerprint": digest({"operation": "file.write", "path": "/tmp/x"}),
        "replayPolicy": "never", "requestedAt": "2026-08-19T10:00:00Z",
    }
    require("ToolRequest", request)


def test_tool_execution_event_payload_is_closed() -> None:
    require("ToolExecutionPreparedPayload", {
        "eventType": "ToolExecutionPrepared", "execution": _execution(),
    })
    with pytest.raises(ContractViolation):
        require("ToolExecutionPreparedPayload", {
            "eventType": "ToolExecutionPrepared", "execution": _execution(), "forged": True,
        })
