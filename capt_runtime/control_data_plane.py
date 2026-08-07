"""Control-plane / data-plane classification (ADR-DT-PLANE-CONV, Gate 12).

Tags every command, API, event, channel, and process as control-plane or
data-plane, and enforces the separation rules:

  Control-plane (stronger identity, auditing, idempotency, explicit receipts,
  stricter rate limits, narrower channels):
    mission creation, policy updates, approval, cancellation, capability issuance,
    driver registration, model promotion, memory-trigger policy, runtime config.

  Data-plane (throughput control, quotas, backpressure, isolation, bounded retries):
    inference, retrieval, tool execution, artifact transfer, memory reads,
    event streaming, trajectory storage, bulk evidence processing.

Privileged control commands must NOT be routed through permissive bulk-data
channels.
"""

from __future__ import annotations

from typing import Any, Dict

from .errors import AuthorityViolation

CONTROL_PLANE_OPS = frozenset({
    "CreateMission", "UpdatePolicy", "ApproveRequest", "CancelTask",
    "IssueCapability", "RegisterDriver", "PromoteModel", "UpdateMemoryTriggerPolicy",
    "UpdateRuntimeConfig", "RevokeIdentity", "RevokeDelegation",
})

DATA_PLANE_OPS = frozenset({
    "RepositoryRead", "RepositoryWrite", "Inference", "RetrieveMemory",
    "ToolExecution", "ArtifactTransfer", "StreamEvents", "StoreTrajectory",
    "ProcessEvidenceBulk",
})

# Permissive bulk-data channels that must never carry privileged control commands.
PERMISSIVE_BULK_CHANNELS = frozenset({"event-stream", "bulk-evidence", "telemetry"})


def classify(operation: str) -> str:
    if operation in CONTROL_PLANE_OPS:
        return "control"
    if operation in DATA_PLANE_OPS:
        return "data"
    # Unknown operations default to control-plane (fail closed: require explicit
    # classification before granting data-plane privileges).
    return "control"


def tag_command(command: Dict[str, Any]) -> Dict[str, Any]:
    op = command.get("operation") or command.get("kind") or command.get("eventType")
    plane = classify(op)
    tagged = dict(command)
    tagged["plane"] = plane
    return tagged


def assert_control_not_on_permissive_channel(operation: str, channel: str) -> None:
    """Reject privileged control commands routed over permissive bulk-data channels."""
    if classify(operation) == "control" and channel in PERMISSIVE_BULK_CHANNELS:
        raise AuthorityViolation(
            "control-plane operation %r must not be routed over permissive channel %r"
            % (operation, channel))
