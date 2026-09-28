from __future__ import annotations

import hashlib
import json
from pathlib import Path

from capt_runtime import commands, contracts
from capt_runtime.aggregates import CapabilityAggregate, ClaimAggregate, ToolExecutionAggregate
from capt_runtime.composition import create_runtime
from capt_runtime.tool_broker import tool_request_fingerprint


WORK_CONTRACT_DIGEST = "sha256:" + ("c" * 64)
CONTENT = "CAPT_VERIFIED_WORK_OK\n"
EXPECTED_FILE_DIGEST = "sha256:" + hashlib.sha256(CONTENT.encode("utf-8")).hexdigest()


def _meta(step: str, actor_kind: str, actor_id: str) -> dict:
    return commands.command(
        command_id="cmd-cvw-" + step,
        idempotency_key="idem-cvw-" + step,
        operation_fingerprint=commands.fingerprint("cvw-" + step, {"step": step}),
        correlation_id="corr-cvw-e2e",
        actor_id=actor_id,
        actor_kind=actor_kind,
        issued_at="2026-09-28T04:00:00Z",
        replay_policy="never",
    )


def _intent(root: Path) -> dict:
    scope = {"kind": "filesystem", "rootPath": str(root), "recursive": True}
    return {
        "schemaVersion": "1.0.0",
        "missionId": "m-cvw-e2e",
        "taskId": "t-cvw-e2e",
        "requestId": "approval-cvw-e2e",
        "objective": "Write the exact fixture and prove the deterministic postcondition.",
        "rawRequest": "Write the exact fixture and prove the deterministic postcondition.",
        "normalizedRequest": "write the exact fixture and prove the deterministic postcondition.",
        "scope": scope,
        "constraints": [
            {
                "kind": "resource_boundary",
                "constraintId": "wc-root",
                "origin": "explicit_user",
                "scope": scope,
            },
            {
                "kind": "forbidden_operation",
                "constraintId": "wc-no-network-or-git-push",
                "origin": "explicit_user",
                "operations": ["git.push", "network.access"],
            },
        ],
        "successCriteria": [
            {
                "criterionId": "tests-pass",
                "statement": "The exact file exists with the required bytes and deterministic test exits zero.",
                "requiresVerification": True,
            }
        ],
        "terminationCriteria": [
            {
                "criterionId": "wc-boundary-violation",
                "statement": "Any frozen WorkContract boundary violation terminates the mission.",
                "terminalState": "failed",
            }
        ],
        "unresolvedAmbiguities": [],
        "requiresApproval": True,
        "requestedCapability": "cap.cvw.execute",
        "operations": ["file.write", "terminal.exec"],
        "consequential": True,
        "capabilitySubject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "capabilityConditions": [{"kind": "requires_approval", "approverRole": "human_operator"}],
        "capabilityMaxUses": 2,
        "maxAttempts": 2,
        "resource": str(root),
        "operation": "VerifiedWorkExecution",
        "riskClassification": "consequential",
        "policyReason": "Exact WorkContract-bound human approval is required.",
        "expiresAt": "2030-01-01T00:00:00Z",
        "remainingUses": 1,
        "correlationId": "corr-cvw-e2e",
        "externalCommitments": [
            {
                "kind": "inversion.work-contract.v0.1",
                "digest": WORK_CONTRACT_DIGEST,
                "reference": "work-cvw-e2e-001",
            }
        ],
    }


def _policy(root: Path) -> dict:
    intent = _intent(root)
    return {
        "schemaVersion": "1.0.0",
        "policyDecisionId": "pd-cvw-e2e",
        "policyBundleDigest": contracts.digest(
            {"policy": "cvw-e2e", "contract": WORK_CONTRACT_DIGEST}
        ),
        "effect": "allow_with_conditions",
        "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "missionId": intent["missionId"],
        "taskId": intent["taskId"],
        "requestedOperations": list(intent["operations"]),
        "requestedScope": dict(intent["scope"]),
        "conditions": [{"kind": "requires_approval", "approverRole": "human_operator"}],
        "rationale": "Allow only the exact human-approved bounded Verified Work operations.",
        "decidedBy": {"actorId": "gov-cvw", "kind": "governance_kernel"},
        "decidedAt": "2026-09-28T04:00:10Z",
        "externalCommitments": list(intent["externalCommitments"]),
    }


def _grant(root: Path) -> dict:
    intent = _intent(root)
    policy = _policy(root)
    return {
        "schemaVersion": "1.0.0",
        "grantId": "grant-cvw-e2e",
        "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
        "capabilityId": intent["requestedCapability"],
        "operations": list(intent["operations"]),
        "scope": dict(intent["scope"]),
        "policyDecisionId": policy["policyDecisionId"],
        "policyBundleDigest": policy["policyBundleDigest"],
        "approvalRequestId": intent["requestId"],
        "conditions": list(policy["conditions"]),
        "maxUses": 2,
        "validFrom": "2026-09-28T00:00:00Z",
        "validUntil": "2030-01-01T00:00:00Z",
        "issuedBy": {"actorId": "gov-cvw", "kind": "governance_kernel"},
        "issuedAt": "2026-09-28T04:00:20Z",
        "externalCommitments": list(intent["externalCommitments"]),
    }


def _lease(root: Path) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "leaseId": "lease-cvw-e2e",
        "grantId": "grant-cvw-e2e",
        "missionId": "m-cvw-e2e",
        "taskId": "t-cvw-e2e",
        "executionContextId": "execctx-cvw-e2e",
        "operations": ["file.write", "terminal.exec"],
        "scope": {"kind": "filesystem", "rootPath": str(root), "recursive": True},
        "maxUses": 2,
        "validFrom": "2026-09-28T00:00:00Z",
        "validUntil": "2030-01-01T00:00:00Z",
        "activatedAt": "2026-09-28T04:00:30Z",
    }


def _tool_request(
    *,
    root: Path,
    tool_id: str,
    operation: str,
    arguments: list[dict],
    idem: str,
    target: str,
) -> dict:
    request = {
        "schemaVersion": "1.0.0",
        "toolRequestId": "req-" + idem,
        "toolId": tool_id,
        "operation": operation,
        "arguments": arguments,
        "consequential": True,
        "grantId": "grant-cvw-e2e",
        "leaseId": "lease-cvw-e2e",
        "reservationId": None,
        "backendId": "local",
        "targetIdentity": target,
        "filesystemScope": str(root),
        "idempotencyKey": idem,
        "operationFingerprint": "sha256:" + ("0" * 64),
        "replayPolicy": "never",
        "requestedAt": "2026-09-28T04:01:00Z",
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _run_envelope(request: dict, *, command_id: str) -> dict:
    return {
        "commandId": command_id,
        "operatorId": "captain-test",
        "sessionId": "session-cvw-e2e",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-cvw-e2e",
        "idempotencyKey": request["idempotencyKey"],
        "timestamp": "2026-09-28T04:01:00Z",
        "op": "run_tool",
        "payload": request,
    }


def _evidence_artifact(root: Path) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "evidenceId": "ev-cvw-artifact",
        "missionId": "m-cvw-e2e",
        "taskId": "t-cvw-e2e",
        "evidence": {
            "kind": "artifact_hash",
            "artifactPath": str(root / "answer.txt"),
            "artifactDigest": EXPECTED_FILE_DIGEST,
        },
        "collectedBy": {"actorId": "tool-broker", "kind": "execution_plane"},
        "collectedAt": "2026-09-28T04:02:00Z",
        "trust": "capt_authoritative",
    }


def _evidence_command(command_output_digest: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "evidenceId": "ev-cvw-command",
        "missionId": "m-cvw-e2e",
        "taskId": "t-cvw-e2e",
        "evidence": {
            "kind": "command_exit",
            "command": "python3 -c <bounded deterministic file assertion>",
            "exitCode": 0,
            "outputDigest": command_output_digest,
        },
        "collectedBy": {"actorId": "tool-broker", "kind": "execution_plane"},
        "collectedAt": "2026-09-28T04:02:00Z",
        "trust": "capt_authoritative",
    }


def test_verified_work_real_tool_effect_to_verified_claim(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "runtime.db"))
    work_root = tmp_path / "work"
    work_root.mkdir()
    try:
        svc = runtime.service
        intent = _intent(work_root)

        created = svc.create_mission_with_approval(
            intent, _meta("mission", "human", "captain-test")
        )
        assert created["status"] == "applied"

        svc.submit_human_approval_decision(
            {
                "schemaVersion": "1.0.0",
                "requestId": intent["requestId"],
                "decision": "approve",
                "operatorId": "captain-test",
                "decidedAt": "2026-09-28T04:00:05Z",
                "note": "Test-only explicit approval of the exact bounded WorkContract fixture.",
                "idempotencyKey": "human-cvw-e2e",
                "correlationId": "corr-cvw-e2e",
                "sessionId": "session-cvw-e2e",
            },
            _meta("approval", "human", "captain-test"),
            now="2026-09-28T04:00:05Z",
        )

        svc.evaluate_policy(
            _policy(work_root), _meta("policy", "governance_kernel", "gov-cvw")
        )
        grant = _grant(work_root)
        grant_meta = commands.command(
            command_id="cmd-cvw-grant",
            idempotency_key="idem-cvw-grant",
            operation_fingerprint=commands.fingerprint(
                "issue_grant_from_human_approval",
                {
                    "requestId": intent["requestId"],
                    "grant": grant,
                    "useId": "approval-to-grant-cvw-e2e",
                },
            ),
            correlation_id="corr-cvw-e2e",
            actor_id="gov-cvw",
            actor_kind="governance_kernel",
            issued_at="2026-09-28T04:00:20Z",
            replay_policy="never",
        )
        issued = svc.issue_grant_from_human_approval(
            intent["requestId"],
            grant,
            grant_meta,
            use_id="approval-to-grant-cvw-e2e",
            now="2026-09-28T04:00:20Z",
        )
        assert issued["approvalState"] == "consumed"
        assert issued["grantState"] == "granted"

        svc.activate_lease(
            _lease(work_root), _meta("lease", "governance_kernel", "gov-cvw")
        )

        relay = runtime.command_service("captain-test", "session-cvw-e2e")
        target = work_root / "answer.txt"

        write_request = _tool_request(
            root=work_root,
            tool_id="file.operations",
            operation="file.write",
            arguments=[
                {"kind": "path", "name": "path", "value": str(target)},
                {"kind": "string", "name": "content", "value": CONTENT},
            ],
            idem="cvw-write-1",
            target=str(target),
        )
        write_receipt = relay.execute(
            _run_envelope(write_request, command_id="cmd-cvw-run-write")
        )
        assert write_receipt["status"] == "accepted"
        assert write_receipt["result"]["status"] == "succeeded"
        assert target.read_text() == CONTENT
        assert "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest() == EXPECTED_FILE_DIGEST

        write_execution_id = write_receipt["result"]["toolExecutionId"]
        write_execution = runtime.store.require_state(
            ToolExecutionAggregate.stream_id(write_execution_id)
        )
        assert write_execution["state"] == "completed"
        assert write_execution["worldReceipt"] is not None
        assert write_execution["settlementStatus"] == "settled"

        verify_argv = json.dumps(
            [
                "/usr/bin/python3",
                "-c",
                (
                    "from pathlib import Path; "
                    "p=Path('answer.txt'); "
                    "assert p.read_text() == 'CAPT_VERIFIED_WORK_OK\\n'"
                ),
            ]
        )
        verify_request = _tool_request(
            root=work_root,
            tool_id="terminal.local",
            operation="terminal.exec",
            arguments=[
                {"kind": "string", "name": "argv", "value": verify_argv},
                {"kind": "path", "name": "cwd", "value": str(work_root)},
                {"kind": "integer", "name": "timeout_ms", "value": 30_000},
            ],
            idem="cvw-verify-1",
            target=str(work_root),
        )
        verify_receipt = relay.execute(
            _run_envelope(verify_request, command_id="cmd-cvw-run-verify")
        )
        assert verify_receipt["status"] == "accepted"
        assert verify_receipt["result"]["status"] == "succeeded"

        verify_execution_id = verify_receipt["result"]["toolExecutionId"]
        verify_execution = runtime.store.require_state(
            ToolExecutionAggregate.stream_id(verify_execution_id)
        )
        assert verify_execution["state"] == "completed"
        assert verify_execution["result"]["exitCode"] == 0

        capability = runtime.store.require_state(
            CapabilityAggregate.stream_id("grant-cvw-e2e")
        )
        assert capability["approvalRequestId"] == "approval-cvw-e2e"
        assert capability["externalCommitments"] == intent["externalCommitments"]
        assert capability["usesConsumed"] == 2

        claim = {
            "schemaVersion": "1.0.0",
            "claimId": "claim-cvw-tests-pass",
            "missionId": "m-cvw-e2e",
            "taskId": "t-cvw-e2e",
            "kind": "completion",
            "statement": intent["successCriteria"][0]["statement"],
            "evidenceIds": ["ev-cvw-artifact", "ev-cvw-command"],
            "verificationId": None,
            "promotionState": "proposed",
            "proposedBy": {"actorId": "tool-broker", "kind": "execution_plane"},
            "proposedAt": "2026-09-28T04:02:00Z",
            "sourceProposalId": None,
        }
        artifact_evidence = _evidence_artifact(work_root)
        command_evidence = _evidence_command(verify_execution["result"]["outputDigest"])
        svc.propose_claim_with_evidence(
            claim,
            [
                (
                    artifact_evidence,
                    _meta("evidence-artifact", "execution_plane", "tool-broker"),
                ),
                (
                    command_evidence,
                    _meta("evidence-command", "execution_plane", "tool-broker"),
                ),
            ],
            _meta("claim", "execution_plane", "tool-broker"),
        )

        verification = {
            "schemaVersion": "1.0.0",
            "verificationId": "verification-cvw-tests-pass",
            "claimId": "claim-cvw-tests-pass",
            "strategy": "test_exit_status",
            "status": {
                "kind": "verified",
                "supportingEvidenceIds": ["ev-cvw-artifact", "ev-cvw-command"],
            },
            "verifiedBy": {"actorId": "verify-cvw", "kind": "verification_plane"},
            "verifiedAt": "2026-09-28T04:02:10Z",
        }
        svc.record_verification(
            verification, _meta("verification", "verification_plane", "verify-cvw")
        )

        svc.decide_claim(
            {
                "schemaVersion": "1.0.0",
                "decisionId": "decision-cvw-tests-pass",
                "claimId": "claim-cvw-tests-pass",
                "verdict": "accept",
                "rationale": "Independent CAPT verification cites both authoritative evidence records.",
                "decidedBy": {"actorId": "claimguard-cvw", "kind": "claim_authority"},
                "decidedAt": "2026-09-28T04:02:20Z",
                "verificationId": "verification-cvw-tests-pass",
                "qualification": None,
            },
            _meta("claim-decision", "claim_authority", "claimguard-cvw"),
        )
        claim_state = runtime.store.require_state(
            ClaimAggregate.stream_id("claim-cvw-tests-pass")
        )
        assert claim_state["verificationStatus"] == "verified"
        assert claim_state["promotionState"] == "accepted"

        # Same settled request must replay rather than redispatch or consume
        # another capability use.
        replay = relay.execute(
            _run_envelope(write_request, command_id="cmd-cvw-run-write")
        )
        assert replay["status"] == "idempotent"
        assert replay["result"]["replayed"] is True
        capability_after_replay = runtime.store.require_state(
            CapabilityAggregate.stream_id("grant-cvw-e2e")
        )
        assert capability_after_replay["usesConsumed"] == 2
        assert target.read_text() == CONTENT

        events = runtime.store.read_events()
        event_types = [e["eventType"] for e in events]
        assert "HumanApprovalConsumedForCapability" in event_types
        assert "CapabilityGranted" in event_types
        assert "ToolExecutionEffectObserved" in event_types
        assert "EvidenceRecorded" in event_types
        assert "ClaimVerified" in event_types
        assert "ClaimGuardDecided" in event_types

        approval_event = next(
            e for e in events if e["eventType"] == "HumanApprovalConsumedForCapability"
        )
        grant_event = next(
            e
            for e in events
            if e["eventType"] == "CapabilityGranted"
            and e["payload"]["grant"]["grantId"] == "grant-cvw-e2e"
        )
        assert approval_event["globalSequence"] + 1 == grant_event["globalSequence"]
        assert approval_event["causationId"] == grant_event["causationId"]
    finally:
        runtime.close()
