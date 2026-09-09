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

TERMINAL_SSH_DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "toolId": "terminal.ssh",
    "displayName": "SSH Terminal",
    "family": "terminal",
    "operations": ["terminal.exec"],
    "requiredCapabilities": ["terminal.exec"],
    "operationEffects": [
        {"operation": "terminal.exec", "effectClass": "durable_remote"},
    ],
    "terminalBackends": ["ssh"],
    "platforms": ["macos", "linux"],
    "supportsTimeout": True,
    "supportsCancellation": False,
    "idempotencySupport": "broker_settled_replay",
    "artifactOutputs": [
        "stdout", "stderr", "exit_code", "host_fingerprint", "profile_id", "remote_cwd"
    ],
}

TERMINAL_DOCKER_DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "toolId": "terminal.docker",
    "displayName": "Docker Terminal",
    "family": "terminal",
    "operations": ["terminal.exec"],
    "requiredCapabilities": ["terminal.exec"],
    "operationEffects": [
        {"operation": "terminal.exec", "effectClass": "durable_local"},
    ],
    "terminalBackends": ["docker"],
    "platforms": ["macos", "linux"],
    "supportsTimeout": True,
    "supportsCancellation": False,
    "idempotencySupport": "broker_settled_replay",
    "artifactOutputs": [
        "stdout", "stderr", "exit_code", "container_id", "image_id",
        "repo_digest", "cleanup_status"
    ],
}

TERMINAL_INVERSION_SANDBOX_DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "toolId": "terminal.inversion_sandbox",
    "displayName": "Inversion Sandbox Terminal",
    "family": "terminal",
    "operations": ["terminal.exec"],
    "requiredCapabilities": ["terminal.exec"],
    "operationEffects": [{"operation": "terminal.exec", "effectClass": "durable_local"}],
    "terminalBackends": ["inversion_sandbox"],
    "platforms": ["macos", "linux"],
    "supportsTimeout": True,
    "supportsCancellation": False,
    "idempotencySupport": "broker_settled_replay",
    "artifactOutputs": ["stdout", "stderr", "exit_code", "container_id", "image_id",
        "security_profile_digest", "network_policy_digest", "filesystem_scope_digest",
        "attestation_digest", "cleanup_status"],
}

SANDBOX_INVERSION_DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "toolId": "sandbox.inversion",
    "displayName": "Inversion Sandbox Lifecycle",
    "family": "sandbox",
    "operations": ["sandbox.create", "sandbox.inspect", "sandbox.close"],
    "requiredCapabilities": ["sandbox.create", "sandbox.inspect", "sandbox.close"],
    "operationEffects": [
        {"operation": "sandbox.create", "effectClass": "resource_creation"},
        {"operation": "sandbox.inspect", "effectClass": "pure_read_only"},
        {"operation": "sandbox.close", "effectClass": "durable_local"},
    ],
    "terminalBackends": ["inversion_sandbox"],
    "platforms": ["macos", "linux"],
    "supportsTimeout": False,
    "supportsCancellation": False,
    "idempotencySupport": "broker_settled_replay",
    "artifactOutputs": [
        "sandbox_lease_id", "state", "container_id", "identity_digest",
        "closure_receipt_digest", "observation"
    ],
}

TERMINAL_CLOUDFLARE_DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "toolId": "terminal.cloudflare",
    "displayName": "Cloudflare Sandbox Terminal",
    "family": "terminal",
    "operations": ["terminal.exec"],
    "requiredCapabilities": ["terminal.exec"],
    "operationEffects": [
        {"operation": "terminal.exec", "effectClass": "durable_remote"},
    ],
    "terminalBackends": ["cloudflare"],
    "platforms": ["linux"],
    "supportsTimeout": True,
    "supportsCancellation": False,
    "idempotencySupport": "broker_settled_replay",
    "artifactOutputs": [
        "stdout", "stderr", "exit_code", "sandbox_id", "profile_id", "remote_cwd", "cleanup_status"
    ],
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
    "idempotencySupport": "reconcile_before_retry",
    "worldReceiptOperations": ["file.write", "file.patch"],
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
