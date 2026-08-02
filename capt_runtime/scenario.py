"""The M0-A proof scenario.

Drives the exact sequence required by the architecture specification:

    MissionCreated -> PolicyEvaluated -> CapabilityGranted
    -> CapabilityLeaseActivated -> TaskTransitioned -> CheckpointCreated
    -> ProcessRestarted -> StateReplayed

`build_scenario` runs steps 1-6 against a real on-disk store. The restart and
replay steps are performed by a SEPARATE PROCESS in the conformance suite, so
the proof does not depend on in-memory state surviving.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import commands
from .checkpoint import create_checkpoint
from .contracts import digest
from .services import RuntimeService
from .store import EventStore

POLICY_BUNDLE_DIGEST = digest({"policyBundle": "m0a-demo", "version": 1})

GOVERNANCE_ACTOR = {"actorId": "gk-1", "kind": "governance_kernel", "displayName": None}
EXECUTION_ACTOR = {"actorId": "exec-1", "kind": "execution_plane", "displayName": None}

MISSION_ID = "m-m0a-001"
TASK_ID = "t-m0a-001"
GRANT_ID = "g-m0a-001"
LEASE_ID = "l-m0a-001"
WORKTREE = "/tmp/capt-m0a-scenario"


def _meta(
    step: str,
    actor: Dict[str, Any],
    issued_at: str,
    operation: str,
    subject: Dict[str, Any],
) -> Dict[str, Any]:
    return commands.command(
        command_id="cmd-" + step,
        idempotency_key="idem-" + step,
        operation_fingerprint=commands.fingerprint(operation, subject),
        correlation_id="corr-m0a",
        actor_id=actor["actorId"],
        actor_kind=actor["kind"],
        issued_at=issued_at,
        replay_policy="never",
    )


def mission_spec() -> Dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "missionId": MISSION_ID,
        "rawRequest": "Prove the CAPT M0-A contract and state transition gate.",
        "normalizedRequest": "prove capt m0-a contract and state transition gate",
        "objectives": [
            {
                "objectiveId": "obj-1",
                "statement": "Demonstrate transactional state transitions with replay.",
                "priority": 1,
            }
        ],
        "constraints": [
            {
                "kind": "resource_boundary",
                "constraintId": "con-1",
                "origin": "explicit_user",
                "scope": {"kind": "filesystem", "rootPath": WORKTREE, "recursive": True},
            }
        ],
        "successCriteria": [
            {
                "criterionId": "sc-1",
                "statement": "Checkpoint replay equals full replay.",
                "requiresVerification": True,
            }
        ],
        "terminationCriteria": [
            {
                "criterionId": "tc-1",
                "statement": "Any invariant violation terminates the mission.",
                "terminalState": "failed",
            }
        ],
        "unresolvedAmbiguities": [],
        "taskGraphId": None,
        "createdAt": "2026-08-02T00:00:00Z",
    }


def policy_decision() -> Dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "policyDecisionId": "pd-m0a-001",
        "policyBundleDigest": POLICY_BUNDLE_DIGEST,
        "effect": "allow_with_conditions",
        "subject": EXECUTION_ACTOR,
        "missionId": MISSION_ID,
        "taskId": TASK_ID,
        "requestedOperations": ["fs.write"],
        "requestedScope": {"kind": "filesystem", "rootPath": WORKTREE, "recursive": True},
        "conditions": [{"kind": "isolated_worktree", "worktreeRoot": WORKTREE}],
        "rationale": "Scoped write inside an isolated worktree for the M0-A proof.",
        "decidedBy": GOVERNANCE_ACTOR,
        "decidedAt": "2026-08-02T00:01:00Z",
    }


def capability_grant() -> Dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "grantId": GRANT_ID,
        "subject": EXECUTION_ACTOR,
        "capabilityId": "cap.fs.write",
        "operations": ["fs.write"],
        "scope": {"kind": "filesystem", "rootPath": WORKTREE, "recursive": True},
        "policyDecisionId": "pd-m0a-001",
        "policyBundleDigest": POLICY_BUNDLE_DIGEST,
        "conditions": [{"kind": "isolated_worktree", "worktreeRoot": WORKTREE}],
        "maxUses": 2,
        "validFrom": "2026-08-02T00:02:00Z",
        "validUntil": "2026-08-02T06:00:00Z",
        "issuedBy": GOVERNANCE_ACTOR,
        "issuedAt": "2026-08-02T00:02:00Z",
    }


def capability_lease() -> Dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "leaseId": LEASE_ID,
        "grantId": GRANT_ID,
        "missionId": MISSION_ID,
        "taskId": TASK_ID,
        "executionContextId": "ec-m0a-001",
        "operations": ["fs.write"],
        # Narrower than the grant: a subdirectory, non-recursive.
        "scope": {"kind": "filesystem", "rootPath": WORKTREE + "/out", "recursive": False},
        "maxUses": 1,
        "validFrom": "2026-08-02T00:03:00Z",
        "validUntil": "2026-08-02T05:00:00Z",
        "activatedAt": "2026-08-02T00:03:00Z",
    }


def task_node() -> Dict[str, Any]:
    return {
        "taskId": TASK_ID,
        "missionId": MISSION_ID,
        "title": "Write the M0-A proof artifact",
        "state": "pending",
        "consequential": True,
        "capabilityRequirements": [
            {
                "requirementId": "req-1",
                "capabilityId": "cap.fs.write",
                "operations": ["fs.write"],
                "scope": {
                    "kind": "filesystem",
                    "rootPath": WORKTREE + "/out",
                    "recursive": False,
                },
            }
        ],
        "assignedDriverId": None,
        "attempt": 0,
        "maxAttempts": 3,
        "recoveryState": "none",
    }


def build_scenario(db_path: str) -> Dict[str, Any]:
    """Run steps 1-6 of the proof sequence against a real store."""
    store = EventStore(db_path)
    service = RuntimeService(store)

    spec = mission_spec()
    service.create_mission(
        spec, _meta("001-mission", {"actorId": "captain", "kind": "human"},
                    "2026-08-02T00:00:00Z", "create_mission", {"missionId": MISSION_ID})
    )

    decision = policy_decision()
    service.evaluate_policy(
        decision,
        _meta("002-policy", GOVERNANCE_ACTOR, "2026-08-02T00:01:00Z",
              "evaluate_policy", {"policyDecisionId": decision["policyDecisionId"]}),
    )

    grant = capability_grant()
    service.issue_grant(
        grant,
        _meta("003-grant", GOVERNANCE_ACTOR, "2026-08-02T00:02:00Z",
              "issue_grant", {"grantId": GRANT_ID}),
    )

    lease = capability_lease()
    service.activate_lease(
        lease,
        _meta("004-lease", GOVERNANCE_ACTOR, "2026-08-02T00:03:00Z",
              "activate_lease", {"leaseId": LEASE_ID}),
    )

    node = task_node()
    service.create_task(
        node,
        _meta("005-task", {"actorId": "cog-1", "kind": "cognitive_plane"},
              "2026-08-02T00:04:00Z", "create_task", {"taskId": TASK_ID}),
    )
    service.transition_task(
        TASK_ID, "ready", "dependencies satisfied",
        _meta("006-ready", EXECUTION_ACTOR, "2026-08-02T00:05:00Z",
              "transition_task", {"taskId": TASK_ID, "to": "ready"}),
    )
    service.transition_task(
        TASK_ID, "assigned", "assigned to execution context",
        _meta("007-assigned", EXECUTION_ACTOR, "2026-08-02T00:06:00Z",
              "transition_task", {"taskId": TASK_ID, "to": "assigned"}),
    )
    service.transition_task(
        TASK_ID, "running", "lease validated, work started",
        _meta("008-running", EXECUTION_ACTOR, "2026-08-02T00:07:00Z",
              "transition_task", {"taskId": TASK_ID, "to": "running"}),
    )

    manifest = create_checkpoint(
        store,
        checkpoint_id="cp-m0a-001",
        created_at="2026-08-02T00:08:00Z",
        policy_bundle_digest=POLICY_BUNDLE_DIGEST,
    )

    summary = {
        "headSequence": store.head_sequence(),
        "checkpointId": manifest["checkpointId"],
        "ledgerDigest": manifest["ledgerDigest"],
        "recoveryState": manifest["recoveryState"]["kind"],
        "eventTypes": [e["eventType"] for e in store.read_events()],
    }
    store.close()
    return summary
