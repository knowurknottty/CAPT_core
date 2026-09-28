from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from capt_runtime import commands
from capt_runtime.aggregates import CapabilityAggregate, HumanApprovalAggregate
from capt_runtime.composition import create_runtime


def _meta(intent: dict) -> dict:
    return commands.command(
        command_id="cmd-approved-cap-mission",
        idempotency_key="idem-approved-cap-mission",
        operation_fingerprint=commands.fingerprint("create_mission", intent),
        correlation_id="corr-approved-cap",
        actor_id="captain-test",
        actor_kind="human",
        issued_at="2026-09-28T04:20:00Z",
        replay_policy="never",
    )


def _intent(root: Path) -> dict:
    scope = {"kind": "filesystem", "rootPath": str(root), "recursive": True}
    return {
        "schemaVersion": "1.0.0",
        "missionId": "m-approved-cap",
        "taskId": "t-approved-cap",
        "requestId": "approval-approved-cap",
        "objective": "Authorize exactly one bounded write and one bounded verification.",
        "rawRequest": "Authorize exactly one bounded write and one bounded verification.",
        "normalizedRequest": "authorize exactly one bounded write and one bounded verification.",
        "scope": scope,
        "constraints": [],
        "successCriteria": [
            {
                "criterionId": "postcondition",
                "statement": "Bounded postcondition is independently verified.",
                "requiresVerification": True,
            }
        ],
        "terminationCriteria": [],
        "unresolvedAmbiguities": [],
        "requiresApproval": True,
        "requestedCapability": "cap.cvw.execute",
        "operations": ["file.write", "terminal.exec"],
        "consequential": True,
        "capabilitySubject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "capabilityConditions": [
            {"kind": "requires_approval", "approverRole": "human_operator"},
            {"kind": "no_network"},
        ],
        "capabilityMaxUses": 2,
        "maxAttempts": 2,
        "resource": str(root),
        "operation": "VerifiedWorkExecution",
        "riskClassification": "consequential",
        "policyReason": "Exact human approval is required before capability materialization.",
        "expiresAt": "2099-01-01T00:00:00Z",
        "remainingUses": 1,
        "correlationId": "corr-approved-cap",
        "externalCommitments": [
            {
                "kind": "inversion.work-contract.v0.1",
                "digest": "sha256:" + ("d" * 64),
                "reference": "work-approved-cap",
            }
        ],
    }


def _command(*, command_id: str, idem: str, op: str, payload: dict) -> dict:
    return {
        "commandId": command_id,
        "operatorId": "captain-test",
        "sessionId": "session-approved-cap",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-approved-cap",
        "idempotencyKey": idem,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "op": op,
        "payload": payload,
    }


def _approved_runtime(tmp_path: Path):
    runtime = create_runtime(str(tmp_path / "runtime.db"))
    root = tmp_path / "work"
    root.mkdir()
    intent = _intent(root)
    runtime.service.create_mission_with_approval(intent, _meta(intent))
    relay = runtime.command_service("captain-test", "session-approved-cap")
    decision = relay.execute(
        _command(
            command_id="cmd-approved-cap-decision",
            idem="idem-approved-cap-decision",
            op="submit_approval_decision",
            payload={
                "requestId": intent["requestId"],
                "decision": "approve",
                "note": "Approve only the exact bounded capability profile.",
            },
        )
    )
    assert decision["status"] == "accepted"
    return runtime, relay, root, intent


def test_operator_route_materializes_only_approved_capability(tmp_path: Path) -> None:
    runtime, relay, root, intent = _approved_runtime(tmp_path)
    try:
        cmd = _command(
            command_id="cmd-approved-cap-activate",
            idem="idem-approved-cap-activate",
            op="activate_approved_capability",
            payload={
                "requestId": intent["requestId"],
                "executionContextId": "execctx-approved-cap",
            },
        )
        receipt = relay.execute(cmd)
        assert receipt["status"] == "accepted"
        result = receipt["result"]

        approval = runtime.store.require_state(
            HumanApprovalAggregate.stream_id(intent["requestId"])
        )
        grant = runtime.store.require_state(
            CapabilityAggregate.stream_id(result["grantId"])
        )
        assert approval["state"] == "consumed"
        assert grant["approvalRequestId"] == intent["requestId"]
        assert grant["subjectActorId"] == "tool-broker"
        assert grant["operations"] == intent["operations"]
        assert grant["scope"] == intent["scope"]
        assert grant["conditions"] == intent["capabilityConditions"]
        assert grant["maxUses"] == intent["capabilityMaxUses"]
        assert grant["externalCommitments"] == intent["externalCommitments"]
        assert grant["lease"]["leaseId"] == result["leaseId"]
        assert grant["lease"]["executionContextId"] == "execctx-approved-cap"

        replay = relay.execute(cmd)
        assert replay["status"] == "idempotent"
        assert replay["result"] == result

        capability_events = [
            e
            for e in runtime.store.read_events()
            if e["eventType"] in {
                "HumanApprovalConsumedForCapability",
                "CapabilityGranted",
                "CapabilityLeaseActivated",
            }
        ]
        assert [e["eventType"] for e in capability_events] == [
            "HumanApprovalConsumedForCapability",
            "CapabilityGranted",
            "CapabilityLeaseActivated",
        ]
    finally:
        runtime.close()


def test_operator_route_rejects_semantic_authority_injection(tmp_path: Path) -> None:
    runtime, relay, _root, intent = _approved_runtime(tmp_path)
    try:
        receipt = relay.execute(
            _command(
                command_id="cmd-approved-cap-inject",
                idem="idem-approved-cap-inject",
                op="activate_approved_capability",
                payload={
                    "requestId": intent["requestId"],
                    "executionContextId": "execctx-approved-cap",
                    "operations": ["network.access"],
                },
            )
        )
        assert receipt["status"] == "rejected"
        assert receipt["classification"] == "malformed"
        approval = runtime.store.require_state(
            HumanApprovalAggregate.stream_id(intent["requestId"])
        )
        assert approval["state"] == "approved"
        assert not any(
            kind == "capability" for _sid, kind, _ver in runtime.store.all_aggregates()
        )
    finally:
        runtime.close()


def test_operator_route_requires_same_human_that_approved(tmp_path: Path) -> None:
    runtime, _relay, _root, intent = _approved_runtime(tmp_path)
    try:
        other = runtime.command_service("other-human", "session-other")
        receipt = other.execute(
            {
                **_command(
                    command_id="cmd-approved-cap-other",
                    idem="idem-approved-cap-other",
                    op="activate_approved_capability",
                    payload={
                        "requestId": intent["requestId"],
                        "executionContextId": "execctx-other",
                    },
                ),
                "operatorId": "other-human",
                "sessionId": "session-other",
            }
        )
        assert receipt["status"] == "rejected"
        assert "APPROVED_CAPABILITY_OPERATOR_MISMATCH" in receipt.get("detail", "")
    finally:
        runtime.close()

def test_generic_approval_cannot_be_promoted_to_capability(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "runtime-generic.db"))
    root = tmp_path / "generic-work"
    root.mkdir()
    try:
        generic = _intent(root)
        generic.pop("capabilitySubject")
        generic.pop("capabilityConditions")
        generic.pop("capabilityMaxUses")
        runtime.service.create_mission_with_approval(generic, _meta(generic))
        relay = runtime.command_service("captain-test", "session-approved-cap")
        decision = relay.execute(
            _command(
                command_id="cmd-generic-decision",
                idem="idem-generic-decision",
                op="submit_approval_decision",
                payload={
                    "requestId": generic["requestId"],
                    "decision": "approve",
                    "note": "Generic approval remains valid but is not capability-complete.",
                },
            )
        )
        assert decision["status"] == "accepted"

        receipt = relay.execute(
            _command(
                command_id="cmd-generic-activate",
                idem="idem-generic-activate",
                op="activate_approved_capability",
                payload={
                    "requestId": generic["requestId"],
                    "executionContextId": "execctx-generic",
                },
            )
        )
        assert receipt["status"] == "rejected"
        assert "APPROVED_CAPABILITY_SUBJECT_REQUIRED" in receipt.get("detail", "")
        approval = runtime.store.require_state(
            HumanApprovalAggregate.stream_id(generic["requestId"])
        )
        assert approval["state"] == "approved"
        assert not any(
            kind == "capability" for _sid, kind, _ver in runtime.store.all_aggregates()
        )
    finally:
        runtime.close()
