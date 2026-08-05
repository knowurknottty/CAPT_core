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
from datetime import UTC, datetime
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
from capt_runtime.store import EventStore
from capt_runtime.verification import build_verification_result, guard_claim
from capt_runtime.composition import RuntimeComposition, create_runtime

from desktop.m1_command_service import RuntimeCommandService

RUNTIME_VERSION = getattr(capt_runtime, "RUNTIME_VERSION", "0.1.0")
CONTRACT_SCHEMA_VERSION = "1.0.0"

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
    def __init__(self, store: EventStore, demo: Optional[Dict[str, Any]] = None, memory_engine: Any = None) -> None:
        self.store = store
        self.demo = demo or {}
        self.memory_engine = memory_engine

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

    def event_timeline(self, after: int = 0) -> List[Dict[str, Any]]:
        return self.store.read_events(after)

    def claimguard_disposition(self, statement: str) -> Dict[str, Any]:
        """Return ClaimGuard's verdict for a statement WITHOUT mutating state."""
        try:
            accepted = guard_claim(statement)
            return {"statement": accepted, "verdict": "accepted"}
        except Exception as exc:  # noqa: BLE001
            return {"statement": statement, "verdict": "rejected", "reason": str(exc)[:160]}

    def verification(self) -> Dict[str, Any]:
        """Recompute the CAPT-authored verification result for the demo artifact.

        This is a read-only computation over authoritative state (the artifact
        produced by the reference-driver proof). It is NOT a desktop decision.
        """
        if not self.demo.get("artifactPath"):
            return {"status": {"kind": "not_tested"}, "trust": "capt_authoritative"}
        try:
            return build_verification_result(
                self.demo["targetPath"],
                self.demo["beforeDigest"],
                self.demo["artifactPath"],
                self.demo["artifactDigest"],
                "openharness",
            )
        except Exception as exc:  # noqa: BLE001
            return {"status": {"kind": "failed"}, "error": str(exc)[:200],
                    "trust": "capt_authoritative"}

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        op = request.get("op")
        try:
            if op == "identity":
                return {"ok": True, "result": self.identity()}
            if op == "capabilities":
                return {"ok": True, "result": {
                    "schemaVersion": CONTRACT_SCHEMA_VERSION,
                    "queryOperations": ["identity", "capabilities", "list_aggregates", "get_state", "get_stream_events", "event_timeline", "claimguard", "verification", "get_memory_policy", "get_memory_state"],
                    "commandOperations": ["create_mission", "submit_approval_decision", "cancel_task", "cancel_driver_run", "update_memory_trigger_policy", "run_fixed_openharness_inspection", "run_approved_hermes_inspection", "checkpoint_runtime", "shutdown", "resume_runtime"],
                    "runtimeComponents": {"composition": True, "eventStore": True, "runtimeService": True, "driverRegistry": True, "driverHost": True, "memory": self.memory_engine is not None, "checkpointReplay": True, "khsb": True, "ctp": True},
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
                return {"ok": True, "result": self.event_timeline(int(request.get("after", 0)))}
            if op == "claimguard":
                return {"ok": True, "result": self.claimguard_disposition(request["statement"])}
            if op == "verification":
                return {"ok": True, "result": self.verification()}
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

    query = RuntimeQueryService(store, demo, memory_engine)

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
    hermes_work_receipts: Dict[str, Dict[str, Any]] = {}
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
            # Governed model operator: the CLI objective becomes authoritative
            # mission/task state; the frozen work order carries only the
            # missionId/taskId references; HermesDriver derives its prompt from
            # the resolved authoritative task (TaskResolver) inside CAPT.
            def _run_approved_hermes(command: Dict[str, Any]):
                key = command["idempotencyKey"]
                prior = hermes_work_receipts.get(key)
                if prior is not None:
                    return {**prior, "_idempotent": True}
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
                grant_id = payload.get("grantId") or ("g-model-" + command_id)
                lease_id = payload.get("leaseId") or ("l-model-" + command_id)
                claim_id = payload.get("claimId") or ("cl-model-" + command_id)
                policy_id = payload.get("policyDecisionId") or ("pd-model-" + command_id)
                executable = payload.get("executable") or None
                # 1. Authoritative mission/task state (objective persisted in
                # the Task aggregate by RuntimeService planning).
                intent = {
                    "schemaVersion": "1.0.0",
                    "missionId": mission_id,
                    "objective": objective,
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
                    "requestedCapability": "cap.fs.read",
                    "resource": target_root,
                    "operation": "ModelOperatorInspection",
                    "riskClassification": "low",
                    "taskId": task_id,
                }
                meta = commands.command(
                    command_id=command_id + ":mission",
                    idempotency_key=key + ":mission",
                    operation_fingerprint=commands.fingerprint("create_mission", intent),
                    correlation_id=command.get("correlationId", "corr-model"),
                    actor_id=cmd_svc.operator_id,
                    actor_kind="human",
                    issued_at=now,
                    replay_policy="never",
                )
                svc.create_mission_with_approval(intent, meta)
                exec_meta = lambda step: commands.command(
                    command_id=command_id + ":" + step,
                    idempotency_key=key + ":" + step,
                    operation_fingerprint=commands.fingerprint("transition_task", {"taskId": task_id, "to": step}),
                    correlation_id=command.get("correlationId", "corr-model"),
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
                    correlation_id=command.get("correlationId", "corr-model"),
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
                # 3. DriverHost dispatch with the resolved authoritative task.
                worktree = Path(target_root)
                staging = worktree.parent / (worktree.name + "-model-staging")
                staging.mkdir(parents=True, exist_ok=True)
                host = runtime.hermes_host(
                    target_repo=str(worktree), staging_root=str(staging),
                    executable=executable, enforce_memory=False,
                )
                ctx = host.build_context(
                    {"leaseId": lease["leaseId"], "operations": lease["operations"],
                     "scope": lease["scope"], "validFrom": lease["validFrom"],
                     "validUntil": lease["validUntil"]},
                    ["terminal"], {"maxSeconds": 600, "maxArtifacts": 1, "maxObservations": 10},
                    [{"artifactPath": str(staging / "model-analysis.md"), "artifactKind": "report"}],
                    {"onUnexpectedWrite": "fail"},
                )
                wo = {
                    "schemaVersion": "1.0.0", "driverRunId": run_id, "driverId": "hermes",
                    "missionId": mission_id, "taskId": task_id, "workOrderVersion": 1,
                    "contextSlice": ctx,
                    "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"],
                }
                svc.create_driver_run(
                    {"schemaVersion": "1.0.0", "driverRunId": run_id, "driverId": "hermes",
                     "missionId": mission_id, "taskId": task_id, "workOrderVersion": 1,
                     "externalRunId": None, "state": "created", "reconciliationStatus": "not_required",
                     "createdAt": now},
                    commands.command(command_id=command_id + ":drcreate", idempotency_key=key + ":drcreate",
                                     operation_fingerprint=commands.fingerprint("create_driver_run", {"driverRunId": run_id}),
                                     correlation_id=command.get("correlationId", "corr-model"),
                                     actor_id="exec-1", actor_kind="execution_plane",
                                     issued_at=now, replay_policy="never"),
                )
                svc.transition_driver_run(run_id, "submitted", exec_meta("drsubmit"))
                svc.transition_driver_run(run_id, "running", exec_meta("drrun"))
                out = host.dispatch(wo, ctx, {"state": "running"}, now=now, lease=dispatch_lease)
                svc.transition_driver_run(run_id, "completed", exec_meta("drcomplete"))
                # 4. Verification + ClaimGuard (CAPT-authored).
                artifact_path = out["artifactCandidate"]["artifactPath"]
                artifact_digest = out["artifactCandidate"]["artifactDigest"]
                before = tree_digest(str(worktree))
                vr = build_verification_result(str(worktree), before, artifact_path, artifact_digest, "hermes")
                accepted = guard_claim("Repository inspected in read-only mode.")
                svc.propose_claim(
                    {"schemaVersion": "1.0.0", "claimId": claim_id, "missionId": mission_id,
                     "taskId": task_id, "kind": "completion", "statement": accepted,
                     "evidenceIds": [], "promotionState": "proposed",
                     "proposedBy": {"actorId": "cog-1", "kind": "cognitive_plane"},
                     "proposedAt": now, "sourceProposalId": None},
                    commands.command(command_id=command_id + ":claim", idempotency_key=key + ":claim",
                                     operation_fingerprint=commands.fingerprint("propose_claim", {"claimId": claim_id}),
                                     correlation_id=command.get("correlationId", "corr-model"),
                                     actor_id="cog-1", actor_kind="cognitive_plane",
                                     issued_at=now, replay_policy="never"),
                )
                # 5. Checkpoint records continuation.
                create_checkpoint(store, "cp-model-" + command_id, now,
                                  contracts.digest({"policyBundle": "model-operator", "version": 1}))
                receipt = {
                    "missionId": mission_id, "taskId": task_id,
                    "driverRunId": run_id, "claimId": claim_id,
                    "verificationId": vr["verificationId"],
                    "artifactPath": artifact_path, "artifactDigest": artifact_digest,
                    "targetPath": str(worktree), "beforeDigest": before,
                    "observations": out.get("observations", []),
                    "driver": "hermes",
                }
                hermes_work_receipts[key] = receipt
                return receipt
            cmd_svc.approved_hermes_runner = _run_approved_hermes
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
            except TimeoutError:
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
