from __future__ import annotations

import copy

import pytest

from capt_runtime import commands, contracts
from capt_runtime.aggregates import CapabilityAggregate, HumanApprovalAggregate
from capt_runtime.errors import AuthorityViolation, IdempotencyConflict
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


ROOT = "/tmp/capt-approved-tool-work"
WORK_DIGEST = "sha256:" + ("a" * 64)
POLICY_DIGEST = contracts.digest({"policy": "human-approved-capability"})


def meta(command_id, actor_kind, actor_id):
    return commands.command(
        command_id=command_id,
        idempotency_key="idem-" + command_id,
        operation_fingerprint=contracts.digest({"command": command_id}),
        correlation_id="wc-correlation-1",
        actor_id=actor_id,
        actor_kind=actor_kind,
        issued_at="2026-09-28T03:00:00Z",
    )




def grant_meta(command_id, grant_obj, use_id):
    return commands.command(
        command_id=command_id,
        idempotency_key="idem-" + command_id,
        operation_fingerprint=commands.fingerprint(
            "issue_grant_from_human_approval",
            {
                "requestId": intent()["requestId"],
                "grant": grant_obj,
                "useId": use_id,
            },
        ),
        correlation_id="wc-correlation-1",
        actor_id="gov-1",
        actor_kind="governance_kernel",
        issued_at="2026-09-28T03:00:20Z",
    )

def intent():
    return {
        "schemaVersion": "1.0.0",
        "missionId": "m-human-capability-1",
        "taskId": "t-human-capability-1",
        "requestId": "approval-human-capability-1",
        "objective": "Perform exactly the human-approved bounded tool operations.",
        "rawRequest": "Perform exactly the human-approved bounded tool operations.",
        "normalizedRequest": "perform exactly the human-approved bounded tool operations.",
        "scope": {"kind": "filesystem", "rootPath": ROOT, "recursive": True},
        "constraints": [],
        "successCriteria": [
            {
                "criterionId": "postcondition",
                "statement": "The approved postcondition is verified.",
                "requiresVerification": True,
            }
        ],
        "terminationCriteria": [],
        "unresolvedAmbiguities": [],
        "requiresApproval": True,
        "requestedCapability": "cap.cvw.execute",
        "operations": ["file.write", "terminal.exec"],
        "consequential": True,
        "capabilitySubject": {"actorId": "exec-cvw", "kind": "execution_plane"},
        "capabilityConditions": [{"kind": "requires_approval", "approverRole": "human_operator"}],
        "capabilityMaxUses": 2,
        "maxAttempts": 2,
        "resource": ROOT,
        "operation": "VerifiedWorkExecution",
        "riskClassification": "consequential",
        "policyReason": "Exact WorkContract-bound human approval required.",
        "expiresAt": "2026-09-29T03:00:00Z",
        "remainingUses": 1,
        "correlationId": "wc-correlation-1",
        "externalCommitments": [
            {
                "kind": "inversion.work-contract.v0.1",
                "digest": WORK_DIGEST,
                "reference": "work-fixture-001",
            }
        ],
    }


def policy():
    i = intent()
    return {
        "schemaVersion": "1.0.0",
        "policyDecisionId": "pd-human-capability-1",
        "policyBundleDigest": POLICY_DIGEST,
        "effect": "allow_with_conditions",
        "subject": {"actorId": "exec-cvw", "kind": "execution_plane"},
        "missionId": i["missionId"],
        "taskId": i["taskId"],
        "requestedOperations": list(i["operations"]),
        "requestedScope": dict(i["scope"]),
        "conditions": [{"kind": "requires_approval", "approverRole": "human_operator"}],
        "rationale": "Governance allows only the exact human-approved work boundary.",
        "decidedBy": {"actorId": "gov-1", "kind": "governance_kernel"},
        "decidedAt": "2026-09-28T03:00:10Z",
        "externalCommitments": list(i["externalCommitments"]),
    }


def grant():
    i = intent()
    return {
        "schemaVersion": "1.0.0",
        "grantId": "grant-human-capability-1",
        "subject": {"actorId": "exec-cvw", "kind": "execution_plane"},
        "capabilityId": i["requestedCapability"],
        "operations": list(i["operations"]),
        "scope": dict(i["scope"]),
        "policyDecisionId": "pd-human-capability-1",
        "policyBundleDigest": POLICY_DIGEST,
        "approvalRequestId": i["requestId"],
        "conditions": [{"kind": "requires_approval", "approverRole": "human_operator"}],
        "maxUses": 2,
        "validFrom": "2026-09-28T03:00:00Z",
        "validUntil": "2026-09-29T03:00:00Z",
        "issuedBy": {"actorId": "gov-1", "kind": "governance_kernel"},
        "issuedAt": "2026-09-28T03:00:20Z",
        "externalCommitments": list(i["externalCommitments"]),
    }


def setup_service():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    i = intent()
    svc.create_mission_with_approval(i, meta("create-human-capability", "human", "captain"))
    svc.submit_human_approval_decision(
        {
            "schemaVersion": "1.0.0",
            "requestId": i["requestId"],
            "decision": "approve",
            "operatorId": "captain",
            "decidedAt": "2026-09-28T03:00:05Z",
            "note": "Approve exact WorkContract-bound capability.",
            "idempotencyKey": "human-decision-1",
            "correlationId": i["correlationId"],
            "sessionId": "session-cvw",
        },
        meta("decide-human-capability", "human", "captain"),
        now="2026-09-28T03:00:05Z",
    )
    svc.evaluate_policy(policy(), meta("policy-human-capability", "governance_kernel", "gov-1"))
    return store, svc


def test_exact_approval_policy_grant_binding_is_atomic_and_one_use():
    store, svc = setup_service()
    result = svc.issue_grant_from_human_approval(
        intent()["requestId"],
        grant(),
        grant_meta("grant-human-capability", grant(), "approval-to-grant-1"),
        use_id="approval-to-grant-1",
        now="2026-09-28T03:00:20Z",
    )
    assert result["status"] == "applied"
    assert result["approvalState"] == "consumed"
    assert result["grantState"] == "granted"

    approval = store.require_state(
        HumanApprovalAggregate.stream_id(intent()["requestId"])
    )
    capability = store.require_state(
        CapabilityAggregate.stream_id(grant()["grantId"])
    )
    assert approval["consumedBy"] == "approval-to-grant-1"
    assert approval["operations"] == intent()["operations"]
    assert capability["operations"] == intent()["operations"]
    assert capability["externalCommitments"] == intent()["externalCommitments"]

    events = store.read_events()
    consume = [
        e for e in events
        if e["payload"]["eventType"] == "HumanApprovalConsumedForCapability"
    ]
    granted = [
        e for e in events
        if e["payload"]["eventType"] == "CapabilityGranted"
        and e["payload"]["grant"]["grantId"] == grant()["grantId"]
    ]
    assert len(consume) == 1
    assert len(granted) == 1
    assert consume[0]["globalSequence"] + 1 == granted[0]["globalSequence"]
    assert consume[0]["causationId"] == "grant-human-capability"
    assert granted[0]["causationId"] == "grant-human-capability"


@pytest.mark.parametrize(
    "mutator,code",
    [
        (
            lambda g: g.update(operations=["file.write"]),
            "HUMAN_APPROVAL_GRANT_OPERATIONS_MISMATCH",
        ),
        (
            lambda g: g.update(
                scope={"kind": "filesystem", "rootPath": ROOT + "/narrow", "recursive": True}
            ),
            "HUMAN_APPROVAL_GRANT_SCOPE_MISMATCH",
        ),
        (
            lambda g: g.update(capabilityId="cap.other"),
            "HUMAN_APPROVAL_GRANT_CAPABILITY_MISMATCH",
        ),
        (
            lambda g: g.update(
                externalCommitments=[
                    {
                        "kind": "inversion.work-contract.v0.1",
                        "digest": "sha256:" + ("b" * 64),
                        "reference": "work-fixture-001",
                    }
                ]
            ),
            "HUMAN_APPROVAL_GRANT_COMMITMENT_MISMATCH",
        ),
    ],
)
def test_grant_cannot_drift_from_human_approval(mutator, code):
    _store, svc = setup_service()
    g = grant()
    mutator(g)
    with pytest.raises(AuthorityViolation, match=code):
        svc.issue_grant_from_human_approval(
            intent()["requestId"],
            g,
            grant_meta(
                "grant-drift-" + code.lower(), g, "approval-to-grant-drift"
            ),
            use_id="approval-to-grant-drift",
            now="2026-09-28T03:00:20Z",
        )


def test_policy_cannot_drift_from_human_approval():
    store = EventStore(":memory:")
    svc = RuntimeService(store)
    i = intent()
    svc.create_mission_with_approval(i, meta("create-policy-drift", "human", "captain"))
    svc.submit_human_approval_decision(
        {
            "schemaVersion": "1.0.0",
            "requestId": i["requestId"],
            "decision": "approve",
            "operatorId": "captain",
            "decidedAt": "2026-09-28T03:00:05Z",
            "idempotencyKey": "human-decision-drift",
            "correlationId": i["correlationId"],
            "sessionId": "session-cvw",
        },
        meta("decide-policy-drift", "human", "captain"),
        now="2026-09-28T03:00:05Z",
    )
    pd = policy()
    pd["requestedOperations"] = ["file.write"]
    svc.evaluate_policy(pd, meta("policy-drift", "governance_kernel", "gov-1"))
    with pytest.raises(
        AuthorityViolation, match="HUMAN_APPROVAL_GRANT_OPERATIONS_MISMATCH"
    ):
        svc.issue_grant_from_human_approval(
            i["requestId"],
            grant(),
            grant_meta(
                "grant-policy-drift", grant(), "approval-to-grant-policy-drift"
            ),
            use_id="approval-to-grant-policy-drift",
            now="2026-09-28T03:00:20Z",
        )


def test_same_human_approval_cannot_issue_second_grant():
    _store, svc = setup_service()
    svc.issue_grant_from_human_approval(
        intent()["requestId"],
        grant(),
        grant_meta("grant-first", grant(), "approval-to-grant-first"),
        use_id="approval-to-grant-first",
        now="2026-09-28T03:00:20Z",
    )
    g2 = copy.deepcopy(grant())
    g2["grantId"] = "grant-human-capability-2"
    with pytest.raises(AuthorityViolation, match="HUMAN_APPROVAL_NOT_APPROVED"):
        svc.issue_grant_from_human_approval(
            intent()["requestId"],
            g2,
            grant_meta("grant-second", g2, "approval-to-grant-second"),
            use_id="approval-to-grant-second",
            now="2026-09-28T03:00:21Z",
        )

def test_legacy_issue_grant_cannot_bypass_required_human_approval():
    _store, svc = setup_service()
    with pytest.raises(
        AuthorityViolation, match="HUMAN_APPROVAL_GRANT_MUST_USE_ATOMIC_APPROVAL_TRANSFER"
    ):
        svc.issue_grant(
            grant(),
            meta("legacy-grant-bypass", "governance_kernel", "gov-1"),
        )


def test_atomic_transfer_rejects_wrong_approval_request_id():
    _store, svc = setup_service()
    g = grant()
    g["approvalRequestId"] = "approval-other"
    with pytest.raises(
        AuthorityViolation, match="HUMAN_APPROVAL_GRANT_REQUEST_ID_MISMATCH"
    ):
        svc.issue_grant_from_human_approval(
            intent()["requestId"],
            g,
            grant_meta(
                "grant-wrong-approval-id", g, "approval-to-grant-wrong-id"
            ),
            use_id="approval-to-grant-wrong-id",
            now="2026-09-28T03:00:20Z",
        )

@pytest.mark.parametrize(
    "mutator,code",
    [
        (
            lambda g: g.update(subject={"actorId": "different-executor", "kind": "execution_plane"}),
            "HUMAN_APPROVAL_GRANT_SUBJECT_MISMATCH",
        ),
        (
            lambda g: g.update(conditions=[]),
            "HUMAN_APPROVAL_GRANT_CONDITIONS_MISMATCH",
        ),
        (
            lambda g: g.update(validUntil="2031-01-01T00:00:00Z"),
            "HUMAN_APPROVAL_GRANT_OUTLIVES_APPROVAL",
        ),
        (
            lambda g: g.update(issuedAt="2026-09-28T02:00:00Z"),
            "HUMAN_APPROVAL_GRANT_ISSUED_BEFORE_DECISION",
        ),
    ],
)
def test_grant_cannot_drift_policy_or_approval_time_bounds(mutator, code):
    _store, svc = setup_service()
    g = grant()
    mutator(g)
    with pytest.raises(AuthorityViolation, match=code):
        svc.issue_grant_from_human_approval(
            intent()["requestId"],
            g,
            grant_meta("grant-boundary-" + code.lower(), g, "approval-boundary"),
            use_id="approval-boundary",
            now="2026-09-28T03:00:20Z",
        )


def test_atomic_grant_recomputes_semantic_fingerprint():
    _store, svc = setup_service()
    g = grant()
    bad = meta("grant-bad-fingerprint", "governance_kernel", "gov-1")
    with pytest.raises(
        IdempotencyConflict,
        match="operation fingerprint does not match semantic request",
    ):
        svc.issue_grant_from_human_approval(
            intent()["requestId"],
            g,
            bad,
            use_id="approval-bad-fingerprint",
            now="2026-09-28T03:00:20Z",
        )


def test_atomic_grant_idempotent_replay_requires_same_semantics():
    _store, svc = setup_service()
    g = grant()
    use_id = "approval-replay"
    metadata = grant_meta("grant-replay", g, use_id)
    first = svc.issue_grant_from_human_approval(
        intent()["requestId"], g, metadata, use_id=use_id,
        now="2026-09-28T03:00:20Z",
    )
    second = svc.issue_grant_from_human_approval(
        intent()["requestId"], g, metadata, use_id=use_id,
        now="2026-09-28T03:00:20Z",
    )
    assert first["grantState"] == "granted"
    assert second["status"] == "idempotent"
    assert second["approvalState"] == "consumed"
    assert second["grantState"] == "granted"
