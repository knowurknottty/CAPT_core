"""Command envelope construction and deterministic fingerprinting (ADR-0108).

Operation fingerprints are content-addressed: same semantic operation ->
same fingerprint, regardless of when it is issued or by which process. This
is what lets a restarted process recognize that a pending operation is the
one it already attempted.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import digest, require

CONTRACT_SCHEMA_VERSION = "1.0.0"


def fingerprint(operation: str, subject: Dict[str, Any]) -> str:
    """Content digest over the operation and its semantically relevant inputs.

    Deliberately excludes commandId, attempt, and timestamps: a retry of the
    SAME operation must produce the SAME fingerprint, otherwise duplicate
    detection cannot work across process restarts.
    """
    return digest({"operation": operation, "subject": subject})


def command(
    command_id: str,
    idempotency_key: str,
    operation_fingerprint: str,
    correlation_id: str,
    actor_id: str,
    actor_kind: str,
    issued_at: str,
    replay_policy: str = "never",
    attempt: int = 1,
    causation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and validate a CommandMetadata envelope."""
    metadata = {
        "schemaVersion": CONTRACT_SCHEMA_VERSION,
        "commandId": command_id,
        "idempotencyKey": idempotency_key,
        "operationFingerprint": operation_fingerprint,
        "correlationId": correlation_id,
        "causationId": causation_id,
        "actor": {"actorId": actor_id, "kind": actor_kind, "displayName": None},
        "issuedAt": issued_at,
        "replayPolicy": replay_policy,
        "attempt": attempt,
    }
    require("CommandMetadata", metadata)
    return metadata


def envelope(
    event_id: str,
    stream_id: str,
    event_type: str,
    payload: Dict[str, Any],
    metadata: Dict[str, Any],
    occurred_at: str,
    mission_id: Optional[str] = None,
    task_id: Optional[str] = None,
    claim_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an EventEnvelope skeleton.

    streamVersion, globalSequence, and payloadDigest are intentionally left as
    placeholders: only the store may assign them, inside the commit
    transaction. A caller cannot forge an ordering position.
    """
    if payload.get("eventType") != event_type:
        raise ValueError(
            "envelope eventType %r does not match payload eventType %r"
            % (event_type, payload.get("eventType"))
        )
    return {
        "schemaVersion": CONTRACT_SCHEMA_VERSION,
        "eventId": event_id,
        "streamId": stream_id,
        "streamVersion": 1,
        "globalSequence": 1,
        "eventType": event_type,
        "occurredAt": occurred_at,
        "actor": metadata["actor"],
        "missionId": mission_id,
        "taskId": task_id,
        "claimId": claim_id,
        "correlationId": metadata["correlationId"],
        "causationId": metadata["commandId"],
        "payload": payload,
        "payloadDigest": "sha256:" + "0" * 64,
    }
