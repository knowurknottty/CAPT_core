"""Materialize executable capability from one exact human-approved boundary.

The caller may select only the approval request and execution-context identity.
Capability semantics are derived exclusively from durable HumanApproval state.
No caller-supplied operations, scope, subject, conditions, use budget, expiry, or
external commitments are accepted by this module.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from . import commands, contracts
from .aggregates import CapabilityAggregate, HumanApprovalAggregate
from .errors import AuthorityViolation


def _id(prefix: str, seed: str) -> str:
    return prefix + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class ApprovedCapabilityAuthority:
    policy_id: str
    grant_id: str
    lease_id: str
    request_id: str
    status: str


def issue_approved_capability_authority(
    *,
    service: Any,
    request_id: str,
    execution_context_id: str,
    operator_id: str,
    command_id: str,
    idempotency_key: str,
    correlation_id: str,
    issued_at: str,
) -> ApprovedCapabilityAuthority:
    """Derive and activate exact capability from durable approved state."""

    if not request_id:
        raise AuthorityViolation("APPROVED_CAPABILITY_REQUEST_ID_REQUIRED")
    if not execution_context_id:
        raise AuthorityViolation("APPROVED_CAPABILITY_EXECUTION_CONTEXT_REQUIRED")

    approval_stream = HumanApprovalAggregate.stream_id(request_id)
    approval = service.store.require_state(approval_stream)
    use_id = _id("approval-capability-use-", request_id)

    if approval.get("operatorId") != operator_id:
        raise AuthorityViolation("APPROVED_CAPABILITY_OPERATOR_MISMATCH")
    if approval.get("state") not in {"approved", "consumed"}:
        raise AuthorityViolation("APPROVED_CAPABILITY_REQUEST_NOT_APPROVED")
    if approval.get("state") == "consumed" and approval.get("consumedBy") != use_id:
        raise AuthorityViolation("APPROVED_CAPABILITY_REQUEST_ALREADY_CONSUMED")
    if issued_at > str(approval.get("expiresAt") or ""):
        raise AuthorityViolation("APPROVED_CAPABILITY_REQUEST_EXPIRED")

    operations = list(approval.get("operations") or [])
    subject = approval.get("capabilitySubject")
    conditions = list(approval.get("capabilityConditions") or [])
    max_uses = approval.get("capabilityMaxUses")
    scope = approval.get("scope")
    capability_id = approval.get("requestedCapability")
    commitments = list(approval.get("externalCommitments") or [])

    if not operations:
        raise AuthorityViolation("APPROVED_CAPABILITY_OPERATIONS_REQUIRED")
    if not isinstance(subject, dict):
        raise AuthorityViolation("APPROVED_CAPABILITY_SUBJECT_REQUIRED")
    if isinstance(max_uses, bool) or not isinstance(max_uses, int) or max_uses < 1:
        raise AuthorityViolation("APPROVED_CAPABILITY_MAX_USES_REQUIRED")
    if not isinstance(scope, dict):
        raise AuthorityViolation("APPROVED_CAPABILITY_SCOPE_REQUIRED")
    if not isinstance(capability_id, str) or not capability_id:
        raise AuthorityViolation("APPROVED_CAPABILITY_ID_REQUIRED")

    authority_snapshot = {
        "requestId": request_id,
        "operatorId": operator_id,
        "missionId": approval["missionId"],
        "taskId": approval["taskId"],
        "capabilityId": capability_id,
        "subject": subject,
        "operations": operations,
        "scope": scope,
        "conditions": conditions,
        "maxUses": max_uses,
        "expiresAt": approval["expiresAt"],
        "externalCommitments": commitments,
    }
    policy_id = _id("pd-human-approved-", request_id)
    grant_id = _id("g-human-approved-", request_id)
    lease_id = _id("l-human-approved-", request_id + ":" + execution_context_id)
    policy_digest = contracts.digest(
        {
            "policyBundle": "human-approved-capability-transfer",
            "version": 1,
            "approvedAuthority": authority_snapshot,
        }
    )

    def gk_meta(step: str, operation: str, semantic: Any) -> dict:
        return commands.command(
            command_id=command_id + ":" + step,
            idempotency_key=idempotency_key + ":" + step,
            operation_fingerprint=commands.fingerprint(operation, semantic),
            correlation_id=correlation_id,
            actor_id="gk-1",
            actor_kind="governance_kernel",
            issued_at=issued_at,
            replay_policy="never",
        )

    policy = {
        "schemaVersion": "1.0.0",
        "policyDecisionId": policy_id,
        "policyBundleDigest": policy_digest,
        "effect": "allow_with_conditions" if conditions else "allow",
        "subject": subject,
        "missionId": approval["missionId"],
        "taskId": approval["taskId"],
        "requestedOperations": operations,
        "requestedScope": scope,
        "conditions": conditions,
        "rationale": "Materialize only the exact durable HumanApproval capability boundary.",
        "decidedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
        "decidedAt": issued_at,
        "externalCommitments": commitments,
    }
    policy_result = service.evaluate_policy(
        policy, gk_meta("policy", "evaluate_policy", policy)
    )

    grant = {
        "schemaVersion": "1.0.0",
        "grantId": grant_id,
        "subject": subject,
        "capabilityId": capability_id,
        "operations": operations,
        "scope": scope,
        "policyDecisionId": policy_id,
        "policyBundleDigest": policy_digest,
        "approvalRequestId": request_id,
        "conditions": conditions,
        "maxUses": max_uses,
        "validFrom": issued_at,
        "validUntil": approval["expiresAt"],
        "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
        "issuedAt": issued_at,
        "externalCommitments": commitments,
    }
    grant_semantic = {"requestId": request_id, "grant": grant, "useId": use_id}
    grant_result = service.issue_grant_from_human_approval(
        request_id,
        grant,
        gk_meta(
            "grant",
            "issue_grant_from_human_approval",
            grant_semantic,
        ),
        use_id=use_id,
        now=issued_at,
    )

    lease = {
        "schemaVersion": "1.0.0",
        "leaseId": lease_id,
        "grantId": grant_id,
        "missionId": approval["missionId"],
        "taskId": approval["taskId"],
        "executionContextId": execution_context_id,
        "operations": operations,
        "scope": scope,
        "maxUses": max_uses,
        "validFrom": issued_at,
        "validUntil": approval["expiresAt"],
        "activatedAt": issued_at,
    }
    lease_result = service.activate_lease(
        lease, gk_meta("lease", "activate_lease", lease)
    )

    # Re-read the authoritative aggregates rather than trusting intermediate
    # return summaries.
    grant_state = service.store.require_state(CapabilityAggregate.stream_id(grant_id))
    approval_state = service.store.require_state(approval_stream)
    if grant_state.get("approvalRequestId") != request_id:
        raise AuthorityViolation("APPROVED_CAPABILITY_GRANT_READBACK_MISMATCH")
    if approval_state.get("consumedBy") != use_id:
        raise AuthorityViolation("APPROVED_CAPABILITY_CONSUMPTION_READBACK_MISMATCH")
    active_lease = grant_state.get("lease") or {}
    if active_lease.get("leaseId") != lease_id:
        raise AuthorityViolation("APPROVED_CAPABILITY_LEASE_READBACK_MISMATCH")

    statuses = {
        str(policy_result.get("status")),
        str(grant_result.get("status")),
        str(lease_result.get("status")),
    }
    status = "idempotent" if statuses == {"idempotent"} else "applied"
    return ApprovedCapabilityAuthority(
        policy_id=policy_id,
        grant_id=grant_id,
        lease_id=lease_id,
        request_id=request_id,
        status=status,
    )
