from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.contracts import require
from capt_runtime.errors import ContractViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


WORK_CONTRACT_DIGEST = "sha256:" + ("a" * 64)


def _write_intent():
    return {
        "schemaVersion": "1.0.0",
        "missionId": "m-verified-work-1",
        "taskId": "t-verified-work-1",
        "requestId": "approval-verified-work-1",
        "objective": "Apply the bounded repository repair and run the declared tests.",
        "rawRequest": "Apply the bounded repository repair and run the declared tests.",
        "normalizedRequest": "apply the bounded repository repair and run the declared tests.",
        "scope": {
            "kind": "filesystem",
            "rootPath": "/tmp/capt-verified-work-fixture",
            "recursive": True,
        },
        "constraints": [
            {
                "kind": "resource_boundary",
                "constraintId": "wc-root",
                "origin": "explicit_user",
                "scope": {
                    "kind": "filesystem",
                    "rootPath": "/tmp/capt-verified-work-fixture",
                    "recursive": True,
                },
            },
            {
                "kind": "forbidden_operation",
                "constraintId": "wc-no-push",
                "origin": "explicit_user",
                "operations": ["git.push"],
            },
        ],
        "successCriteria": [
            {
                "criterionId": "tests-pass",
                "statement": "Declared repository test suite exits zero.",
                "requiresVerification": True,
            }
        ],
        "terminationCriteria": [
            {
                "criterionId": "contract-boundary-violation",
                "statement": "Any WorkContract boundary violation terminates the mission.",
                "terminalState": "failed",
            }
        ],
        "unresolvedAmbiguities": [],
        "requiresApproval": True,
        "requestedCapability": "cap.fs.write",
        "operations": ["repository.read", "repository.write", "filesystem.read", "filesystem.write"],
        "consequential": True,
        "capabilitySubject": {"actorId": "exec-cvw", "kind": "execution_plane"},
        "capabilityConditions": [{"kind": "requires_approval", "approverRole": "human_operator"}],
        "capabilityMaxUses": 2,
        "maxAttempts": 2,
        "resource": "/tmp/capt-verified-work-fixture",
        "operation": "RepositoryWrite",
        "riskClassification": "consequential",
        "policyReason": "Frozen WorkContract authorizes only the declared bounded repository repair.",
        "expiresAt": "2026-09-29T03:00:00Z",
        "remainingUses": 1,
        "correlationId": "wc-fixture-001",
        "externalCommitments": [
            {
                "kind": "inversion.work-contract.v0.1",
                "digest": WORK_CONTRACT_DIGEST,
                "reference": "work-fixture-001",
            }
        ],
    }


def _meta(intent):
    return commands.command(
        command_id="cmd-verified-work-1",
        idempotency_key="idem-verified-work-1",
        operation_fingerprint=commands.fingerprint("create_mission", intent),
        correlation_id="wc-fixture-001",
        actor_id="captain",
        actor_kind="human",
        issued_at="2026-09-28T03:00:00Z",
    )


def test_operator_intent_can_express_bounded_write_contract():
    intent = _write_intent()
    require("OperatorMissionIntent", intent)

    store = EventStore(":memory:")
    svc = RuntimeService(store)
    result = svc.create_mission_with_approval(intent, _meta(intent))

    assert result["status"] == "applied"

    mission = store.require_state("mission-" + intent["missionId"])
    task = store.require_state("task-" + intent["taskId"])
    approval = store.require_state("human_approval-" + intent["requestId"])

    assert mission["externalCommitments"] == intent["externalCommitments"]
    assert task["consequential"] is True
    assert task["maxAttempts"] == 2
    requirement = task["capabilityRequirements"][0]
    assert requirement["capabilityId"] == "cap.fs.write"
    assert requirement["operations"] == intent["operations"]
    assert requirement["scope"] == intent["scope"]

    assert approval["externalCommitments"] == intent["externalCommitments"]
    assert approval["remainingUses"] == 1
    assert approval["expiresAt"] == intent["expiresAt"]
    assert approval["correlationId"] == intent["correlationId"]


def test_external_commitment_digest_fails_closed():
    intent = _write_intent()
    intent["externalCommitments"][0]["digest"] = "sha256:deadbeef"
    with pytest.raises(ContractViolation):
        require("OperatorMissionIntent", intent)


def test_empty_operation_set_fails_closed():
    intent = _write_intent()
    intent["operations"] = []
    with pytest.raises(ContractViolation):
        require("OperatorMissionIntent", intent)


def test_retry_ceiling_above_contract_max_fails_closed():
    intent = _write_intent()
    intent["maxAttempts"] = 101
    with pytest.raises(ContractViolation):
        require("OperatorMissionIntent", intent)
