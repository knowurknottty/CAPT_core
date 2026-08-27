#!/usr/bin/env python3.12
"""CAPT Desktop Runtime M0 — local CAPT runtime service (authoritative side).

This process OWNS the authoritative CAPT state. It wraps the real
``capt_runtime`` RuntimeService + EventStore and exposes a *read-only* local
IPC surface to the desktop operator client. It is the single authority for
missions, tasks, capabilities, drivers, evidence, verification, ClaimGuard,
events, checkpoints, and replay. The desktop never touches the ledger
directly; it issues typed read queries over an authenticated Unix-domain
socket.

M0 is read-only: the service seeds one demonstration mission (using the real
RuntimeService and a real reference-driver read-only proof) and answers
read queries. No desktop-originated mutation is accepted in M0.

IPC transport: Unix domain socket. Authentication: a per-start session token
written to a 0600 file; the client must present it as the first framed
message or the connection is dropped.

Run:
  python3.12 desktop/capt_runtime_service.py --ledger <path> --sock <path> \
      --token-file <path> [--seed]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
UTC = timezone.utc
import getpass
import hashlib
import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import capt_runtime
from capt_runtime import commands, contracts
from capt_runtime.checkpoint import create_checkpoint
from capt_runtime.driver_host import DriverHost, tree_digest
from capt_runtime.drivers.openharness import OpenHarnessDriver, DESCRIPTOR as REF
from capt_runtime.drivers.registry import DriverRegistry
from capt_runtime.scenario import build_scenario
from capt_runtime.services import RuntimeService
from capt_runtime.errors import AuthorityViolation
from capt_runtime.store import EventStore
from capt_runtime.verification import (
    VerificationFailure,
    build_artifact_hash_evidence,
    build_contradicted_verification_result,
    build_verification_result,
    capture_git_status,
    guard_claim,
)
from capt_runtime.composition import RuntimeComposition, create_runtime
from capt_runtime.provider_endpoint import credential_required
from capt_runtime.operator_provenance import (
    build_cognitive_provenance, build_prompt_assembly, effective_context_budget,
)
from capt_runtime.model_approval_binding import (
    build_bound_model_operator_approval, staging_root_for_ledger,
)
from capt_runtime.prepared_execution import PreparedApprovedModelExecution, freeze
from capt_runtime.verification_baseline import capture_verification_baseline
from capt_runtime.authored_skills import (
    parse_authored_skill_request, prepare_runtime_skill_context, summarize_skill_context,
)

from desktop.m1_command_service import RuntimeCommandService

RUNTIME_VERSION = getattr(capt_runtime, "RUNTIME_VERSION", "0.1.0")
CONTRACT_SCHEMA_VERSION = "1.0.0"


def _test_fault(point: str) -> None:
    """Test-only crash seam for durable lifecycle boundary proof.

    It is inert unless a test explicitly supplies the exact environment value.
    A hard exit models process death: no exception handler is allowed to turn a
    missing persistence step into a fabricated outcome.
    """
    if os.environ.get("CAPT_TEST_OUROBOROS_CRASH_AFTER") == point:
        os._exit(86)


def _reconcile_stranded_driver_runs(runtime: RuntimeComposition, now: str) -> None:
    """Conservatively recover durable pre-restart DriverRun state.

    This is CAPT Core reconciliation over the existing EventStore, never a
    driver invocation. It gives a crashed command a durable exit path before a
    duplicate request can observe its idempotency admission.
    """
    store, svc = runtime.store, runtime.service
    for stream_id, kind, _version in store.all_aggregates():
        if kind != "driverrun":
            continue
        run = store.load_state(stream_id)
        if not run or run.get("state") not in ("created", "submitted", "running", "suspended", "completed"):
            continue
        run_id, task_id = run["driverRunId"], run["taskId"]
        def recovery_meta(step: str) -> Dict[str, Any]:
            return commands.command(
                command_id="cmd-recovery-" + run_id + ":" + step,
                idempotency_key="idem-recovery-" + run_id + ":" + step,
                operation_fingerprint=commands.fingerprint("recover_driver_run", {"driverRunId": run_id, "step": step}),
                correlation_id="corr-recovery-" + run_id, actor_id="exec-recovery",
                actor_kind="execution_plane", issued_at=now, replay_policy="never",
            )
        # A created run has not reached submission. Every later non-terminal
        # state is ambiguous: consume any open reservation and forbid replay.
        if run["state"] == "created":
            svc.transition_driver_run(run_id, "failed", recovery_meta("created-failed"))
            task = store.load_state("task-" + task_id)
            if task and task.get("state") in ("assigned", "running"):
                svc.transition_task(task_id, "failed", "restart before driver submission", recovery_meta("created-task-failed"))
            continue
        for cap_stream, cap_kind, _ in store.all_aggregates():
            if cap_kind != "capability":
                continue
            capability = store.load_state(cap_stream)
            if capability is None:
                continue
            lease = capability.get("lease")
            if not lease or lease.get("missionId") != run.get("missionId") or lease.get("taskId") != task_id:
                continue
            for reservation in capability.get("reservations", []):
                if reservation.get("state") != "open":
                    continue
                consumption = {
                    "schemaVersion": "1.0.0",
                    "consumptionId": "con-recovery-" + reservation["reservationId"],
                    "reservationId": reservation["reservationId"], "leaseId": reservation["leaseId"],
                    "outcome": "indeterminate", "sideEffectIdentity": run_id, "finalizedAt": now,
                }
                svc.finalize_use(capability["grantId"], consumption, recovery_meta("finalize-" + reservation["reservationId"]))
        if run["state"] == "submitted":
            svc.transition_driver_run(run_id, "lost", recovery_meta("submitted-lost"))
        elif run["state"] == "running":
            svc.transition_driver_run(run_id, "lost", recovery_meta("running-lost"))
        task = store.load_state("task-" + task_id)
        if task and task.get("state") == "running":
            svc.transition_task(task_id, "suspended", "restart requires governed reconciliation", recovery_meta("task-suspended"))


DEMO_MISSION_ID = "m-desktop-m0-demo"
DEMO_TASK_ID = "t-desktop-m0-demo"
DEMO_DRIVER_RUN_ID = "dr-desktop-m0-demo"
DEMO_GRANT_ID = "g-desktop-m0-demo"
DEMO_LEASE_ID = "l-desktop-m0-demo"
DEMO_CLAIM_ID = "cl-desktop-m0-demo"
DEMO_WORKTREE = "/tmp/capt-desktop-m0-demo-worktree"


# --------------------------------------------------------------------------
# Demo mission seeding (CAPT authority, server-side, read-only proof)
# --------------------------------------------------------------------------

def _meta(step, actor_kind, actor_id, operation, subject):
    return commands.command(
        command_id="cmd-demo-" + step,
        idempotency_key="idem-demo-" + step,
        operation_fingerprint=commands.fingerprint(operation, subject),
        correlation_id="corr-desktop-m0",
        actor_id=actor_id,
        actor_kind=actor_kind,
        issued_at="2026-08-03T00:00:00Z",
        replay_policy="never",
    )


def seed_demo_mission(runtime: RuntimeComposition) -> Dict[str, Any]:
    """Create a faithful read-only demonstration mission using real CAPT.

    Builds the M0-A governance/policy/capability/task sequence, then runs a
    REAL reference-driver read-only proof through DriverHost to produce a
    DriverRun, observation, artifact, verification result, and a bounded
    ClaimGuard claim. All authoritative state is written by CAPT, not the
    desktop.
    """
    # Idempotent: if the demo mission already exists, do not duplicate.
    store = runtime.store
    if store.aggregate_version("mission-" + DEMO_MISSION_ID) > 0:
        return {"seeded": False, "reason": "demo mission already present"}

    svc = runtime.service

    mission_spec = {
        "schemaVersion": "1.0.0",
        "missionId": DEMO_MISSION_ID,
        "rawRequest": "Desktop M0 read-only demonstration mission.",
        "normalizedRequest": "desktop m0 read-only demonstration mission",
        "objectives": [
            {"objectiveId": "obj-1", "statement": "Demonstrate a read-only vertical slice.", "priority": 1}
        ],
        "constraints": [
            {"kind": "resource_boundary", "constraintId": "con-1", "origin": "explicit_user",
             "scope": {"kind": "filesystem", "rootPath": DEMO_WORKTREE, "recursive": True}}
        ],
        "successCriteria": [
            {"criterionId": "sc-1", "statement": "Read-only proof completed and verified.", "requiresVerification": True}
        ],
        "terminationCriteria": [
            {"criterionId": "tc-1", "statement": "Invariant violation terminates the mission.", "terminalState": "failed"}
        ],
        "unresolvedAmbiguities": [],
        "taskGraphId": None,
        "createdAt": "2026-08-03T00:00:00Z",
    }
    svc.create_mission(mission_spec, _meta("mission", "human", "captain", "create_mission",
                                          {"missionId": DEMO_MISSION_ID}))

    policy = {
        "schemaVersion": "1.0.0", "policyDecisionId": "pd-desktop-m0",
        "policyBundleDigest": contracts.digest({"policyBundle": "desktop-m0", "version": 1}),
        "effect": "allow_with_conditions", "subject": {"actorId": "exec-1", "kind": "execution_plane"},
        "missionId": DEMO_MISSION_ID, "taskId": DEMO_TASK_ID,
        "requestedOperations": ["repository.read", "filesystem.read", "artifact.create", "analysis.execute"],
        "requestedScope": {"kind": "filesystem", "rootPath": DEMO_WORKTREE, "recursive": True},
        "conditions": [{"kind": "isolated_worktree", "worktreeRoot": DEMO_WORKTREE}],
        "rationale": "Scoped read-only demo.",
        "decidedBy": {"actorId": "gk-1", "kind": "governance_kernel"}, "decidedAt": "2026-08-03T00:01:00Z",
    }
    svc.evaluate_policy(policy, _meta("policy", "governance_kernel", "gk-1", "evaluate_policy",
                                     {"policyDecisionId": "pd-desktop-m0"}))

    grant = {
        "schemaVersion": "1.0.0", "grantId": DEMO_GRANT_ID,
        "subject": {"actorId": "exec-1", "kind": "execution_plane"},
        "capabilityId": "cap.fs.read", "operations": ["repository.read", "filesystem.read", "artifact.create", "analysis.execute"],
        "scope": {"kind": "filesystem", "rootPath": DEMO_WORKTREE, "recursive": True},
        "policyDecisionId": "pd-desktop-m0",
        "policyBundleDigest": contracts.digest({"policyBundle": "desktop-m0", "version": 1}),
        "conditions": [{"kind": "isolated_worktree", "worktreeRoot": DEMO_WORKTREE}],
        "maxUses": 1, "validFrom": "2026-08-03T00:02:00Z", "validUntil": "2030-01-01T00:00:00Z",
        "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"}, "issuedAt": "2026-08-03T00:02:00Z",
    }
    svc.issue_grant(grant, _meta("grant", "governance_kernel", "gk-1", "issue_grant",
                                {"grantId": DEMO_GRANT_ID}))

    lease = {
        "schemaVersion": "1.0.0", "leaseId": DEMO_LEASE_ID, "grantId": DEMO_GRANT_ID,
        "missionId": DEMO_MISSION_ID, "taskId": DEMO_TASK_ID, "executionContextId": "ec-desktop-m0",
        "operations": ["repository.read", "filesystem.read", "artifact.create", "analysis.execute"],
        "scope": {"kind": "filesystem", "rootPath": DEMO_WORKTREE, "recursive": True},
        "maxUses": 1, "validFrom": "2026-08-03T00:03:00Z", "validUntil": "2030-01-01T00:00:00Z",
        "activatedAt": "2026-08-03T00:03:00Z",
    }
    svc.activate_lease(lease, _meta("lease", "governance_kernel", "gk-1", "activate_lease",
                                    {"leaseId": DEMO_LEASE_ID}))

    # The proven M0-B dispatch path: the lease used for the boundary check
    # carries `allowedPaths` (required by verify_lease) but is NOT re-validated
    # against the CapabilityLease contract there. This mirrors the e2e proof.
    dispatch_lease = dict(lease)
    dispatch_lease["scope"] = {**lease["scope"], "allowedPaths": [DEMO_WORKTREE]}

    task = {
        "taskId": DEMO_TASK_ID, "missionId": DEMO_MISSION_ID,
        "title": "Read-only inspection of the demo worktree", "state": "pending",
        "consequential": False,
        "capabilityRequirements": [
            {"requirementId": "req-1", "capabilityId": "cap.fs.read", "operations": ["fs.read"],
             "scope": {"kind": "filesystem", "rootPath": DEMO_WORKTREE, "recursive": True}}
        ],
        "assignedDriverId": None, "attempt": 0, "maxAttempts": 1, "recoveryState": "none",
    }
    svc.create_task(task, _meta("task", "cognitive_plane", "cog-1", "create_task",
                                {"taskId": DEMO_TASK_ID}))
    svc.transition_task(DEMO_TASK_ID, "ready", "deps satisfied",
                        _meta("ready", "execution_plane", "exec-1", "transition_task",
                              {"taskId": DEMO_TASK_ID, "to": "ready"}))
    svc.transition_task(DEMO_TASK_ID, "assigned", "assigned to execution context",
                        _meta("assigned", "execution_plane", "exec-1", "transition_task",
                              {"taskId": DEMO_TASK_ID, "to": "assigned"}))
    svc.transition_task(DEMO_TASK_ID, "running", "lease validated",
                        _meta("running", "execution_plane", "exec-1", "transition_task",
                              {"taskId": DEMO_TASK_ID, "to": "running"}))

    # Real reference-driver read-only proof -> DriverRun + observation + artifact.
    worktree = Path(DEMO_WORKTREE)
    worktree.mkdir(parents=True, exist_ok=True)
    (worktree / "README.md").write_text("# desktop M0 demo worktree\n")
    staging = worktree.parent / (worktree.name + "-staging")
    staging.mkdir(parents=True, exist_ok=True)

    host = runtime.openharness_host(
        target_repo=str(worktree), staging_root=str(staging), enforce_memory=False
    )
    ctx = host.build_context(
        {"leaseId": lease["leaseId"], "operations": lease["operations"],
         "scope": lease["scope"], "validFrom": lease["validFrom"], "validUntil": lease["validUntil"]},
        ["terminal"], {"maxSeconds": 60, "maxArtifacts": 1, "maxObservations": 10},
        [{"artifactPath": str(staging / "analysis.md"), "artifactKind": "report"}],
        {"onUnexpectedWrite": "fail"},
    )
    wo = {
        "schemaVersion": "1.0.0", "driverRunId": DEMO_DRIVER_RUN_ID, "driverId": "openharness",
        "missionId": DEMO_MISSION_ID, "taskId": DEMO_TASK_ID, "workOrderVersion": 1,
        "contextSlice": ctx, "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"],
    }
    svc.create_driver_run(
        {"schemaVersion": "1.0.0", "driverRunId": DEMO_DRIVER_RUN_ID, "driverId": "openharness",
         "missionId": DEMO_MISSION_ID, "taskId": DEMO_TASK_ID, "workOrderVersion": 1,
         "externalRunId": None, "state": "created", "reconciliationStatus": "not_required",
         "createdAt": "2026-08-03T00:04:00Z"},
        _meta("driverrun", "execution_plane", "exec-1", "create_driver_run",
              {"driverRunId": DEMO_DRIVER_RUN_ID}),
    )
    svc.transition_driver_run(DEMO_DRIVER_RUN_ID, "submitted",
                              _meta("drsubmit", "execution_plane", "exec-1", "transition_driver_run",
                                    {"driverRunId": DEMO_DRIVER_RUN_ID}))
    svc.transition_driver_run(DEMO_DRIVER_RUN_ID, "running",
                              _meta("drrun", "execution_plane", "exec-1", "transition_driver_run",
                                    {"driverRunId": DEMO_DRIVER_RUN_ID}))
    out = host.dispatch(wo, ctx, {"state": "running"}, now="2026-08-03T00:04:00Z", lease=dispatch_lease)
    svc.transition_driver_run(DEMO_DRIVER_RUN_ID, "completed",
                              _meta("drcomplete", "execution_plane", "exec-1", "transition_driver_run",
                                    {"driverRunId": DEMO_DRIVER_RUN_ID}))

    # Verification (CAPT-authored) + ClaimGuard bounded claim.
    artifact_path = out["artifactCandidate"]["artifactPath"]
    artifact_digest = out["artifactCandidate"]["artifactDigest"]
    before = tree_digest(str(worktree))
    vr = build_verification_result(str(worktree), before, artifact_path, artifact_digest, "openharness")
    claim_statement = "Repository inspected in read-only mode."
    accepted = guard_claim(claim_statement)
    svc.propose_claim(
        {"schemaVersion": "1.0.0", "claimId": DEMO_CLAIM_ID, "missionId": DEMO_MISSION_ID,
         "taskId": DEMO_TASK_ID, "kind": "completion", "statement": accepted,
         "evidenceIds": [], "promotionState": "proposed",
         "proposedBy": {"actorId": "cog-1", "kind": "cognitive_plane"},
         "proposedAt": "2026-08-03T00:05:00Z", "sourceProposalId": None},
        _meta("claim", "cognitive_plane", "cog-1", "propose_claim", {"claimId": DEMO_CLAIM_ID}),
    )

    create_checkpoint(store, "cp-desktop-m0", "2026-08-03T00:05:00Z",
                      contracts.digest({"policyBundle": "desktop-m0", "version": 1}))
    return {"seeded": True, "driverRunId": DEMO_DRIVER_RUN_ID, "verificationId": vr["verificationId"],
            "artifactPath": artifact_path, "artifactDigest": artifact_digest,
            "targetPath": str(worktree), "beforeDigest": before}


def _seed_memory_store(mem_store) -> None:
    """Seed the authoritative memory store with prior-mission context.

    These records are CAPT-owned memory used by the mandatory retrieval trigger
    when an operator creates a mission. They are real, attributable records with
    provenance/trust/consent — not anonymous text blobs.
    """
    from capt_runtime.memory import MemoryRecord

    mem_store.store(MemoryRecord(
        record_id="mem-prior-approval-denied-write-etc",
        memory_class="project",
        owner="capt",
        source="capt_runtime.aggregates.human_approval",
        provenance="mission:demo-m0/approval:demo-approval-1",
        trust="verified",
        verification_status="verified",
        sensitivity="project",
        consent="project",
        content="Prior approval for a write to /etc was DENIED; writes outside the "
                "staging root are never authorized. Approval scope is bounded to the "
                "originally requested resource.",
    ))
    mem_store.store(MemoryRecord(
        record_id="mem-operator-pref-concise",
        memory_class="user",
        owner="operator-knowurknot",
        source="operator_stated",
        provenance="operator:knowurknot",
        trust="unverified",
        verification_status="pending",
        sensitivity="user",
        consent="user",
        content="Operator preference: concise, direct reporting; no AI slop; working "
                "artifacts only; prove claims with live execution.",
    ))
    mem_store.store(MemoryRecord(
        record_id="mem-failed-approach-gitguardian-secret-scan",
        memory_class="episodic",
        owner="capt",
        source="capt_runtime.verification",
        provenance="mission:release-security/evidence:release-security-1",
        trust="verified",
        verification_status="verified",
        sensitivity="project",
        consent="project",
        content="A prior release-security CI failure was a false-positive GitGuardian "
                "secret scan on bare git SHAs. Fix: prefix sha1:/sha256:; rewrite "
                "history; drop generated artifacts. Do not block merge on unrelated "
                "private-dep auth failures.",
        conflict_state=None,
    ))


# --------------------------------------------------------------------------
# Read-only IPC query handlers (authoritative state only)
# --------------------------------------------------------------------------

class RuntimeQueryService:
    def __init__(self, store: EventStore, demo: Optional[Dict[str, Any]] = None, memory_engine: Any = None, lab_registry: Any = None) -> None:
        self.store = store
        self.demo = demo or {}
        self.memory_engine = memory_engine
        self.lab_registry = lab_registry

    def identity(self) -> Dict[str, Any]:
        return {
            "runtimeVersion": RUNTIME_VERSION,
            "contractSchemaVersion": CONTRACT_SCHEMA_VERSION,
            "ledgerPath": self.store.path,
            "headSequence": self.store.head_sequence(),
            "ledgerChainDigest": self.store.head_chain(),
            "integrity": self._verify_chain(),
        }

    def _verify_chain(self) -> str:
        try:
            self.store.verify_chain()
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return "broken:" + str(exc)[:120]

    def list_aggregates(self) -> List[Dict[str, Any]]:
        return [
            {"streamId": s, "kind": k, "version": v}
            for (s, k, v) in self.store.all_aggregates()
        ]

    def get_state(self, stream_id: str) -> Optional[Dict[str, Any]]:
        return self.store.load_state(stream_id)

    def get_stream_events(self, stream_id: str) -> List[Dict[str, Any]]:
        return self.store.read_stream(stream_id)

    def event_timeline(self, after: int = 0, limit: int = 250) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 1000))
        return self.store.read_recent_events(after_sequence=after, limit=bounded)

    def _claim_id_for_statement(self, statement: str) -> Optional[str]:
        """Find the most recent claim with this exact statement, if any."""
        matches = []
        for stream_id, kind, version in self.store.all_aggregates():
            if kind != "claim":
                continue
            state = self.store.load_state(stream_id)
            if state and state.get("statement") == statement:
                matches.append((version, state.get("claimId")))
        return max(matches)[1] if matches else None

    def claimguard_disposition(
        self, statement: str, claim_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Project a committed ClaimGuard decision before advisory recomputation."""
        selected = claim_id or self._claim_id_for_statement(statement)
        if selected:
            state = self.store.load_state("claim-" + selected)
            if state and state.get("guardVerdict"):
                for env in reversed(self.store.read_stream("claim-" + selected)):
                    payload = env.get("payload", {})
                    if payload.get("eventType") == "ClaimGuardDecided":
                        decision = payload["decision"]
                        return {
                            "statement": state["statement"],
                            "verdict": "accepted" if decision["verdict"] == "accept" else "rejected",
                            "claimId": selected,
                            "decisionId": decision["decisionId"],
                            "committed": True,
                            "advisory": False,
                        }
        try:
            accepted = guard_claim(statement)
            return {"statement": accepted, "verdict": "accepted", "committed": False, "advisory": True}
        except Exception as exc:  # noqa: BLE001
            return {"statement": statement, "verdict": "rejected", "reason": str(exc)[:160],
                    "committed": False, "advisory": True}

    def verification(self, claim_id: Optional[str] = None) -> Dict[str, Any]:
        """Recompute the CAPT-authored verification result for the demo artifact.

        This is a read-only computation over authoritative state (the artifact
        produced by the reference-driver proof). It is NOT a desktop decision.

        The returned dict is the contract-conforming VerificationResult with a
        '_view' sibling carrying trust/checks/observedBy for the GUI layer.
        The desktop view flattens _view into the top-level response so consumers
        that expect vr['trust']/vr['checks'] keep working.
        """
        if claim_id:
            for env in reversed(self.store.read_stream("claim-" + claim_id)):
                payload = env.get("payload", {})
                if payload.get("eventType") == "ClaimVerified":
                    return {**payload["verification"], "committed": True, "advisory": False}
        if not self.demo.get("artifactPath"):
            return {"status": {"kind": "not_tested"}, "trust": "capt_authoritative"}
        try:
            vr = build_verification_result(
                self.demo["targetPath"],
                self.demo["beforeDigest"],
                self.demo["artifactPath"],
                self.demo["artifactDigest"],
                "openharness",
            )
            # Flatten _view annotations into the top-level for GUI consumers.
            view = vr.pop("_view", {})
            vr.update(view)
            vr.update({"committed": False, "advisory": True})
            return vr
        except Exception as exc:  # noqa: BLE001
            return {"status": {"kind": "failed"}, "error": str(exc)[:200],
                    "trust": "capt_authoritative", "committed": False, "advisory": True}

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        op = request.get("op")
        try:
            if op == "identity":
                return {"ok": True, "result": self.identity()}
            if op == "capabilities":
                return {"ok": True, "result": {
                    "schemaVersion": CONTRACT_SCHEMA_VERSION,
                    "queryOperations": ["identity", "capabilities", "list_aggregates", "get_state", "get_stream_events", "event_timeline", "claimguard", "verification", "get_memory_policy", "get_memory_state"] + (["lab_engines"] if self.lab_registry is not None else []),
                    "commandOperations": ["create_mission", "request_model_prompt_approval", "submit_approval_decision", "cancel_task", "cancel_driver_run", "update_memory_trigger_policy", "run_fixed_openharness_inspection", "run_approved_hermes_inspection", "checkpoint_runtime", "shutdown", "resume_runtime", "run_tool"] + (["run_lab_engine_advisory"] if self.lab_registry is not None else []),
                    "runtimeComponents": {"composition": True, "eventStore": True, "runtimeService": True, "driverRegistry": True, "driverHost": True, "memory": self.memory_engine is not None, "checkpointReplay": True, "khsb": True, "ctp": True, "labEngines": self.lab_registry is not None, "toolRegistry": True, "toolBroker": True},
                    "lifecycleOperations": {"checkpoint": True, "shutdown": True, "resume": True},
                }}
            if op == "list_aggregates":
                return {"ok": True, "result": self.list_aggregates()}
            if op == "get_state":
                st = self.get_state(request["streamId"])
                if st is None:
                    return {"ok": False, "error": "unknown stream %s" % request["streamId"]}
                return {"ok": True, "result": st}
            if op == "get_stream_events":
                return {"ok": True, "result": self.get_stream_events(request["streamId"])}
            if op == "event_timeline":
                return {"ok": True, "result": self.event_timeline(
                    int(request.get("after", 0)), int(request.get("limit", 250))
                )}
            if op == "claimguard":
                return {"ok": True, "result": self.claimguard_disposition(
                    request["statement"], request.get("claimId")
                )}
            if op == "verification":
                return {"ok": True, "result": self.verification(request.get("claimId"))}
            if op == "lab_engines":
                if self.lab_registry is None:
                    return {"ok": False, "error": "Lab engine registry not active"}
                return {"ok": True, "result": self.lab_registry.describe()}
            if op == "get_memory_policy":
                if self.memory_engine is None:
                    return {"ok": False, "error": "memory engine not active"}
                p = self.memory_engine.policy
                from capt_runtime.memory.policy import TRIGGER_INTERVAL_TOKENS
                return {"ok": True, "result": {
                    "policyVersion": p.policy_version,
                    "policyDigest": p.policy_digest,
                    "triggerIntervalTokens": TRIGGER_INTERVAL_TOKENS,
                    "retrievalTriggerSteps": p.retrieval_trigger_steps,
                    "compressionTriggerSteps": p.compression_trigger_steps,
                    "checkpointTriggerSteps": p.checkpoint_trigger_steps,
                    "consolidationTriggerSteps": p.consolidation_trigger_steps,
                    "hardStopTriggerSteps": p.hard_stop_trigger_steps,
                    "modelSafeLimitSteps": p.model_safe_limit_steps,
                    "source": p.source,
                    "retrievalTokens": p.retrieval_tokens(),
                    "compressionTokens": p.compression_tokens(),
                    "checkpointTokens": p.checkpoint_tokens(),
                    "consolidationTokens": p.consolidation_tokens(),
                    "hardStopTokens": p.hard_stop_tokens(),
                    "modelSafeLimitTokens": p.model_safe_limit_tokens(),
                }}
            if op == "get_memory_state":
                if self.memory_engine is None:
                    return {"ok": False, "error": "memory engine not active"}
                mission_id = request.get("missionId", "")
                pack = self.memory_engine.last_context_pack(mission_id)
                return {"ok": True, "result": {
                    "memoryPathActive": True,
                    "lastContextPack": pack,
                    "triggerLog": self.memory_engine.trigger_log(mission_id),
                    "policyVersions": self.memory_engine.persisted_policy_versions(),
                }}
            return {"ok": False, "error": "unknown op %r" % op}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)[:300]}


# --------------------------------------------------------------------------
# Authenticated Unix-domain-socket server
# --------------------------------------------------------------------------

def _recv_json(sock: socket.socket) -> Optional[Dict[str, Any]]:
    header = sock.recv(4)
    if not header:
        return None
    length = int.from_bytes(header, "big")
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(length - len(buf))
        if not chunk:
            return None
        buf += chunk
    return json.loads(buf.decode("utf-8"))


def _send_json(sock: socket.socket, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload).encode("utf-8")
    sock.sendall(len(data).to_bytes(4, "big") + data)


def serve(ledger_path: str, sock_path: Path, token_file: str, seed: bool) -> None:
    sock_path = Path(sock_path)
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    if sock_path.exists():
        if not sock_path.is_socket():
            raise RuntimeError("CAPT runtime socket path is not a socket: %s" % sock_path)
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.settimeout(0.2)
            probe.connect(str(sock_path))
        except ConnectionRefusedError:
            sock_path.unlink()
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError("CAPT runtime service already active at %s" % sock_path)
        finally:
            probe.close()

    runtime = create_runtime(str(ledger_path))
    _reconcile_stranded_driver_runs(runtime, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    runtime.reconcile_stranded_tools()
    store = runtime.store
    svc = runtime.service
    demo = None
    if seed:
        _seed_memory_store(runtime.memory_store)
        demo = seed_demo_mission(runtime)

    # Mandatory CAPT memory trigger subsystem (M1-memory, ADR-DT-M1-MEM-001).
    # CAPT owns the memory path; the desktop and drivers are projection/
    # execution surfaces only. The engine is wired into every connection's
    # command service and into DriverHost dispatch gating.
    memory_engine = runtime.memory_engine

    from capt_lab.registry import build_default_registry
    from capt_lab.runtime import run_lab_advisory
    lab_registry = build_default_registry()
    query = RuntimeQueryService(store, demo, memory_engine, lab_registry=lab_registry)

    token = secrets.token_hex(32)
    tf = Path(token_file)
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text(token)
    os.chmod(tf, 0o600)

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(8)
    srv.settimeout(0.2)
    shutdown_requested = threading.Event()
    fixed_work_receipts: Dict[str, Dict[str, Any]] = {}
    checkpoint_receipts: Dict[str, Dict[str, Any]] = {}
    print("CAPT_RUNTIME_SERVICE_READY sock=%s ledger=%s pid=%d" % (sock_path, ledger_path, os.getpid()))

    def handle_conn(conn: socket.socket) -> None:
        try:
            # Authenticate: first frame must be the session token.
            auth = _recv_json(conn)
            if not auth or auth.get("token") != token:
                _send_json(conn, {"ok": False, "error": "unauthenticated"})
                return
            # Bind operator identity to this authenticated connection.
            # Single-user macOS desktop: the operator is the local user. The
            # session token authenticates the connection; the operator/session
            # binding prevents the desktop from spoofing another operator or
            # reusing a stale session's authority (Phase 3).
            operator_id = "operator-" + (getpass.getuser() or "local")
            session_id = "sess-" + secrets.token_hex(8)
            cmd_svc = runtime.command_service(operator_id, session_id)
            # Fixed v0.5 OpenHarness inspection: service-owned runner uses the
            # already-created canonical RuntimeComposition; no duplicate runtime.
            def _fixed_openharness(command: Dict[str, Any]):
                key = command["idempotencyKey"]
                prior = fixed_work_receipts.get(key)
                if prior is not None:
                    return {**prior, "_idempotent": True}
                result = seed_demo_mission(runtime)
                fixed_work_receipts[key] = result
                return result
            cmd_svc.fixed_openharness_runner = _fixed_openharness
            lab_staging_root = Path(ledger_path).parent / "lab-staging"
            cmd_svc.lab_runner = lambda command: run_lab_advisory(
                store, svc, lab_registry, lab_staging_root, command
            )
            # Governed model operator: the CLI objective becomes authoritative
            # mission/task state; the frozen work order carries only the
            # missionId/taskId references; HermesDriver derives its prompt from
            # the resolved authoritative task (TaskResolver) inside CAPT.
            def _prepare_approved_hermes(command: Dict[str, Any]) -> PreparedApprovedModelExecution:
                """Validate and freeze every deterministic dispatch input."""
                payload = command.get("payload", {})
                objective = payload.get("objective")
                target_root = payload.get("targetRoot")
                if not objective or not target_root:
                    raise ValueError("MODEL_TASK_OBJECTIVE_OR_TARGET_MISSING")
                command_id = command["commandId"]
                now = command.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                mission_id = payload.get("missionId") or ("m-model-" + command_id)
                task_id = payload.get("taskId") or (mission_id + "-task-1")
                run_id = payload.get("driverRunId") or ("dr-model-" + command_id)
                from capt_runtime.model_agent_tools import configured_agent_tool_mode
                agent_mode = configured_agent_tool_mode(str(run_id))
                grant_id = payload.get("grantId") or ("g-model-" + command_id)
                lease_id = payload.get("leaseId") or ("l-model-" + command_id)
                claim_id = payload.get("claimId") or ("cl-model-" + command_id)
                policy_id = payload.get("policyDecisionId") or ("pd-model-" + command_id)
                executable = payload.get("executable") or None
                provider_id = payload.get("provider")
                provider_model = payload.get("model")
                if agent_mode["enabled"] and (not provider_id or not provider_model):
                    raise ValueError("MODEL_AGENT_TOOLBRIDGE_REQUIRES_PROVIDER_MODEL")
                provider = None
                provider_key = ""
                if provider_id:
                    from capt_ui.operator.providers import ProviderManager
                    from capt_ui.operator.secrets import resolve
                    provider = ProviderManager(Path(ledger_path).parent / "ui").get(str(provider_id))
                    if provider is None or not provider_model:
                        raise ValueError("PROVIDER_OR_MODEL_UNAVAILABLE")
                    provider_key = resolve(provider.id, provider.key_ref)
                    if credential_required(provider.id, provider.kind, provider.base_url) and not provider_key:
                        raise ValueError("PROVIDER_CREDENTIAL_UNAVAILABLE")
                requested_context_budget = int(payload.get("requestedContextBudget", 32_000))
                effective_budget = effective_context_budget(
                    requested_context_budget, provider.context_limit if provider is not None else 0)
                response_mode = str(payload.get("responseMode", "SPOCK"))
                enhancement_engine = str(payload.get("promptEnhancement", "OFF"))
                human_verification_required = bool(payload.get("humanVerificationRequired", True))
                # Explicit authored-skill selection outranks contextual selection.
                # When no explicit selection is present and a verified managed pack
                # exists under the state root, CAPT auto-selects applicable skills
                # before approval and freezes the selection through dispatch.
                skill_context, skill_names = prepare_runtime_skill_context(
                    payload, state_root=Path(ledger_path).parent
                )
                # Governed continuation context selection (PR #47 context gate).
                # Prior authoritative mission evidence is selected HERE, from the
                # ledger, before approval/admission. No manual injection, no
                # surviving in-memory object carries it across the restart.
                from capt_runtime.continuation_context import select_continuation_context
                ledger_dir = str(Path(ledger_path).parent)
                continuation = select_continuation_context(
                    store, str(mission_id), str(task_id),
                    exclude_run_id=str(run_id), ledger_dir=ledger_dir,
                )
                context_pack_digest = continuation["contextPackDigest"]
                prompt_assembly = build_prompt_assembly(
                    human_prompt=str(objective), response_mode=response_mode,
                    enhancement_engine=enhancement_engine,
                    context_pack_digest=context_pack_digest,
                    tool_schema_digest=contracts.digest({"operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"]}),
                    continuation_context=continuation["records"],
                    authored_skill_context=skill_context,
                )
                # Runtime authority binds human approval to the exact
                # model-visible assembly. Client booleans are provenance only;
                # no client can use OFF/no-transform as a governance bypass.
                approval_request_id = payload.get("approvalRequestId")
                if not approval_request_id:
                    raise AuthorityViolation("MODEL_PROMPT_APPROVAL_RECEIPT_REQUIRED")
                bound_assembly = build_bound_model_operator_approval(
                    human_prompt=str(objective), response_mode=response_mode,
                    enhancement_engine=enhancement_engine, mission_id=str(mission_id),
                    task_id=str(task_id), driver_run_id=str(run_id), target_root=str(target_root),
                    provider=str(provider_id or ""), model=str(provider_model or ""),
                    requested_context_budget=requested_context_budget,
                    human_verification_required=human_verification_required,
                    executable=str(executable or ""),
                    staging_root=staging_root_for_ledger(store.path, str(run_id)),
                    context_pack_digest=context_pack_digest,
                    continuation_context=continuation["records"],
                    authored_skill_context=skill_context,
                    agent_tool_profile=str(agent_mode["profile"]),
                    agent_tool_operations=list(agent_mode["operations"]),
                    agent_tool_grant_id=str(agent_mode["grantId"]),
                    agent_tool_lease_id=str(agent_mode["leaseId"]),
                )
                # This read-only check catches a mismatched approval before the
                # command service consumes the one-use receipt.
                svc.require_approved_prompt_assembly(
                    str(approval_request_id), bound_assembly["promptAssemblyDigest"],
                    "ModelOperatorInspection")
                return PreparedApprovedModelExecution(
                    command_id=str(command_id), idempotency_key=str(command["idempotencyKey"]),
                    correlation_id=str(command.get("correlationId", "corr-model")), issued_at=str(now),
                    approval_request_id=str(approval_request_id),
                    prompt_assembly_digest=bound_assembly["promptAssemblyDigest"],
                    dispatch_prompt_digest=bound_assembly["dispatchPromptDigest"],
                    mission_id=str(mission_id), task_id=str(task_id), driver_run_id=str(run_id),
                    resource=str(target_root), objective=str(objective),
                    provider_id=str(provider_id) if provider_id else None,
                    provider_model=str(provider_model) if provider_model else None,
                    executable=str(executable) if executable else None,
                    data=freeze({
                        "grantId": str(grant_id), "leaseId": str(lease_id),
                        "claimId": str(claim_id), "policyDecisionId": str(policy_id),
                        "requestedContextBudget": requested_context_budget,
                        "effectiveBudget": effective_budget,
                        "responseMode": response_mode,
                        "enhancementEngine": enhancement_engine,
                        "humanVerificationRequired": human_verification_required,
                        "promptAssembly": prompt_assembly,
                        "dispatchPrompt": bound_assembly["dispatchPrompt"],
                        "contextPackDigest": context_pack_digest,
                        "continuationContext": continuation["records"],
                        "authoredSkillContext": skill_context,
                        "skillNames": skill_names,
                        "agentToolProfile": str(agent_mode["profile"]),
                        "agentToolOperations": list(agent_mode["operations"]),
                        "agentToolGrantId": str(agent_mode["grantId"]),
                        "agentToolLeaseId": str(agent_mode["leaseId"]),
                    }),
                    context_pack_digest=context_pack_digest,
                )

            def _execute_approved_hermes(prepared: PreparedApprovedModelExecution):
                # Dispatch consumes only the immutable prepared object. It never
                # reconstructs fields from the original raw command.
                key = prepared.idempotency_key
                command_fingerprint = commands.fingerprint(
                    "admit_approved_model_execution",
                    {"preparedExecutionDigest": prepared.prepared_execution_digest})
                objective = prepared.objective
                target_root = prepared.resource
                command_id, now = prepared.command_id, prepared.issued_at
                correlation_id = prepared.correlation_id
                mission_id, task_id, run_id = prepared.mission_id, prepared.task_id, prepared.driver_run_id
                grant_id, lease_id = prepared.data["grantId"], prepared.data["leaseId"]
                claim_id, policy_id = prepared.data["claimId"], prepared.data["policyDecisionId"]
                provider_id, provider_model = prepared.provider_id, prepared.provider_model
                executable = prepared.executable
                provider = None
                provider_key = ""
                if provider_id:
                    from capt_ui.operator.providers import ProviderManager
                    from capt_ui.operator.secrets import resolve
                    provider = ProviderManager(Path(ledger_path).parent / "ui").get(provider_id)
                    if provider is None or not provider_model:
                        raise ValueError("PROVIDER_OR_MODEL_UNAVAILABLE")
                    provider_key = resolve(provider.id, provider.key_ref)
                    if credential_required(provider.id, provider.kind, provider.base_url) and not provider_key:
                        raise ValueError("PROVIDER_CREDENTIAL_UNAVAILABLE")
                requested_context_budget = prepared.data["requestedContextBudget"]
                effective_budget = prepared.data["effectiveBudget"]
                response_mode = prepared.data["responseMode"]
                enhancement_engine = prepared.data["enhancementEngine"]
                human_verification_required = prepared.data["humanVerificationRequired"]
                prompt_assembly = prepared.data["promptAssembly"]
                model_visible_objective = prompt_assembly["modelVisiblePrompt"]
                dispatch_prompt = prepared.data["dispatchPrompt"]
                skill_context = (
                    json.loads(json.dumps(prepared.data["authoredSkillContext"]))
                    if prepared.data.get("authoredSkillContext") else None
                )
                skill_names = list(prepared.data.get("skillNames") or ())
                agent_tool_profile = str(prepared.data.get("agentToolProfile") or "")
                agent_tool_operations = list(prepared.data.get("agentToolOperations") or ())
                agent_tool_grant_id = str(prepared.data.get("agentToolGrantId") or "")
                agent_tool_lease_id = str(prepared.data.get("agentToolLeaseId") or "")
                agent_enabled = bool(agent_tool_profile)
                if agent_enabled and (provider is None or not provider_model):
                    raise ValueError("MODEL_AGENT_TOOLBRIDGE_REQUIRES_PROVIDER_MODEL")
                task_title = str(objective).strip()[:512] or "Model operator task"
                cognitive_provenance = build_cognitive_provenance(
                    assembly=prompt_assembly, provider_id=provider.id if provider is not None else "hermes",
                    model=str(provider_model or "hermes"), requested_context_budget=requested_context_budget,
                    effective_context_budget_value=effective_budget,
                    human_verification_required=human_verification_required,
                    correlation={"missionId": mission_id, "taskId": task_id, "driverRunId": run_id,
                                 "policyDecisionId": policy_id, "grantId": grant_id, "leaseId": lease_id},
                )
                def recovery_meta(step: str) -> Dict[str, Any]:
                    return commands.command(
                        command_id=command_id + ":" + step,
                        idempotency_key=key + ":" + step,
                        operation_fingerprint=commands.fingerprint(step, {"driverRunId": run_id}),
                        correlation_id=correlation_id,
                        actor_id="exec-1", actor_kind="execution_plane",
                        issued_at=now, replay_policy="never",
                    )
                # Restart/replay safety: persisted DriverRun is CAPT authority.
                # `running` is not proof that dispatch did or did not cross the
                # boundary. It is converted durably to lost/reconciliation-required,
                # its open reservation is consumed indeterminately, and its task is
                # suspended for the existing governed cancellation/reconciliation
                # command path. No branch re-dispatches an extant run.
                prior_run = store.load_state("driverrun-" + run_id)
                # An immediately-created ``created`` run is this invocation's
                # durable admission intent. Any later state is restart evidence
                # and must follow recovery, never re-dispatch.
                if prior_run is not None and prior_run.get("state") != "created":
                    capability = store.load_state("capability-" + grant_id)
                    reservation_id = "res-" + command_id
                    open_reservation = bool(capability and reservation_id in [
                        r["reservationId"] for r in capability.get("reservations", [])
                        if r["state"] == "open"
                    ])
                    if open_reservation:
                        consumption = {
                            "schemaVersion": "1.0.0", "consumptionId": "con-" + command_id,
                            "reservationId": reservation_id, "leaseId": lease_id,
                            "outcome": "indeterminate", "sideEffectIdentity": run_id,
                            "finalizedAt": now,
                        }
                        svc.finalize_use(grant_id, consumption, recovery_meta("recover-finalize"))
                    prior_state = prior_run.get("state")
                    task_state = store.load_state("task-" + task_id)
                    if prior_state in ("created", "submitted"):
                        # Dispatch is provably not yet entered in this runner's
                        # ordering. Preserve authority: no consumption is invented.
                        svc.transition_driver_run(run_id, "failed", recovery_meta("recover-no-dispatch"))
                        if task_state and task_state.get("state") in ("assigned", "running"):
                            svc.transition_task(task_id, "failed", "dispatch not entered before restart", recovery_meta("recover-task-failed"))
                        recovery = "persisted_pre_dispatch_run_failed"
                    elif prior_state in ("running", "suspended"):
                        if prior_state == "running":
                            svc.transition_driver_run(run_id, "lost", recovery_meta("recover-lost"))
                        if task_state and task_state.get("state") == "running":
                            svc.transition_task(task_id, "suspended", "external boundary indeterminate; governed reconciliation required", recovery_meta("recover-suspend"))
                        recovery = "persisted_indeterminate_requires_reconciliation"
                    else:
                        # Completed/terminal runs are immutable evidence. Only an
                        # open reservation may be conservatively reconciled above.
                        if prior_state == "completed" and task_state and task_state.get("state") == "running":
                            svc.transition_task(task_id, "suspended", "completed external work requires governed reconciliation", recovery_meta("recover-suspend"))
                        recovery = "persisted_driver_run_not_repeated"
                    receipt = {"missionId": mission_id, "taskId": task_id, "driverRunId": run_id,
                               "claimId": claim_id, "recovery": recovery}
                    store.complete_claimed_command(key, command_fingerprint, receipt)
                    return receipt
                # 1. Authoritative mission/task state (objective persisted in
                # the Task aggregate by RuntimeService planning).
                intent = {
                    "schemaVersion": "1.0.0",
                    "missionId": mission_id,
                    "objective": task_title,
                    "scope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
                    "requiresApproval": False,
                    "constraints": [{"kind": "resource_boundary", "constraintId": "con-model-1",
                                     "origin": "explicit_user",
                                     "scope": {"kind": "filesystem", "rootPath": target_root, "recursive": True}}],
                    "successCriteria": [{"criterionId": "sc-model-1",
                                         "statement": "Model task completed with evidence-backed observations.",
                                         "requiresVerification": True}],
                    "terminationCriteria": [{"criterionId": "tc-model-1",
                                             "statement": "Invariant violation terminates the mission.",
                                             "terminalState": "failed"}],
                    "requestedCapability": "cap.agent.tools" if agent_enabled else "cap.fs.read",
                    "resource": target_root,
                    "operation": "ModelOperatorInspection",
                    "riskClassification": "medium" if agent_enabled else "low",
                    "taskId": task_id,
                }
                existing_mission = store.load_state("mission-" + str(mission_id))
                planning_op = (
                    "plan_task_for_existing_mission" if existing_mission is not None
                    else "create_mission"
                )
                meta = commands.command(
                    command_id=command_id + ":mission",
                    idempotency_key=key + ":mission",
                    operation_fingerprint=commands.fingerprint(planning_op, intent),
                    correlation_id=correlation_id,
                    actor_id=cmd_svc.operator_id,
                    actor_kind="human",
                    issued_at=now,
                    replay_policy="never",
                )
                if existing_mission is None:
                    svc.create_mission_with_approval(intent, meta)
                else:
                    svc.plan_task_for_existing_mission(intent, meta)
                exec_meta = lambda step: commands.command(
                    command_id=command_id + ":" + step,
                    idempotency_key=key + ":" + step,
                    operation_fingerprint=commands.fingerprint("transition_task", {"taskId": task_id, "to": step}),
                    correlation_id=correlation_id,
                    actor_id="exec-1", actor_kind="execution_plane",
                    issued_at=now, replay_policy="never",
                )
                svc.transition_task(task_id, "ready", "authoritative task approved", exec_meta("ready"))
                svc.transition_task(task_id, "assigned", "assigned to hermes execution context", exec_meta("assigned"))
                svc.transition_task(task_id, "running", "model operator dispatch authorized", exec_meta("running"))
                # 2. Authoritative policy/grant/lease for the external call.
                gk_meta = lambda step: commands.command(
                    command_id=command_id + ":" + step,
                    idempotency_key=key + ":" + step,
                    operation_fingerprint=commands.fingerprint(step, {"missionId": mission_id, "taskId": task_id}),
                    correlation_id=correlation_id,
                    actor_id="gk-1", actor_kind="governance_kernel",
                    issued_at=now, replay_policy="never",
                )
                policy = {
                    "schemaVersion": "1.0.0", "policyDecisionId": policy_id,
                    "policyBundleDigest": contracts.digest({"policyBundle": "model-operator", "version": 1}),
                    "effect": "allow_with_conditions",
                    "subject": {"actorId": "exec-1", "kind": "execution_plane"},
                    "missionId": mission_id, "taskId": task_id,
                    "requestedOperations": ["repository.read", "filesystem.read", "artifact.create", "analysis.execute"],
                    "requestedScope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
                    "conditions": [{"kind": "isolated_worktree", "worktreeRoot": target_root}],
                    "rationale": "Bounded read-only model operator task.",
                    "decidedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
                    "decidedAt": now,
                }
                svc.evaluate_policy(policy, gk_meta("evaluate_policy"))
                grant = {
                    "schemaVersion": "1.0.0", "grantId": grant_id,
                    "subject": {"actorId": "exec-1", "kind": "execution_plane"},
                    "capabilityId": "cap.fs.read",
                    "operations": ["repository.read", "filesystem.read", "artifact.create", "analysis.execute"],
                    "scope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
                    "policyDecisionId": policy_id,
                    "policyBundleDigest": contracts.digest({"policyBundle": "model-operator", "version": 1}),
                    "conditions": [{"kind": "isolated_worktree", "worktreeRoot": target_root}],
                    "maxUses": 1, "validFrom": now, "validUntil": "2030-01-01T00:00:00Z",
                    "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"}, "issuedAt": now,
                }
                svc.issue_grant(grant, gk_meta("issue_grant"))
                lease = {
                    "schemaVersion": "1.0.0", "leaseId": lease_id, "grantId": grant_id,
                    "missionId": mission_id, "taskId": task_id,
                    "executionContextId": "ec-model-" + command_id,
                    "operations": ["repository.read", "filesystem.read", "artifact.create", "analysis.execute"],
                    "scope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
                    "maxUses": 1, "validFrom": now, "validUntil": "2030-01-01T00:00:00Z",
                    "activatedAt": now,
                }
                svc.activate_lease(lease, gk_meta("activate_lease"))
                dispatch_lease = dict(lease)
                dispatch_lease["scope"] = {**lease["scope"], "allowedPaths": [target_root]}
                if agent_enabled:
                    tool_policy_id = "pd-agent-tools-" + run_id
                    tool_bundle_digest = contracts.digest({
                        "policyBundle": "model-agent-toolbroker", "version": 1,
                        "profile": agent_tool_profile,
                    })
                    tool_policy = {
                        "schemaVersion": "1.0.0", "policyDecisionId": tool_policy_id,
                        "policyBundleDigest": tool_bundle_digest,
                        "effect": "allow_with_conditions",
                        "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
                        "missionId": mission_id, "taskId": task_id,
                        "requestedOperations": agent_tool_operations,
                        "requestedScope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
                        "conditions": [{"kind": "isolated_worktree", "worktreeRoot": target_root}],
                        "rationale": "Approval-bound CAPT MCP coding-agent tools.",
                        "decidedBy": {"actorId": "gk-1", "kind": "governance_kernel"},
                        "decidedAt": now,
                    }
                    svc.evaluate_policy(tool_policy, gk_meta("evaluate_agent_tool_policy"))
                    tool_grant = {
                        "schemaVersion": "1.0.0", "grantId": agent_tool_grant_id,
                        "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
                        "capabilityId": "cap.agent.tools", "operations": agent_tool_operations,
                        "scope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
                        "policyDecisionId": tool_policy_id, "policyBundleDigest": tool_bundle_digest,
                        "conditions": [{"kind": "isolated_worktree", "worktreeRoot": target_root}],
                        "maxUses": 128, "validFrom": now, "validUntil": "2030-01-01T00:00:00Z",
                        "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"}, "issuedAt": now,
                    }
                    svc.issue_grant(tool_grant, gk_meta("issue_agent_tool_grant"))
                    tool_lease = {
                        "schemaVersion": "1.0.0", "leaseId": agent_tool_lease_id,
                        "grantId": agent_tool_grant_id, "missionId": mission_id, "taskId": task_id,
                        "executionContextId": "ec-agent-tools-" + command_id,
                        "operations": agent_tool_operations,
                        "scope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
                        "maxUses": 128, "validFrom": now, "validUntil": "2030-01-01T00:00:00Z",
                        "activatedAt": now,
                    }
                    svc.activate_lease(tool_lease, gk_meta("activate_agent_tool_lease"))
                # 3. DriverHost dispatch with the resolved authoritative task.
                worktree = Path(target_root)
                staging = Path(ledger_path).parent / "staging" / run_id
                staging.mkdir(parents=True, exist_ok=True)
                if agent_enabled:
                    from capt_runtime.hermes_toolbridge import ToolBridgeBinding
                    bridge_binding = ToolBridgeBinding(
                        grant_id=agent_tool_grant_id, lease_id=agent_tool_lease_id,
                        filesystem_scope=str(worktree), runtime_sock=str(sock_path),
                        token_file=str(tf),
                    )
                    host = runtime.hermes_host(
                        target_repo=str(worktree), staging_root=str(staging),
                        executable=executable, enforce_memory=False,
                        dispatch_prompt=str(dispatch_prompt),
                        tool_bridge_binding=bridge_binding, provider_id=provider.id,
                        provider_model=str(provider_model), provider_api_key=provider_key,
                        workspace_mcp_executable=os.environ.get("CAPT_WORKSPACE_MCP_EXECUTABLE"),
                    )
                elif provider is not None:
                    host = runtime.provider_host(
                        target_repo=str(worktree), staging_root=str(staging),
                        provider_id=provider.id, model=str(provider_model),
                        base_url=provider.base_url, api_key=provider_key,
                        dispatch_prompt=str(dispatch_prompt),
                    )
                else:
                    host = runtime.hermes_host(
                        target_repo=str(worktree), staging_root=str(staging),
                        executable=executable, enforce_memory=False,
                        dispatch_prompt=str(dispatch_prompt),
                    )
                if skill_context is not None:
                    host.bind_prepared_authored_skills(skill_context, skill_names)
                ctx = host.build_context(
                    {"leaseId": lease["leaseId"], "operations": lease["operations"],
                     "scope": lease["scope"], "validFrom": lease["validFrom"],
                     "validUntil": lease["validUntil"]},
                    (["capt_broker"] if agent_enabled else ["terminal"]),
                    {"maxSeconds": 600, "maxArtifacts": 1, "maxObservations": 10},
                    [{"artifactPath": str(staging / "model-analysis.md"), "artifactKind": "report"}],
                    {"onUnexpectedWrite": "fail"},
                    skill_names=skill_names or None,
                )
                wo = {
                    "schemaVersion": "1.0.0", "driverRunId": run_id,
                    "driverId": "hermes" if agent_enabled else ("provider" if provider is not None else "hermes"),
                    "missionId": mission_id, "taskId": task_id, "workOrderVersion": 1,
                    "contextSlice": ctx,
                    "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"],
                }
                # DriverRunCreated was committed atomically with approval use.
                svc.transition_driver_run(run_id, "submitted", exec_meta("drsubmit"))
                svc.transition_driver_run(run_id, "running", exec_meta("drrun"))
                # The integrity baseline is CAPT-side evidence captured before the
                # external process. Existing operator dirt is part of the baseline;
                # only a delta is attributed to the driver. Persist it in CAPT
                # staging now so later verification does not depend on this receipt.
                baseline = capture_verification_baseline(
                    str(worktree), staging, mission_id, task_id, run_id, now
                )
                before = baseline["manifest"]["beforeDigest"]
                reservation_id = "res-" + command_id
                reservation = {
                    "schemaVersion": "1.0.0", "reservationId": reservation_id,
                    "leaseId": lease_id, "operation": "repository.read",
                    "operationFingerprint": commands.fingerprint("hermes.dispatch", {"driverRunId": run_id}),
                    "idempotencyKey": key + ":dispatch", "state": "open", "reservedAt": now,
                }
                svc.reserve_use(grant_id, reservation, exec_meta("reserve"))
                _test_fault("reservation")
                try:
                    out = host.dispatch(wo, ctx, {"state": "running"}, now=now, lease=dispatch_lease)
                except Exception:
                    # Dispatch reached an external boundary after reservation. The
                    # absence of a result is not proof that no side effect occurred:
                    # consume indeterminately and require recovery rather than retry.
                    consumption = {
                        "schemaVersion": "1.0.0", "consumptionId": "con-" + command_id,
                        "reservationId": reservation_id, "leaseId": lease_id,
                        "outcome": "indeterminate", "sideEffectIdentity": run_id, "finalizedAt": now,
                    }
                    svc.finalize_use(grant_id, consumption, exec_meta("finalize-indeterminate"))
                    # A dispatch exception after the boundary is not evidence of
                    # failure. Preserve the unknown as lost + suspended so the
                    # existing governed cancellation/reconciliation path, not an
                    # automatic retry, decides the terminal disposition.
                    svc.transition_driver_run(run_id, "lost", exec_meta("drlost"))
                    svc.transition_task(task_id, "suspended", "external dispatch outcome indeterminate; reconciliation required", exec_meta("tasksuspended"))
                    raise
                _test_fault("dispatch")
                svc.transition_driver_run(run_id, "completed", exec_meta("drcomplete"))
                _test_fault("driver_completed")
                # A returned driver result proves this invocation completed. Its
                # capability use is therefore consumed before any downstream claim
                # verification, which may still reject the result.
                consumption = {
                    "schemaVersion": "1.0.0", "consumptionId": "con-" + command_id,
                    "reservationId": reservation_id, "leaseId": lease_id,
                    "outcome": "succeeded", "sideEffectIdentity": out.get("externalRunId") or run_id,
                    "finalizedAt": now,
                }
                svc.finalize_use(grant_id, consumption, exec_meta("finalize"))
                _test_fault("capability_finalized")
                # 4. Verification + ClaimGuard (CAPT-authored).
                artifact_path = out["artifactCandidate"]["artifactPath"]
                artifact_digest = out["artifactCandidate"]["artifactDigest"]
                accepted = guard_claim("Repository inspected in read-only mode.")
                svc.propose_claim(
                    {"schemaVersion": "1.0.0", "claimId": claim_id, "missionId": mission_id,
                     "taskId": task_id, "kind": "completion", "statement": accepted,
                     "evidenceIds": [], "promotionState": "proposed",
                     "proposedBy": {"actorId": "cog-1", "kind": "cognitive_plane"},
                     "proposedAt": now, "sourceProposalId": None},
                    commands.command(command_id=command_id + ":claim", idempotency_key=key + ":claim",
                                     operation_fingerprint=commands.fingerprint("propose_claim", {"claimId": claim_id}),
                                     correlation_id=correlation_id,
                                     actor_id="cog-1", actor_kind="cognitive_plane",
                                     issued_at=now, replay_policy="never"),
                )
                baseline_ev_id = "ev-" + commands.fingerprint(
                    "artifact_hash", {"artifact": baseline["artifactDigest"], "role": "verification_baseline"}
                )
                result_ev_id = "ev-" + commands.fingerprint(
                    "artifact_hash", {"artifact": artifact_digest, "role": "driver_result"}
                )
                baseline_evidence = build_artifact_hash_evidence(
                    mission_id=mission_id, artifact_path=baseline["artifactPath"],
                    artifact_digest=baseline["artifactDigest"],
                    collected_by={"actorId": "verification_pipeline", "kind": "verification_plane"},
                    evidence_id=baseline_ev_id, task_id=task_id, collected_at=now,
                )
                result_evidence = build_artifact_hash_evidence(
                    mission_id=mission_id, artifact_path=artifact_path, artifact_digest=artifact_digest,
                    collected_by={"actorId": "verification_pipeline", "kind": "verification_plane"},
                    evidence_id=result_ev_id, task_id=task_id, collected_at=now,
                )
                def evidence_meta(step: str, evidence_id: str) -> Dict[str, Any]:
                    return commands.command(
                        command_id=command_id + ":" + step, idempotency_key=key + ":" + step,
                        operation_fingerprint=commands.fingerprint("record_evidence", {"evidenceId": evidence_id}),
                        correlation_id=correlation_id,
                        actor_id="verification_pipeline", actor_kind="verification_plane",
                        issued_at=now, replay_policy="never",
                    )
                svc.record_evidence(
                    claim_id, baseline_evidence, evidence_meta("evidence-baseline", baseline_ev_id)
                )
                svc.record_evidence(
                    claim_id, result_evidence, evidence_meta("evidence-result", result_ev_id)
                )
                _test_fault("evidence_recorded")
                # A provider response and its immutable artifact are evidence, not
                # verification.  Keep the claim proposed and the task in the
                # aggregate's existing awaiting_verification state; a later
                # verification/ClaimGuard authority must perform any promotion.
                svc.transition_task(task_id, "awaiting_verification", "provider response recorded; independent verification required", exec_meta("taskawaitingverification"))
                create_checkpoint(store, "cp-model-" + command_id, now,
                                  contracts.digest({"policyBundle": "model-operator", "version": 1}))
                receipt = {
                    "missionId": mission_id, "taskId": task_id, "driverRunId": run_id,
                    "claimId": claim_id, "verificationId": None,
                    "artifactPath": artifact_path, "artifactDigest": artifact_digest,
                    "targetPath": str(worktree), "beforeDigest": before,
                    "verificationBaselinePath": baseline["artifactPath"],
                    "verificationBaselineDigest": baseline["artifactDigest"],
                    "verificationBaselineEvidenceId": baseline_ev_id,
                    "resultEvidenceId": result_ev_id,
                    "observations": out.get("observations", []), "driver": "provider" if provider is not None else "hermes",
                    "providerProvenance": out.get("diagnostics", {}) if provider is not None else {},
                    "cognitiveProvenance": cognitive_provenance,
                    "authoredSkills": summarize_skill_context(ctx.get("skillContext")),
                }
                store.complete_claimed_command(key, command_fingerprint, receipt)
                return receipt
            class _PreparedApprovedHermesRunner:
                prepare = staticmethod(_prepare_approved_hermes)
                execute = staticmethod(_execute_approved_hermes)

            cmd_svc.approved_hermes_runner = _PreparedApprovedHermesRunner()
            def _runtime_checkpoint(command: Dict[str, Any]):
                from capt_runtime.checkpoint import create_checkpoint
                from capt_runtime.contracts import digest
                key = command["idempotencyKey"]
                prior = checkpoint_receipts.get(key)
                if prior is not None:
                    return {**prior, "_idempotent": True}
                manifest = create_checkpoint(runtime.store, "cp-" + command["commandId"], datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), digest({"policyBundle": "harness", "version": 1}))
                checkpoint_receipts[key] = manifest
                return manifest
            cmd_svc.runtime_checkpoint_runner = _runtime_checkpoint
            cmd_svc.shutdown_runner = lambda: (shutdown_requested.set() or {"shutdown": "accepted"})
            def _resume_runtime():
                from capt_runtime.checkpoint import verify_checkpoint
                manifest = runtime.store.latest_checkpoint()
                if manifest is None:
                    raise ValueError("NO_CHECKPOINT")
                verify_checkpoint(manifest)
                return {"checkpoint": manifest, "execution": "not_repeated"}
            cmd_svc.resume_runner = _resume_runtime
            _send_json(conn, {
                "ok": True, "authenticated": True,
                "operatorId": operator_id, "sessionId": session_id,
            })
            while True:
                req = _recv_json(conn)
                if req is None:
                    return
                if req.get("op") == "command":
                    # The command envelope must carry the SAME operatorId and
                    # sessionId bound to this connection, or it is rejected as
                    # unauthorized by the command service.
                    _send_json(conn, cmd_svc.execute(req.get("command", {})))
                else:
                    _send_json(conn, query.handle(req))
        except Exception:  # noqa: BLE001
            return
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    try:
        while not shutdown_requested.is_set():
            try:
                conn, _ = srv.accept()
            except (TimeoutError, socket.timeout):
                continue
            threading.Thread(target=handle_conn, args=(conn,), daemon=True).start()
    finally:
        runtime.close()
        try:
            sock_path.unlink()
        except OSError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--sock", required=True)
    ap.add_argument("--token-file", required=True)
    ap.add_argument("--seed", action="store_true")
    args = ap.parse_args()
    serve(args.ledger, args.sock, args.token_file, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
