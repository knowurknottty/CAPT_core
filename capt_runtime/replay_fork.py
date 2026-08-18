"""Point-in-time replay and linear continuation preparation (CAPT-UPG-016).

A replay fork is a read-only, content-addressed *preparation* for a future
continuation. It never truncates or rewrites EventStore history, and possessing
a fork manifest does not authorize mission/task execution or side effects.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from .checkpoint import verify_checkpoint
from .contracts import digest
from .errors import IntegrityViolation
from .replay import ReplayState, _apply
from .store import EventStore, GENESIS_CHAIN, chain_next

FORK_SCHEMA_VERSION = "1.0.0"


def _prefix_chain(store: EventStore, sequence: int) -> str:
    if sequence < 0:
        raise ValueError("sequence must be >= 0")
    head = store.head_sequence()
    if sequence > head:
        raise ValueError("sequence exceeds ledger head")
    chain = GENESIS_CHAIN
    for envelope in store.read_events(after_sequence=0):
        global_sequence = int(envelope["globalSequence"])
        if global_sequence > sequence:
            break
        chain = chain_next(chain, envelope["payloadDigest"], envelope["eventId"])
    return chain


def replay_at_sequence(store: EventStore, sequence: int) -> ReplayState:
    """Deterministically reconstruct state through an exact global sequence."""
    store.verify_chain()
    if sequence < 0:
        raise ValueError("sequence must be >= 0")
    head = store.head_sequence()
    if sequence > head:
        raise ValueError("sequence exceeds ledger head")

    state = ReplayState()
    for envelope in store.read_events(after_sequence=0):
        if int(envelope["globalSequence"]) > sequence:
            break
        _apply(state, envelope)
    return state


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    return digest({k: v for k, v in manifest.items() if k != "manifestDigest"})


def prepare_linear_fork(
    store: EventStore,
    *,
    fork_id: str,
    selected_sequence: int,
    created_at: str,
    checkpoint_manifest: Optional[Mapping[str, Any]] = None,
    requested_continuation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Prepare a non-authoritative continuation manifest from historical state."""
    if not fork_id:
        raise ValueError("fork_id is required")
    if not created_at:
        raise ValueError("created_at is required")

    store.verify_chain()
    head_at_preparation = store.head_sequence()
    state = replay_at_sequence(store, selected_sequence)
    selected_chain = _prefix_chain(store, selected_sequence)

    checkpoint_ref = None
    if checkpoint_manifest is not None:
        checkpoint = dict(checkpoint_manifest)
        verify_checkpoint(checkpoint)
        checkpoint_sequence = int(checkpoint["ledgerPosition"]["globalSequence"])
        if checkpoint_sequence > selected_sequence:
            raise IntegrityViolation("checkpoint is newer than selected replay sequence")
        checkpoint_chain = _prefix_chain(store, checkpoint_sequence)
        if checkpoint_chain != checkpoint["ledgerDigest"]:
            raise IntegrityViolation("checkpoint ledger digest does not match source ledger prefix")
        checkpoint_ref = {
            "checkpointId": checkpoint["checkpointId"],
            "globalSequence": checkpoint_sequence,
            "ledgerDigest": checkpoint["ledgerDigest"],
            "integrityDigest": checkpoint["integrityDigest"],
        }

    manifest: Dict[str, Any] = {
        "schemaVersion": FORK_SCHEMA_VERSION,
        "kind": "LinearReplayForkManifest",
        "forkId": fork_id,
        "createdAt": created_at,
        "source": {
            "ledgerHeadAtPreparation": head_at_preparation,
            "ledgerHeadDigestAtPreparation": store.head_chain(),
            "selectedSequence": selected_sequence,
            "selectedChainDigest": selected_chain,
            "selectedStateDigest": state.digest(),
            "selectedStreamVersions": dict(sorted(state.versions.items())),
        },
        "sourceCheckpoint": checkpoint_ref,
        "requestedContinuation": dict(requested_continuation or {}),
        "authority": {
            "classification": "continuation_preparation_only",
            "rewritesHistory": False,
            "isAuthoritativeRuntimeState": False,
            "mayDispatch": False,
            "mayMutateSourceLedger": False,
            "requiresGovernedAdoption": True,
        },
        "manifestDigest": "",
    }
    manifest["manifestDigest"] = _manifest_digest(manifest)
    return manifest


def verify_linear_fork(store: EventStore, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    """Verify a fork against the source ledger prefix without forbidding later appends."""
    if manifest.get("schemaVersion") != FORK_SCHEMA_VERSION:
        raise IntegrityViolation("unsupported linear replay fork schema")
    if manifest.get("kind") != "LinearReplayForkManifest":
        raise IntegrityViolation("not a linear replay fork manifest")
    if manifest.get("manifestDigest") != _manifest_digest(manifest):
        raise IntegrityViolation("linear replay fork manifest digest mismatch")

    store.verify_chain()
    source = manifest.get("source") or {}
    selected_sequence = int(source.get("selectedSequence", -1))
    if selected_sequence < 0 or selected_sequence > store.head_sequence():
        raise IntegrityViolation("selected replay sequence is unavailable in source ledger")

    chain = _prefix_chain(store, selected_sequence)
    if chain != source.get("selectedChainDigest"):
        raise IntegrityViolation("source ledger prefix no longer matches fork manifest")

    state = replay_at_sequence(store, selected_sequence)
    if state.digest() != source.get("selectedStateDigest"):
        raise IntegrityViolation("point-in-time state digest does not match fork manifest")
    if dict(sorted(state.versions.items())) != source.get("selectedStreamVersions"):
        raise IntegrityViolation("point-in-time stream versions do not match fork manifest")

    checkpoint_ref = manifest.get("sourceCheckpoint")
    if checkpoint_ref:
        checkpoint = store.load_checkpoint(checkpoint_ref["checkpointId"])
        verify_checkpoint(checkpoint)
        if checkpoint["integrityDigest"] != checkpoint_ref["integrityDigest"]:
            raise IntegrityViolation("source checkpoint integrity identity changed")
        if checkpoint["ledgerDigest"] != checkpoint_ref["ledgerDigest"]:
            raise IntegrityViolation("source checkpoint ledger identity changed")

    return {
        "forkId": manifest["forkId"],
        "selectedSequence": selected_sequence,
        "selectedStateDigest": state.digest(),
        "sourcePrefixVerified": True,
        "laterSourceEventsAllowed": store.head_sequence() >= selected_sequence,
        "requiresGovernedAdoption": True,
    }
