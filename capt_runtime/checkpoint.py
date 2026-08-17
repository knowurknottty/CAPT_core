"""Checkpoint creation, verification, and replay (ADR-0109).

A checkpoint is a self-verifying description of runtime state at an exact
ledger position. Replay from a checkpoint plus the tail must equal full replay
from the origin — asserted by the conformance suite, not assumed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import commands
from .aggregates import (
    CapabilityAggregate,
    ClaimAggregate,
    DriverRunAggregate,
    MissionAggregate,
    TaskAggregate,
)
from .contracts import CONTRACT_SCHEMA_VERSION, canonical_json, digest, require
from .errors import IntegrityViolation
from .store import AppendRequest, EventStore

RUNTIME_VERSION = "0.1.0"

_KIND_TO_FIELD = {
    "mission": "missionVersions",
    "task": "taskVersions",
    "capability": "capabilityVersions",
    "driverrun": "driverRunVersions",
    "claim": "claimVersions",
    "human_approval": "humanApprovalVersions",
}


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_integrity_digest(manifest: Dict[str, Any]) -> str:
    """Digest over the manifest with integrityDigest itself removed.

    Including the field would make the digest self-referential and therefore
    uncomputable; omitting it deliberately is the documented convention.
    """
    material = {k: v for k, v in manifest.items() if k != "integrityDigest"}
    return digest(material)


def create_checkpoint(
    store: EventStore,
    checkpoint_id: str,
    created_at: str,
    policy_bundle_digest: str,
    artifact_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build, validate, and persist a CheckpointManifest.

    recoveryState is DERIVED from open reservations, never supplied by a
    caller: a checkpoint cannot be declared clean while consequential work is
    unresolved (ledger Finding K).
    """
    versions: Dict[str, List[Dict[str, Any]]] = {
        field: [] for field in _KIND_TO_FIELD.values()
    }
    active_lease_ids: List[str] = []
    open_reservation_ids: List[str] = []

    for stream_id, kind, version in store.all_aggregates():
        field = _KIND_TO_FIELD.get(kind)
        if field is None:
            raise IntegrityViolation("unknown aggregate kind %r in store" % kind)
        versions[field].append({"streamId": stream_id, "version": version})

        if kind == "capability":
            state = store.require_state(stream_id)
            lease = state.get("lease")
            if lease is not None and lease["state"] == "active":
                active_lease_ids.append(lease["leaseId"])
            open_reservation_ids.extend(CapabilityAggregate.open_reservations(state))

    if open_reservation_ids:
        recovery_state: Dict[str, Any] = {
            "kind": "awaiting_reconciliation",
            "openReservationIds": sorted(open_reservation_ids),
        }
    else:
        recovery_state = {"kind": "clean"}

    artifact_hashes = []
    for raw in sorted(artifact_paths or []):
        path = Path(raw)
        if path.is_file():
            artifact_hashes.append({"path": raw, "digest": _file_digest(path)})

    head = store.head_sequence()
    manifest: Dict[str, Any] = {
        "schemaVersion": CONTRACT_SCHEMA_VERSION,
        "runtimeVersion": RUNTIME_VERSION,
        "checkpointId": checkpoint_id,
        "createdAt": created_at,
        "ledgerPosition": {
            "globalSequence": head,
            "eventId": _head_event_id(store, head),
        },
        "ledgerDigest": store.verify_chain(),
        "missionVersions": sorted(versions["missionVersions"], key=lambda e: e["streamId"]),
        "taskVersions": sorted(versions["taskVersions"], key=lambda e: e["streamId"]),
        "capabilityVersions": sorted(
            versions["capabilityVersions"], key=lambda e: e["streamId"]
        ),
        "driverRunVersions": sorted(
            versions["driverRunVersions"], key=lambda e: e["streamId"]
        ),
        "claimVersions": sorted(versions["claimVersions"], key=lambda e: e["streamId"]),
        "humanApprovalVersions": sorted(
            versions["humanApprovalVersions"], key=lambda e: e["streamId"]
        ),
        "activeLeaseIds": sorted(active_lease_ids),
        "activeReservationIds": sorted(open_reservation_ids),
        "pendingOutboxEventIds": store.pending_outbox(),
        "artifactHashes": artifact_hashes,
        "policyBundleDigest": policy_bundle_digest,
        "recoveryState": recovery_state,
        "integrityDigest": "sha256:" + "0" * 64,
    }
    manifest["integrityDigest"] = manifest_integrity_digest(manifest)
    require("CheckpointManifest", manifest)
    store.save_checkpoint(manifest)
    return manifest


def _head_event_id(store: EventStore, head: int) -> Optional[str]:
    if head == 0:
        return None
    events = store.read_events(after_sequence=head - 1)
    return events[0]["eventId"] if events else None


def verify_checkpoint(manifest: Dict[str, Any]) -> None:
    """Reject a corrupted or schema-incompatible checkpoint.

    Order matters: schema compatibility is checked BEFORE integrity, so an
    incompatible manifest reports the real reason rather than a digest
    mismatch caused by a field this version does not understand.
    """
    if manifest.get("schemaVersion") != CONTRACT_SCHEMA_VERSION:
        raise IntegrityViolation(
            "checkpoint schemaVersion %r is not compatible with runtime contract "
            "version %r" % (manifest.get("schemaVersion"), CONTRACT_SCHEMA_VERSION)
        )
    if manifest.get("runtimeVersion") != RUNTIME_VERSION:
        raise IntegrityViolation(
            "checkpoint runtimeVersion %r != %r"
            % (manifest.get("runtimeVersion"), RUNTIME_VERSION)
        )
    require("CheckpointManifest", manifest)

    recomputed = manifest_integrity_digest(manifest)
    if recomputed != manifest["integrityDigest"]:
        raise IntegrityViolation(
            "checkpoint %s integrity digest mismatch: stored %s, recomputed %s"
            % (manifest["checkpointId"], manifest["integrityDigest"], recomputed)
        )


def can_dispatch_consequential(manifest: Dict[str, Any]) -> bool:
    """False when a resumed runtime must reconcile before acting."""
    return manifest["recoveryState"]["kind"] == "clean"
