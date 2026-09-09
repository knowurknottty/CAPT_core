"""Persistent sandbox resource facts; capability authority stays elsewhere.

Pure state transitions only. External observation and governed multi-stream
persistence belong to the runtime; this aggregate never performs Docker I/O.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from ..contracts import require
from ..errors import IllegalTransition

TRANSITIONS = {
    "reserved": {"created", "closed", "indeterminate"},
    "created": {"running", "closing", "indeterminate"},
    "running": {"closing", "indeterminate"},
    "closing": {"closed", "indeterminate"},
    "indeterminate": {"running", "closing", "closed"},
    "closed": set(),
}

# External facts can be bound after reservation, including during crash recovery,
# but can never be replaced or cleared once observed.
_BIND_ONCE_FIELDS = frozenset({
    "containerId", "guardianContainerId", "guardianImageId", "networkId",
    "networkName", "creationAttestationDigest", "sideEffectIdentity",
})
_MUTABLE_FIELDS = frozenset({
    "updatedAt", "lastReconciledAt", "reconciliationReason",
    "reconciliationEvidenceDigest", "closeReason", "closedAt", "closureReceiptDigest",
})
_OBSERVED_FIELDS = frozenset({"containerId", "creationAttestationDigest", "sideEffectIdentity"})


class SandboxLeaseAggregate:
    KIND = "sandbox_lease"
    OWNED_FIELDS = frozenset("sandbox_lease." + field for field in (
        _BIND_ONCE_FIELDS | _MUTABLE_FIELDS | {"state", "createdAt", "expiresAt", "ttlSeconds"}
    ))
    REFERENCE_FIELDS = frozenset({
        "sandboxLeaseId", "profileId", "profileDigest", "imageId",
        "securityProfileDigest", "networkPolicyDigest", "filesystemScopeDigest",
        "persistentEntrypointDigest", "operatorId", "sessionId", "executionContextId",
        "creationToolExecutionId", "dockerEndpoint", "daemonIdentityDigest",
    })

    @staticmethod
    def stream_id(sandbox_lease_id: str) -> str:
        stream = "sandbox_lease-" + sandbox_lease_id
        require("StreamId", stream)
        return stream

    @staticmethod
    def reserve(record: Dict[str, Any]) -> Dict[str, Any]:
        require("SandboxLease", record)
        if record["state"] != "reserved":
            raise IllegalTransition("sandbox lease " + record["sandboxLeaseId"], record["state"], "reserved")
        return deepcopy(record)

    @staticmethod
    def _transition(state: Dict[str, Any], target: str, patch: Dict[str, Any], *, reconciliation: bool = False) -> Dict[str, Any]:
        require("SandboxLease", state)
        current = state["state"]
        label = "sandbox lease " + state["sandboxLeaseId"]
        if target not in TRANSITIONS[current] or (current == "indeterminate") != reconciliation:
            raise IllegalTransition(label, current, target)
        for field, value in patch.items():
            if field in _MUTABLE_FIELDS:
                continue
            if field in _BIND_ONCE_FIELDS and field not in state:
                continue
            if field != "state" and field in state and state[field] == value:
                continue
            raise IllegalTransition(label + " immutable field " + field, current, target)
        nxt = deepcopy(state)
        nxt.update(deepcopy(patch))
        nxt["state"] = target
        if current == "reserved" and target == "closed" and (
            nxt.get("closeReason") != "create_failed_no_effect"
            or _BIND_ONCE_FIELDS.intersection(nxt)
        ):
            raise IllegalTransition(label + " requires create_failed_no_effect", current, target)
        if target in {"created", "running"} and not _OBSERVED_FIELDS.issubset(nxt):
            raise IllegalTransition(label + " requires observed identity", current, target)
        require("SandboxLease", nxt)
        return nxt

    @staticmethod
    def record_created(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        return SandboxLeaseAggregate._transition(state, "created", patch)

    @staticmethod
    def record_running(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        return SandboxLeaseAggregate._transition(state, "running", patch)

    @staticmethod
    def begin_close(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        return SandboxLeaseAggregate._transition(state, "closing", patch)

    @staticmethod
    def record_closed(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        return SandboxLeaseAggregate._transition(state, "closed", patch)

    @staticmethod
    def mark_indeterminate(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        return SandboxLeaseAggregate._transition(state, "indeterminate", patch)

    @staticmethod
    def reconcile(state: Dict[str, Any], target_state: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        return SandboxLeaseAggregate._transition(state, target_state, patch, reconciliation=True)
