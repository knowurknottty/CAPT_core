"""Phase-scoped capability authority for model-invoked CAPT tools.

HumanApproval freezes the normalized authority profile.  This module turns that
already-approved profile into a short-lived ToolBroker grant/lease for exactly one
DriverRun.  It cannot widen the profile and it never bypasses ToolBroker.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from . import contracts
from .errors import AuthorityViolation
from .model_authority import revalidate_normalized_model_authority
from .model_tool_bridge import MODEL_TOOL_MAX_CALLS, ModelToolBridge
from .tool_broker import ToolBroker


def _id(prefix: str, driver_run_id: str) -> str:
    suffix = hashlib.sha256(driver_run_id.encode("utf-8")).hexdigest()[:24]
    return prefix + suffix


@dataclass(frozen=True)
class IssuedModelToolAuthority:
    policy_id: str
    grant_id: str
    lease_id: str
    bridge: ModelToolBridge


def issue_model_tool_authority(
    *,
    service: Any,
    broker: ToolBroker,
    authority_profile: Mapping[str, Any],
    target_root: str,
    mission_id: str,
    task_id: str,
    driver_run_id: str,
    operator_id: str,
    session_id: str,
    issued_at: str,
    valid_until: str,
    metadata_factory: Callable[[str], Mapping[str, Any]],
    now: Callable[[], str],
) -> IssuedModelToolAuthority:
    """Mint exact, bounded ToolBroker authority for one approved model run."""
    profile = revalidate_normalized_model_authority(
        authority_profile, target_root=target_root
    )
    if valid_until < issued_at:
        raise AuthorityViolation("MODEL_TOOL_AUTHORITY_ALREADY_EXPIRED")

    policy_id = _id("pd-model-tools-", driver_run_id)
    grant_id = _id("g-model-tools-", driver_run_id)
    lease_id = _id("l-model-tools-", driver_run_id)
    scope = {
        "kind": "filesystem",
        "rootPath": profile["filesystemRoot"],
        "recursive": True,
    }
    operations = list(profile["toolOperations"])
    policy_digest = contracts.digest({
        "policyBundle": "model-tool-authority",
        "version": 1,
        "driverRunId": driver_run_id,
        "authorityProfile": profile,
    })

    service.evaluate_policy(
        {
            "schemaVersion": "1.0.0",
            "policyDecisionId": policy_id,
            "policyBundleDigest": policy_digest,
            "effect": "allow",
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "missionId": mission_id,
            "taskId": task_id,
            "requestedOperations": operations,
            "requestedScope": scope,
            "conditions": [],
            "rationale": "Exact HumanApproval-bound model tool authority for one DriverRun.",
            "decidedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
            "decidedAt": issued_at,
        },
        dict(metadata_factory("tool-policy")),
    )
    service.issue_grant(
        {
            "schemaVersion": "1.0.0",
            "grantId": grant_id,
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "capabilityId": "cap.model.tools",
            "operations": operations,
            "scope": scope,
            "policyDecisionId": policy_id,
            "policyBundleDigest": policy_digest,
            "conditions": [],
            "maxUses": MODEL_TOOL_MAX_CALLS,
            "validFrom": issued_at,
            "validUntil": valid_until,
            "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
            "issuedAt": issued_at,
        },
        dict(metadata_factory("tool-grant")),
    )
    service.activate_lease(
        {
            "schemaVersion": "1.0.0",
            "leaseId": lease_id,
            "grantId": grant_id,
            "missionId": mission_id,
            "taskId": task_id,
            "executionContextId": _id("ec-model-tools-", driver_run_id),
            "operations": operations,
            "scope": scope,
            "maxUses": MODEL_TOOL_MAX_CALLS,
            "validFrom": issued_at,
            "validUntil": valid_until,
            "activatedAt": issued_at,
        },
        dict(metadata_factory("tool-lease")),
    )
    bridge = ModelToolBridge(
        broker=broker,
        authority_profile=profile,
        target_root=target_root,
        grant_id=grant_id,
        lease_id=lease_id,
        operator_id=operator_id,
        session_id=session_id,
        driver_run_id=driver_run_id,
        now=now,
    )
    return IssuedModelToolAuthority(
        policy_id=policy_id,
        grant_id=grant_id,
        lease_id=lease_id,
        bridge=bridge,
    )


def revoke_model_tool_authority(
    *,
    service: Any,
    grant_id: str,
    issued_at: str,
    reason: str,
    metadata: Mapping[str, Any],
) -> None:
    """Irreversibly close a model tool phase; reconciliation evidence remains durable."""
    actor = dict(metadata.get("actor") or {})
    if actor.get("kind") != "governance_kernel":
        raise AuthorityViolation("MODEL_TOOL_REVOCATION_REQUIRES_GOVERNANCE_KERNEL")
    revocation_id = _id("rev-model-tools-", grant_id + ":" + issued_at)
    service.revoke(
        grant_id,
        {
            "schemaVersion": "1.0.0",
            "revocationId": revocation_id,
            "targetKind": "grant",
            "targetId": grant_id,
            "reason": reason[:1024],
            "revokedBy": actor,
            "revokedAt": issued_at,
        },
        dict(metadata),
    )
