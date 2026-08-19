"""Normative Slice-A built-in tool descriptors.

Descriptors advertise only implemented execution families. Readiness is supplied
by the concrete adapter/backend wiring, not by these metadata constants.
"""

from __future__ import annotations

TERMINAL_LOCAL_DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "toolId": "terminal.local",
    "displayName": "Terminal & Processes",
    "family": "terminal",
    "operations": ["terminal.exec"],
    "requiredCapabilities": ["terminal.exec"],
    "operationEffects": [
        {"operation": "terminal.exec", "effectClass": "durable_local"},
    ],
    "terminalBackends": ["local"],
    "platforms": ["macos", "linux"],
    "supportsTimeout": True,
    "supportsCancellation": True,
    "idempotencySupport": "broker_settled_replay",
    "artifactOutputs": ["stdout", "stderr"],
}

FILE_OPERATIONS_DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "toolId": "file.operations",
    "displayName": "File Operations",
    "family": "file",
    "operations": ["file.read", "file.search", "file.write", "file.patch"],
    "requiredCapabilities": ["file.read", "file.search", "file.write", "file.patch"],
    "operationEffects": [
        {"operation": "file.read", "effectClass": "pure_read_only"},
        {"operation": "file.search", "effectClass": "pure_read_only"},
        {"operation": "file.write", "effectClass": "durable_local"},
        {"operation": "file.patch", "effectClass": "durable_local"},
    ],
    "terminalBackends": ["local"],
    "platforms": ["macos", "linux"],
    "supportsTimeout": False,
    "supportsCancellation": False,
    "idempotencySupport": "broker_settled_replay",
    "artifactOutputs": ["file_digest", "byte_count", "search_matches", "replacement_count"],
}

CODE_EXECUTION_DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "toolId": "code.execution",
    "displayName": "Code Execution",
    "family": "code_execution",
    "operations": ["code.execute_python"],
    "requiredCapabilities": ["code.execute_python"],
    "operationEffects": [
        {"operation": "code.execute_python", "effectClass": "durable_local"},
    ],
    "terminalBackends": ["local"],
    "platforms": ["macos", "linux"],
    "supportsTimeout": True,
    "supportsCancellation": True,
    "idempotencySupport": "broker_settled_replay",
    "artifactOutputs": ["stdout", "stderr"],
}

SLICE_A_DESCRIPTORS = (
    TERMINAL_LOCAL_DESCRIPTOR,
    FILE_OPERATIONS_DESCRIPTOR,
    CODE_EXECUTION_DESCRIPTOR,
)
