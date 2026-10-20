"""Authenticated, read-only production release readiness witness.

The caller must perform its own governed stop/checkpoint and post-restart
verification; a readiness witness is NEVER an activation authorization.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from capt_runtime.aggregates.capability import CapabilityAggregate


def assess_release_snapshot(
    identity: dict[str, Any],
    checkpoint: dict[str, Any],
    unresolved: list[str],
    active_run_ids: list[str],
    active_tool_ids: list[str],
    *,
    state_root: Path,
    installed_source: str,
    candidate_source: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    if identity.get("integrity") != "ok":
        blockers.append("EVENTSTORE_INTEGRITY_NOT_OK")
    if str(Path(identity.get("ledgerPath", "")).parent) != str(state_root):
        blockers.append("AUTHENTICATED_RUNTIME_STATE_ROOT_MISMATCH")
    if checkpoint.get("integrityVerified") is not True:
        blockers.append("CHECKPOINT_INTEGRITY_UNVERIFIED")
    if checkpoint.get("globalSequence") != identity.get("headSequence"):
        blockers.append("CHECKPOINT_NOT_CURRENT")
    if checkpoint.get("recoveryState") != "clean" or checkpoint.get("canDispatchConsequential") is not True:
        blockers.append("CHECKPOINT_RECOVERY_NOT_CLEAN")
    if sorted(checkpoint.get("openReservations") or []) != sorted(unresolved):
        blockers.append("RESERVATION_PROJECTION_MISMATCH")
    if unresolved:
        blockers.append("UNRESOLVED_RESERVATIONS")
    if active_run_ids or active_tool_ids:
        blockers.append("ACTIVE_EXECUTION")
    if not installed_source or installed_source == candidate_source:
        blockers.append("SOURCE_SWITCH_IDENTITY_INVALID")
    return {
        "eligibleForQuiescence": not blockers,
        "blockers": blockers,
        "authenticatedRuntimeService": bool(identity),
        "headSequence": identity.get("headSequence"),
        "ledgerChainDigest": identity.get("ledgerChainDigest"),
        "checkpointId": checkpoint.get("checkpointId"),
        "installedSourceSha": installed_source,
        "candidateSourceSha": candidate_source,
        "unresolvedReservationIds": sorted(unresolved),
        "activeDriverRunIds": sorted(active_run_ids),
        "activeToolExecutionIds": sorted(active_tool_ids),
        "stateRoot": str(state_root),
    }


def read_authenticated_release_readiness(state_root: Path, candidate_source: str) -> dict[str, Any]:
    """Connect to RuntimeService, not raw EventStore, for fresh authoritative state.

    Does not stop any process, consume approval, modify the ledger, or claim
    recovery authority. A fresh checkpoint remains a separate guarded action.
    """
    from desktop.desktop_runtime_client import RuntimeClient

    root = Path(state_root).resolve(strict=True)
    client = RuntimeClient(str(root / "runtime.sock"), str(root / "runtime.token"))
    try:
        identity = client.connect()
        checkpoints = client._query({"op": "checkpoints"})["result"]["checkpoints"]
        if not checkpoints:
            raise RuntimeError("NO_AUTHENTICATED_CHECKPOINT")
        checkpoint = checkpoints[0]
        unresolved: list[str] = []
        active_runs: list[str] = []
        active_tools: list[str] = []
        for ref in client.list_aggregates():
            kind = ref.get("kind")
            if kind not in ("capability", "driverrun", "tool_execution"):
                continue
            state = client.get_state(ref["streamId"])
            if kind == "capability":
                unresolved.extend(CapabilityAggregate.unresolved_reservations(state))
            elif kind == "driverrun" and state.get("state") in ("created", "submitted", "running", "queued"):
                active_runs.append(ref["streamId"])
            elif kind == "tool_execution" and state.get("state") in ("created", "submitted", "running", "queued"):
                active_tools.append(ref["streamId"])
        marker = root / "runtime-venv" / "CAPT_SOURCE_HEAD"
        if not marker.is_file() or marker.is_symlink():
            raise RuntimeError("ACTIVE_RUNTIME_SOURCE_MARKER_UNVERIFIED")
        return assess_release_snapshot(
            identity, checkpoint, unresolved, active_runs, active_tools,
            state_root=root, installed_source=marker.read_text().strip(),
            candidate_source=candidate_source,
        )
    finally:
        client.disconnect()
