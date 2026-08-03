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


def seed_demo_mission(store: EventStore) -> Dict[str, Any]:
    """Create a faithful read-only demonstration mission using real CAPT.

    Builds the M0-A governance/policy/capability/task sequence, then runs a
    REAL reference-driver read-only proof through DriverHost to produce a
    DriverRun, observation, artifact, verification result, and a bounded
    ClaimGuard claim. All authoritative state is written by CAPT, not the
    desktop.
    """
    # Idempotent: if the demo mission already exists, do not duplicate.
    if store.aggregate_version("mission-" + DEMO_MISSION_ID) > 0:
        return {"seeded": False, "reason": "demo mission already present"}

    svc = RuntimeService(store)

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

    reg = DriverRegistry()
    reg.register(REF)
    host = DriverHost(reg, str(staging), str(worktree))
    host.select_driver(OpenHarnessDriver(str(staging)))
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


# --------------------------------------------------------------------------
# Read-only IPC query handlers (authoritative state only)
# --------------------------------------------------------------------------

class RuntimeQueryService:
    def __init__(self, store: EventStore, demo: Optional[Dict[str, Any]] = None) -> None:
        self.store = store
        self.demo = demo or {}

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
        sock_path.unlink()

    store = EventStore(str(ledger_path))
    demo = None
    if seed:
        demo = seed_demo_mission(store)
    query = RuntimeQueryService(store, demo)

    token = secrets.token_hex(32)
    tf = Path(token_file)
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text(token)
    os.chmod(tf, 0o600)

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(8)
    print("CAPT_RUNTIME_SERVICE_READY sock=%s ledger=%s pid=%d" % (sock_path, ledger_path, os.getpid()))

    def handle_conn(conn: socket.socket) -> None:
        try:
            # Authenticate: first frame must be the session token.
            auth = _recv_json(conn)
            if not auth or auth.get("token") != token:
                _send_json(conn, {"ok": False, "error": "unauthenticated"})
                return
            _send_json(conn, {"ok": True, "authenticated": True})
            while True:
                req = _recv_json(conn)
                if req is None:
                    return
                _send_json(conn, query.handle(req))
        except Exception:  # noqa: BLE001
            return
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    try:
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=handle_conn, args=(conn,), daemon=True).start()
    finally:
        store.close()
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
