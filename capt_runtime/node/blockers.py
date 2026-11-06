"""Specific Node indeterminacy -> existing human-only Lab Board boundary."""

from __future__ import annotations

import hashlib


def blocker_from_indeterminate(
    *,
    operation_id: str,
    mission_id: str,
    reason: str,
    evidence_refs: list[str],
    created_at: str,
) -> dict:
    if not operation_id:
        raise ValueError("node_operation_id_required")
    if not reason or reason in {"error", "unknown", "generic"}:
        raise ValueError("node_blocker_reason_must_be_specific")
    suffix = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:20]
    return {
        "schemaVersion": "1.0.0",
        "itemId": "node-blocker-" + suffix,
        "missionId": mission_id,
        "title": f"Resolve CAPT Node operation {operation_id}",
        "state": "blocked_human",
        "ownerRef": "human",
        "blockerReason": reason,
        "humanRequest": "Resolve the indeterminate Node effect from preserved evidence; do not retry blindly.",
        "evidenceRefs": list(evidence_refs),
        "createdBy": {"actorId": "capt-node", "kind": "execution_plane"},
        "createdAt": created_at,
        "updatedAt": created_at,
    }
