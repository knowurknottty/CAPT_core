"""State Transition Kernel (ADR-DT-PLANE-CONV).

A single shared mechanics layer for command-envelope validation, aggregate
version checks, idempotency, transactional mutation, event append, outbox
commit, snapshot coordination, replay, schema migration hooks, correlation and
causation, invariant hooks, and deterministic receipts.

This module is a THIN, DOMAIN-NEUTRAL facade over the already-canonical
mechanics in ``store.py``, ``commands.py``, ``invariants.py``, ``checkpoint.py``,
and ``replay.py``. It owns NO domain policy: no mission policy, approval policy,
identity policy, evidence policy, memory policy, learning policy, or artifact
promotion policy. Domain aggregates remain responsible for deciding whether a
transition is legal.

The kernel guarantees that an accepted transition is atomic, versioned,
journaled, replayable, and idempotent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .commands import command as _build_command, envelope as _build_envelope
from .contracts import CONTRACT_SCHEMA_VERSION, canonical_json, digest, require
from .store import AppendRequest, EventStore
from .invariants import by_id as _invariant_by_id
from .checkpoint import create_checkpoint, verify_checkpoint
from .replay import full_replay, ReplayState


# -- command envelope validation -----------------------------------------

def build_command_envelope(
    command_id: str,
    idempotency_key: str,
    operation: str,
    correlation_id: str,
    actor_id: str,
    actor_kind: str,
    issued_at: str,
    causation_id: Optional[str] = None,
    replay_policy: str = "never",
    attempt: int = 1,
) -> Dict[str, Any]:
    """Validate and build a CommandMetadata envelope (kernel mechanics)."""
    return _build_command(
        command_id=command_id,
        idempotency_key=idempotency_key,
        operation_fingerprint=digest(operation),
        correlation_id=correlation_id,
        actor_id=actor_id,
        actor_kind=actor_kind,
        issued_at=issued_at,
        replay_policy=replay_policy,
        attempt=attempt,
        causation_id=causation_id,
    )


def build_event_envelope(
    event_id: str,
    stream_id: str,
    kind: str,
    event_type: str,
    payload: Dict[str, Any],
    metadata: Dict[str, Any],
    occurred_at: str,
    mission_id: Optional[str] = None,
    task_id: Optional[str] = None,
    claim_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an EventEnvelope skeleton (kernel mechanics).

    streamVersion, globalSequence, and payloadDigest are assigned by the store
    inside the commit transaction; a caller cannot forge ordering.
    """
    return _build_envelope(
        event_id=event_id,
        stream_id=stream_id,
        event_type=event_type,
        payload=payload,
        metadata=metadata,
        occurred_at=occurred_at,
        mission_id=mission_id,
        task_id=task_id,
        claim_id=claim_id,
    )


# -- transactional mutation + event append + outbox commit ----------------

def commit_transition(
    store: EventStore,
    stream_id: str,
    kind: str,
    expected_version: int,
    event_type: str,
    payload: Dict[str, Any],
    command: Dict[str, Any],
    occurred_at: str,
    new_state: Dict[str, Any],
    mission_id: Optional[str] = None,
    task_id: Optional[str] = None,
    claim_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Atomic, versioned, journaled, idempotent transition.

    Wraps ``EventStore.commit_command`` with envelope construction. The kernel
    does NOT decide legality — the caller must have already validated the
    transition against domain invariants.
    """
    envelope = build_event_envelope(
        event_id=digest("%s:%s:%d" % (stream_id, event_type, expected_version + 1)),
        stream_id=stream_id,
        kind=kind,
        event_type=event_type,
        payload=payload,
        metadata=command,
        occurred_at=occurred_at,
        mission_id=mission_id,
        task_id=task_id,
        claim_id=claim_id,
    )
    request = AppendRequest(
        stream_id=stream_id,
        kind=kind,
        expected_version=expected_version,
        envelope=envelope,
        state=new_state,
    )
    return store.commit_command(
        [request],
        idempotency_key=command["idempotencyKey"],
        operation_fingerprint=command["operationFingerprint"],
        command_id=command["commandId"],
    )


# -- invariant hooks -------------------------------------------------------

def evaluate_invariant(invariant_id: str, state: Dict[str, Any]) -> Optional[str]:
    """Run a registered invariant hook. Returns a violation message or None."""
    try:
        inv = _invariant_by_id(invariant_id)
    except KeyError:
        return "unknown invariant %s" % invariant_id
    return inv(state)


# -- snapshot coordination + replay ---------------------------------------

def coordinate_checkpoint(
    store: EventStore,
    checkpoint_id: str,
    created_at: str,
    policy_bundle_digest: str,
) -> Dict[str, Any]:
    """Coordinate a verified checkpoint (kernel mechanics)."""
    manifest = create_checkpoint(store, checkpoint_id, created_at, policy_bundle_digest)
    verify_checkpoint(manifest)
    return manifest


def replay_state(store: EventStore) -> ReplayState:
    """Deterministic full replay (kernel mechanics)."""
    return full_replay(store)


# -- deterministic receipts -----------------------------------------------

def receipt(status: str, result: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Build a deterministic receipt with a content digest."""
    body = {
        "status": status,
        "result": result,
        "correlationId": correlation_id,
    }
    body["receiptDigest"] = digest(body)
    return body


__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "build_command_envelope",
    "build_event_envelope",
    "commit_transition",
    "evaluate_invariant",
    "coordinate_checkpoint",
    "replay_state",
    "receipt",
    "AppendRequest",
    "EventStore",
    "ReplayState",
]
