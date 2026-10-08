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
import fcntl
import getpass
import json
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version as distribution_version
from typing import Any, Dict, List, Optional

import capt_runtime
from capt_runtime import commands, contracts


from capt_runtime.checkpoint import (
    can_dispatch_consequential,
    create_checkpoint,
    verify_checkpoint,
)
from capt_runtime.driver_host import tree_digest
from capt_runtime.errors import AuthorityViolation
from capt_runtime.store import EventStore
from capt_runtime.ipc_framing import FrameProtocolError, recv_json, send_json
from capt_runtime.resource_governor import TokenCostGovernor
from capt_runtime.reasoning import ReasoningConfigurationError, normalize_reasoning_effort, legacy_cohort_configuration_reasoning_effort
from capt_runtime.cohort_contract import compile_cohort_objective, normalize_cohort_spec
from capt_runtime.vessel_charter import validate_vessel_artifact
from capt_runtime.replay import replay_to_sequence
from capt_runtime.verification import (
    build_artifact_hash_evidence,
    build_verification_result,
    guard_claim,
)
from capt_runtime.composition import RuntimeComposition, create_runtime
from capt_runtime.provider_endpoint import credential_required
from capt_runtime.model_authority import (
    assert_provider_network_allowed,
    canonical_execution_target_root,
    normalize_model_authority,
    revalidate_normalized_model_authority,
)
from capt_runtime.model_tool_authority import (
    issue_model_tool_authority, revoke_model_tool_authority,
)
from capt_runtime.operator_provenance import (
    build_cognitive_provenance, build_prompt_assembly, effective_context_budget,
)
from capt_runtime.model_approval_binding import (
    build_bound_model_operator_approval, staging_root_for_ledger,
)
from capt_runtime.prepared_execution import PreparedApprovedModelExecution, freeze
from capt_runtime.prompt_proposals import authoritative_proposal_binding_for_execution
from capt_runtime.verification_baseline import capture_verification_baseline
from capt_runtime.authored_skills import (
    parse_authored_skill_request, prepare_runtime_skill_context, summarize_skill_context,
)
from capt_runtime.managed_skills import default_managed_skill_root, verify_managed_skill_pack
from desktop.prompt_compiler_provider import build_prompt_compiler
from desktop.operator_control import OperatorControlStore


_COMMAND_TIMESTAMP_SKEW_BOUND_SECONDS = 300


def _parse_rfc3339_timestamp(value: Any) -> datetime:
    """Parse an RFC3339 timestamp, failing closed on malformed input."""
    stamp = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _check_command_timestamp_skew(
    command_issued_at: Any,
    consumed_at: str,
    bound_seconds: int = _COMMAND_TIMESTAMP_SKEW_BOUND_SECONDS,
) -> None:
    """Fail closed when a command-carried timestamp disagrees with authoritative wall-clock time.

    The preparation path stamps authority consumption with the runtime's own
    clock. A command-carried timestamp that is missing, malformed, or skewed
    beyond the bound is evidence of tampering or clock failure and must not
    be silently trusted as the authority-consumption time.
    """
    if not command_issued_at:
        raise AuthorityViolation("MODEL_COMMAND_TIMESTAMP_MISSING")
    try:
        skew = abs(
            (_parse_rfc3339_timestamp(command_issued_at) - _parse_rfc3339_timestamp(consumed_at)).total_seconds()
        )
    except Exception as exc:
        raise AuthorityViolation("MODEL_COMMAND_TIMESTAMP_MALFORMED") from exc
    if skew > bound_seconds:
        raise AuthorityViolation("MODEL_COMMAND_TIMESTAMP_SKEW")

RUNTIME_VERSION = getattr(capt_runtime, "RUNTIME_VERSION", "0.1.0")
CONTRACT_SCHEMA_VERSION = "1.0.0"


def _build_provider_governor(store: EventStore) -> TokenCostGovernor:
    """Build the paid-provider budget boundary and independent spend alert."""
    max_cost = float(os.environ.get("CAPT_PROVIDER_SESSION_COST_CAP_USD", "10"))
    if max_cost <= 0:
        raise ValueError("COST_CAP_INVALID")
    raw_alert = os.environ.get("CAPT_PROVIDER_SPEND_ALERT_USD", "").strip()
    alert_cost = float(raw_alert) if raw_alert else max_cost * 0.8

    def emit_alert(details: Dict[str, Any]) -> None:
        store.record_security_rejection(
            rejection_id="spend-alert-" + secrets.token_hex(8),
            rejection_kind="provider_spend_threshold_alert",
            details=dict(details),
        )
        print(
            "CAPT_SPEND_ALERT consumed=${consumedCostUsd:.4f} threshold=${thresholdUsd:.4f} cap=${maxCostUsd:.4f}".format(**details),
            file=sys.stderr,
            flush=True,
        )

    return TokenCostGovernor(
        max_cost_usd_per_session=max_cost,
        alert_cost_usd=alert_cost,
        on_cost_alert=emit_alert,
    )


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


def _reconcile_legacy_issue_task_marker(runtime: RuntimeComposition, now: str) -> bool:
    """Conservatively suspend the one historical manual task with no run lineage.

    This narrow migration does not discover a worker or assert completion.
    Other running tasks are never touched. Repeated startups are no-ops.
    """
    task_id = "m-capt-issues-20260924-live-task-1"
    mission_id = "m-capt-issues-20260924-live"
    store, svc = runtime.store, runtime.service
    task_stream = "task-" + task_id
    task = store.load_state(task_stream)
    if not task or task.get("state") not in ("running", "suspended"):
        return False
    if task.get("missionId") != mission_id or task.get("assignedDriverId") != "capt-node":
        return False
    if task.get("resultRefs") or task.get("attempt") != 1:
        return False
    events = store.read_stream(task_stream)
    if not events or events[-1].get("eventType") != "TaskTransitioned":
        return False
    if events[-1].get("payload", {}).get("toState") not in ("running", "suspended"):
        return False
    try:
        last = datetime.fromisoformat(events[-1]["occurredAt"].replace("Z", "+00:00"))
        current = datetime.fromisoformat(now.replace("Z", "+00:00"))
        if (current - last).total_seconds() < 86400:
            return False
    except (TypeError, ValueError):
        return False
    # No stable driver/effect identity means we cannot invent one or replay.
    # Refuse recovery if *any* durable DriverRun/ToolExecution was associated
    # with this exact task, even if now terminal; such cases need manual review.
    for stream_id, kind, _ in store.all_aggregates():
        if kind not in ("driverrun", "tool_execution"):
            continue
        effect = store.load_state(stream_id)
        if effect and effect.get("taskId") == task_id:
            return False
    def metadata(step: str) -> Dict[str, Any]:
        return commands.command(
            command_id="cmd-reconcile-20261008-legacy-issue-task-" + step,
            idempotency_key="idem-reconcile-20261008-legacy-issue-task-" + step,
            operation_fingerprint=commands.fingerprint(
                "reconcile_legacy_issue_task_marker", {"taskId": task_id, "step": step}
            ),
            correlation_id="corr-reconcile-20261008-legacy-issue-task",
            actor_id="capt-recovery", actor_kind="system",
            issued_at=now, replay_policy="never",
        )
    changed = False
    if task["state"] == "running":
        svc.transition_task(
            task_id, "suspended",
            "historical manual running marker has no durable DriverRun/ToolExecution; "
            "actual worker completion unknown; inspect external work before resumption",
            metadata("task"), expected_version=store.aggregate_version(task_stream),
        )
        changed = True
    mission_stream = "mission-" + mission_id
    mission = store.load_state(mission_stream)
    if mission and mission.get("state") == "executing":
        svc.transition_mission(
            mission_id, "suspended",
            "the only historical issue task requires governed reconciliation; "
            "no completion is asserted",
            metadata("mission"), expected_version=store.aggregate_version(mission_stream),
        )
        changed = True
    return changed


DEMO_MISSION_ID = "m-desktop-m0-demo"
DEMO_TASK_ID = "t-desktop-m0-demo"
DEMO_DRIVER_RUN_ID = "dr-desktop-m0-demo"
DEMO_GRANT_ID = "g-desktop-m0-demo"
DEMO_LEASE_ID = "l-desktop-m0-demo"
DEMO_CLAIM_ID = "cl-desktop-m0-demo"
DEMO_WORKTREE = "/tmp/capt-desktop-m0-demo-worktree"


def _prepare_hermes_host_with_authored_skills(
    runtime: RuntimeComposition, payload: Dict[str, Any], *, target_repo: str,
    staging_root: str, executable: Optional[str] = None,
    authored_skill_pack_lock: Optional[Dict[str, Any]] = None,
):
    """Bind explicit command skill selection to a pin-verifying DriverHost."""
    skill_root, skill_names = parse_authored_skill_request(payload)
    host = runtime.hermes_host(
        target_repo=target_repo, staging_root=staging_root, executable=executable,
        enforce_memory=False, authored_skill_pack_root=skill_root,
        authored_skill_pack_lock=authored_skill_pack_lock,
    )
    if skill_names:
        host.prepare_authored_skills(skill_names)
    return host, skill_names


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

def _installed_package_version() -> str:
    """Release identity, distinct from the checkpoint compatibility version."""
    try:
        return distribution_version("capt-solo")
    except PackageNotFoundError:
        return "unknown"


class RuntimeQueryService:
    def __init__(
        self, store: EventStore, demo: Optional[Dict[str, Any]] = None,
        memory_engine: Any = None, mcp_manager: Any = None,
        operator_control: OperatorControlStore | None = None,
        pi_active_attempts: set[str] | None = None,
        media_registry: Any = None,
        media_config_error: str | None = None,
    ) -> None:
        self.store = store
        self.pi_active_attempts = pi_active_attempts
        self.media_registry = media_registry
        self.media_config_error = media_config_error
        self.demo = demo or {}
        self.memory_engine = memory_engine
        self.mcp_manager = mcp_manager
        self.operator_control = operator_control

    def identity(self) -> Dict[str, Any]:
        return {
            "runtimeVersion": RUNTIME_VERSION,  # checkpoint compatibility; not app release
            "packageVersion": _installed_package_version(),
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

    def managed_skills(self) -> Dict[str, Any]:
        root = default_managed_skill_root(Path(self.store.path).parent)
        if not root.is_dir():
            return {
                "schemaVersion": CONTRACT_SCHEMA_VERSION,
                "packRoot": str(root),
                "installed": False,
                "packName": "ultimate",
                "packVersion": None,
                "manifestDigest": None,
                "trust": None,
                "skills": [],
            }
        verified = verify_managed_skill_pack(root)
        return {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "packRoot": str(root.resolve()),
            "installed": True,
            "packName": verified["packName"],
            "packVersion": verified["packVersion"],
            "manifestDigest": verified["manifestDigest"],
            "trust": verified["trust"],
            "skills": [
                {
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "version": item.get("version") or "0.0.0",
                    "contentDigest": item["contentDigest"],
                    "triggers": list(item.get("triggers") or []),
                }
                for item in verified["skills"]
            ],
        }

    def get_state(self, stream_id: str) -> Optional[Dict[str, Any]]:
        return self.store.load_state(stream_id)

    def get_stream_events(self, stream_id: str) -> List[Dict[str, Any]]:
        return self.store.read_stream(stream_id)

    def event_timeline(self, after: int = 0, limit: int = 250) -> List[Dict[str, Any]]:
        bounded = max(1, min(int(limit), 1000))
        return self.store.read_recent_events(after_sequence=after, limit=bounded)

    def replay_state_at(self, global_sequence: int, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """Project deterministic historical state without mutating the runtime."""
        state = replay_to_sequence(self.store, int(global_sequence))
        result: Dict[str, Any] = {
            "globalSequence": int(global_sequence),
            "headSequence": self.store.head_sequence(),
            "stateDigest": state.digest(),
            "summary": state.summary(),
        }
        if stream_id is not None:
            result.update({
                "streamId": stream_id,
                "streamVersion": state.versions.get(stream_id),
                "state": state.aggregates.get(stream_id),
            })
        return result

    def operator_control_snapshot(self) -> Dict[str, Any]:
        if self.operator_control is None:
            raise RuntimeError("OPERATOR_CONTROL_UNAVAILABLE")
        return self.operator_control.snapshot()

    def operator_session_get(self, session_id: str) -> Dict[str, Any]:
        if self.operator_control is None:
            raise RuntimeError("OPERATOR_CONTROL_UNAVAILABLE")
        state = self.operator_control.session_get(session_id)
        if state is None:
            raise KeyError("OPERATOR_CONTROL_SESSION_UNKNOWN")
        return state

    def operator_proposal_get(self, proposal_id: str | None = None) -> Dict[str, Any]:
        control = self.operator_control_snapshot()
        selected = proposal_id or control.get("proposalId")
        if not selected:
            return {"control": control, "configurationDigest": control["configurationDigest"], "proposal": None}
        proposal = self.store.load_state("prompt_proposal-" + str(selected))
        if proposal is None:
            raise KeyError("OPERATOR_CONTROL_PROPOSAL_UNKNOWN")
        return {"control": control, "configurationDigest": control["configurationDigest"], "proposal": proposal}

    def operator_execution_state(self) -> Dict[str, Any]:
        control = self.operator_control_snapshot()
        out: Dict[str, Any] = {"control": control}
        for key, prefix in (("approvalRequestId", "human_approval-"), ("taskId", "task-"),
                            ("driverRunId", "driverrun-"), ("claimId", "claim-")):
            identity = control.get(key)
            if identity:
                out[key.removesuffix("Id") + "State"] = self.store.load_state(prefix + str(identity))
        return out

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

    # ------------------------------------------------------------------
    # Read projections.
    #
    # CAPT accepts ~26 command ops that create and transition governed state,
    # but before these ops there was almost no way to READ that state: an
    # operator could command a mission, approval or checkpoint and then not
    # inspect it (and confirming a checkpoint persisted meant opening the
    # ledger file directly, which the runtime is supposed to own).
    #
    # Every projection below is DERIVED from authoritative store state and
    # never rewrites it. The stored ``state`` is reported verbatim; any
    # refinement arrives in an explicitly-named derived field. Nothing here can
    # invent a transition the runtime did not actually take.
    # ------------------------------------------------------------------

    def _aggregate_states(self, kind: str) -> List[Dict[str, Any]]:
        """Load every aggregate of one kind. States come from the store as-is.

        The kind filter is applied BEFORE ``load_state`` so only matching
        aggregates are unsealed.
        """
        out: List[Dict[str, Any]] = []
        for stream_id, agg_kind, _version in self.store.all_aggregates():
            if agg_kind != kind:
                continue
            state = self.store.load_state(stream_id)
            if isinstance(state, dict):
                out.append({"streamId": stream_id, **state})
        return out

    @staticmethod
    def _derive_expiry(expires_at: Optional[str]) -> Dict[str, Any]:
        """Derive expiry WITHOUT claiming the runtime took the transition.

        CAPT never drives ``expired`` (HumanApprovalAggregate.mark_expired has
        no caller), so a past-due approval still reads ``approved`` in state.
        Callers therefore get the stored state verbatim plus this derived view,
        and are told which is which.
        """
        if not expires_at:
            return {"expiresAt": None, "expired": None, "expiresInSeconds": None}
        try:
            when = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            return {"expiresAt": expires_at, "expired": None,
                    "expiresInSeconds": None, "expiryUnparseable": True}
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        delta = int((when - datetime.now(timezone.utc)).total_seconds())
        return {"expiresAt": expires_at, "expired": delta <= 0,
                "expiresInSeconds": delta}

    def bots(self, request: Dict[str, Any]) -> Dict[str, Any]:
        # Read bounded CAPT Bot identity/policy projections without secret material.
        role_kind = request.get("roleKind")
        mission_id = request.get("missionId")
        limit = int(request.get("limit", 100))
        entries: List[Dict[str, Any]] = []
        by_role: Dict[str, int] = {}
        for agg in self._aggregate_states("bot"):
            role = str(agg.get("roleKind") or "")
            by_role[role] = by_role.get(role, 0) + 1
            if role_kind and role != role_kind:
                continue
            if mission_id and agg.get("missionId") != mission_id:
                continue
            model_strategy = agg.get("modelStrategy") or {}
            cognition = agg.get("cognitionPolicy") or {}
            locality = agg.get("localityPolicy") or {}
            collaboration = agg.get("collaboration") or {}
            entries.append({
                "botId": agg.get("botId"),
                "displayName": agg.get("displayName"),
                "roleKind": role,
                "role": agg.get("role"),
                "missionId": agg.get("missionId"),
                "primaryModel": model_strategy.get("primary"),
                "fallbackModels": list(model_strategy.get("fallbacks") or []),
                "promotionMode": cognition.get("promotionMode"),
                "defaultRuntime": locality.get("defaultRuntime"),
                "privateData": locality.get("privateData"),
                "mayDelegate": bool(collaboration.get("mayDelegate", False)),
                "maxSpawnDepth": int(collaboration.get("maxSpawnDepth", 0)),
                "authorityTemplateRef": agg.get("authorityTemplateRef"),
                "createdAt": agg.get("createdAt"),
            })
        entries.sort(key=lambda e: (str(e.get("displayName") or ""), str(e.get("botId") or "")))
        return {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "count": len(entries),
            "countsByRoleKind": by_role,
            "note": (
                "Bot identity and policy are authoritative EventStore projections. "
                "Identity is not authority; credentials and live capability leases are never exposed here."
            ),
            "bots": entries[:limit],
        }

    def approvals(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Read approvals, with expiry DERIVED rather than asserted."""
        wanted_state = request.get("state")
        mission_id = request.get("missionId")
        actionable_only = bool(request.get("actionableOnly", False))
        limit = int(request.get("limit", 50))

        entries: List[Dict[str, Any]] = []
        by_state: Dict[str, int] = {}
        for agg in self._aggregate_states("human_approval"):
            state = agg.get("state")
            by_state[str(state)] = by_state.get(str(state), 0) + 1
            if wanted_state and state != wanted_state:
                continue
            if mission_id and agg.get("missionId") != mission_id:
                continue
            expiration = self._derive_expiry(agg.get("expiresAt"))
            awaiting_decision = state == "requested"
            awaiting_consumption = state == "approved"
            entries.append({
                "requestId": agg.get("requestId"),
                "missionId": agg.get("missionId"),
                "taskId": agg.get("taskId"),
                "state": state,                       # verbatim, authoritative
                "decision": agg.get("decision"),
                "operation": agg.get("operation"),
                "requestedCapability": agg.get("requestedCapability"),
                "riskClassification": agg.get("riskClassification"),
                "resource": agg.get("resource"),
                "requestedBy": agg.get("requestedBy"),
                "operatorId": agg.get("operatorId"),
                "createdAt": agg.get("createdAt"),
                "decidedAt": agg.get("decidedAt"),
                "consumedAt": agg.get("consumedAt"),
                "remainingUses": agg.get("remainingUses"),
                "policyReason": agg.get("policyReason"),
                **expiration,
                "awaitingDecision": awaiting_decision,        # derived
                "awaitingConsumption": awaiting_consumption,  # derived
                # Stale: the runtime still says approved but the window passed.
                "derivedStale": bool(awaiting_consumption and expiration["expired"]),
            })
            if actionable_only and not (awaiting_decision or awaiting_consumption):
                entries.pop()
        entries.sort(key=lambda e: str(e.get("createdAt") or ""), reverse=True)
        return {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "count": len(entries),
            "totalAggregates": sum(by_state.values()),
            "countsByStoredState": by_state,
            "awaitingDecision": sum(1 for e in entries if e["awaitingDecision"]),
            "awaitingConsumption": sum(1 for e in entries if e["awaitingConsumption"]),
            "derivedStale": sum(1 for e in entries if e["derivedStale"]),
            "note": ("`state` is the stored value. CAPT never drives the `expired` "
                     "transition, so a past-due approval still reads 'approved'; "
                     "`expired`/`derivedStale` are computed here and are NOT state."),
            "approvals": entries[:limit],
        }

    def missions(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Read missions with derived task counts."""
        wanted_state = request.get("state")
        limit = int(request.get("limit", 50))
        task_counts: Dict[str, int] = {}
        task_states: Dict[str, Dict[str, int]] = {}
        for task in self._aggregate_states("task"):
            mid = task.get("missionId")
            if not mid:
                continue
            task_counts[mid] = task_counts.get(mid, 0) + 1
            bucket = task_states.setdefault(mid, {})
            tstate = str(task.get("state"))
            bucket[tstate] = bucket.get(tstate, 0) + 1
        by_state: Dict[str, int] = {}
        entries: List[Dict[str, Any]] = []
        for agg in self._aggregate_states("mission"):
            state = agg.get("state")
            by_state[str(state)] = by_state.get(str(state), 0) + 1
            if wanted_state and state != wanted_state:
                continue
            mid = agg.get("missionId")
            entries.append({
                "missionId": mid,
                "state": state,
                "objectives": agg.get("objectives") or [],
                "successCriteria": agg.get("successCriteria") or [],
                "terminationCriteria": agg.get("terminationCriteria") or [],
                "policyDecisionIds": agg.get("policyDecisionIds") or [],
                "taskGraphId": agg.get("taskGraphId"),
                "taskCount": task_counts.get(mid, 0),           # derived
                "taskStates": task_states.get(mid, {}),         # derived
            })
        entries.sort(key=lambda e: str(e.get("missionId")))
        return {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "count": len(entries),
            "countsByState": by_state,
            "note": ("Mission state carries no timestamp, so entries are ordered by "
                     "missionId, not recency."),
            "missions": entries[:limit],
        }

    def tasks(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Read tasks, optionally scoped to a mission or a state."""
        wanted_state = request.get("state")
        mission_id = request.get("missionId")
        limit = int(request.get("limit", 100))
        by_state: Dict[str, int] = {}
        entries: List[Dict[str, Any]] = []
        for agg in self._aggregate_states("task"):
            state = agg.get("state")
            by_state[str(state)] = by_state.get(str(state), 0) + 1
            if wanted_state and state != wanted_state:
                continue
            if mission_id and agg.get("missionId") != mission_id:
                continue
            entries.append({
                "taskId": agg.get("taskId"),
                "missionId": agg.get("missionId"),
                "title": agg.get("title"),
                "state": state,
                "consequential": agg.get("consequential"),
                "attempt": agg.get("attempt"),
                "maxAttempts": agg.get("maxAttempts"),
                "recoveryState": agg.get("recoveryState"),
                "assignedDriverId": agg.get("assignedDriverId"),
                "dependencyCount": len(agg.get("dependencies") or []),
                "capabilityRequirementCount": len(agg.get("capabilityRequirements") or []),
                "resultRefCount": len(agg.get("resultRefs") or []),
            })
        entries.sort(key=lambda e: str(e.get("taskId")))
        return {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "count": len(entries),
            "countsByState": by_state,
            "tasks": entries[:limit],
        }

    def checkpoints(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Read checkpoints: the recovery surface that had no read op.

        Column data comes from ``EventStore.list_checkpoints``; ``createdAt``,
        ``recoveryState`` and ``canDispatchConsequential`` require the sealed
        manifest and are therefore loaded per row. Integrity is re-verified
        rather than trusted from the stored digest.
        """
        limit = int(request.get("limit", 20))
        include_manifest_detail = bool(request.get("detail", True))
        entries: List[Dict[str, Any]] = []
        for row in self.store.list_checkpoints(limit):
            entry: Dict[str, Any] = dict(row)
            if include_manifest_detail:
                try:
                    manifest = self.store.load_checkpoint(row["checkpointId"])
                    entry["createdAt"] = manifest.get("createdAt")
                    entry["runtimeVersion"] = manifest.get("runtimeVersion")
                    recovery = manifest.get("recoveryState") or {}
                    entry["recoveryState"] = recovery.get("kind")
                    entry["openReservations"] = recovery.get("openReservationIds") or []
                    entry["canDispatchConsequential"] = can_dispatch_consequential(manifest)
                    try:
                        verify_checkpoint(manifest)
                        entry["integrityVerified"] = True
                    except Exception as exc:  # noqa: BLE001
                        entry["integrityVerified"] = False
                        entry["integrityError"] = ("%s: %s"
                                                   % (type(exc).__name__, exc))[:200]
                except Exception as exc:  # noqa: BLE001
                    entry["manifestUnreadable"] = ("%s: %s"
                                                   % (type(exc).__name__, exc))[:200]
            entries.append(entry)
        return {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "count": len(entries),
            "note": ("A checkpoint binds the ledger head at write time; the write "
                     "does NOT advance the head. `integrityVerified` is recomputed "
                     "here, not read from the stored digest."),
            "checkpoints": entries,
        }

    def security_rejections(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Read the security audit trail.

        Recording a refusal without a way to read it back leaves the audit trail
        write-only, which is the same 'commandable but not inspectable' gap the
        other projections close. Only digests of identities are stored, so this
        surface cannot leak the identifiers it protects.
        """
        wanted_kind = request.get("kind")
        limit = int(request.get("limit", 100))
        include_details = bool(request.get("detail", True))

        entries: List[Dict[str, Any]] = []
        by_kind: Dict[str, int] = {}
        for row in self.store.list_security_rejections(limit=limit):
            kind = row.get("rejectionKind")
            by_kind[str(kind)] = by_kind.get(str(kind), 0) + 1
            if wanted_kind and kind != wanted_kind:
                continue
            entry = {
                "rejectionId": row.get("rejectionId"),
                "timestamp": row.get("timestamp"),
                "rejectionKind": kind,
                "actorId": row.get("actorId"),
                "sourceIp": row.get("sourceIp"),
            }
            if include_details:
                entry["details"] = row.get("details")
            entries.append(entry)
        return {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "count": len(entries),
            "countsByKind": by_kind,
            "note": ("Identities are recorded as digests only; `actorId` is a digest, "
                     "never a raw operator or session identifier. The store's "
                     "rejection_kind column is unconstrained TEXT, so treat "
                     "countsByKind as observed values, not a closed enumeration."),
            "rejections": entries,
        }

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        op = request.get("op")
        try:
            if op == "identity":
                return {"ok": True, "result": self.identity()}
            if op == "capabilities":
                return {"ok": True, "result": {
                    "schemaVersion": CONTRACT_SCHEMA_VERSION,
                    "queryOperations": ["council_receipt", "provider_failure_diagnostic", "identity", "capabilities", "list_aggregates", "bots", "approvals", "missions", "tasks", "checkpoints", "security_rejections", "get_state", "get_stream_events", "event_timeline", "replay_state_at", "claimguard", "verification", "get_memory_policy", "get_memory_state", "mcp_servers", "managed_skills", "operator_control_snapshot", "operator_session_get", "operator_proposal_get", "operator_execution_state", "pi_request_status", "media_route_catalog", "media_job_status"],
                    "commandOperations": ["create_mission", "prepare_media_approval", "submit_approved_media", "poll_media_job", "fetch_media_artifact", "register_bot", "operator_chat_new", "operator_execution_config_set", "operator_prompt_submit", "operator_proposal_select", "compile_prompt_proposal", "revise_prompt_proposal", "cancel_prompt_proposal", "request_prompt_proposal_approval", "request_model_prompt_approval", "submit_approval_decision", "activate_approved_capability", "submit_provider_result_review", "cancel_task", "cancel_driver_run", "steer_deliberation", "revoke_capability", "create_replay_fork", "update_memory_trigger_policy", "run_fixed_openharness_inspection", "run_approved_hermes_inspection", "run_approved_council_inspection", "checkpoint_runtime", "shutdown", "resume_runtime", "run_tool", "install_managed_skill", "create_managed_skill"],
                    "runtimeComponents": {"composition": True, "eventStore": True, "runtimeService": True, "driverRegistry": True, "driverHost": True, "memory": self.memory_engine is not None, "checkpointReplay": True, "khsb": True, "ctp": True, "toolRegistry": True, "toolBroker": True, "mcpClient": self.mcp_manager is not None, "promptCompiler": True, "botFoundation": True},
                    "lifecycleOperations": {"checkpoint": True, "shutdown": True, "resume": True},
                }}
            if op == "operator_control_snapshot":
                return {"ok": True, "result": self.operator_control_snapshot()}
            if op == "operator_session_get":
                return {"ok": True, "result": self.operator_session_get(str(request["sessionId"]))}
            if op == "operator_proposal_get":
                return {"ok": True, "result": self.operator_proposal_get(request.get("proposalId"))}
            if op == "operator_execution_state":
                return {"ok": True, "result": self.operator_execution_state()}
            if op == "media_route_catalog":
                if self.media_config_error:
                    return {"ok": False, "error": "MEDIA_CONFIGURATION_INVALID"}
                from desktop.media_registry import media_route_catalog
                from capt_runtime.media_execution import MediaRouteRegistry
                return {"ok": True, "result": media_route_catalog(
                    self.media_registry or MediaRouteRegistry({}))}
            if op == "media_job_status":
                from capt_runtime.media_execution import media_job_status
                return {"ok": True, "result": media_job_status(
                    self.store, str(request["driverRunId"]))}
            if op == "pi_request_status":
                from capt_runtime.prompt_proposals import pi_attempt_status
                return {"ok": True, "result": pi_attempt_status(
                    self.store, str(request["proposalId"]), self.pi_active_attempts
                )}
            if op == "managed_skills":
                return {"ok": True, "result": self.managed_skills()}
            if op == "list_aggregates":
                return {"ok": True, "result": self.list_aggregates()}
            if op == "bots":
                return {"ok": True, "result": self.bots(request)}
            if op == "approvals":
                return {"ok": True, "result": self.approvals(request)}
            if op == "missions":
                return {"ok": True, "result": self.missions(request)}
            if op == "tasks":
                return {"ok": True, "result": self.tasks(request)}
            if op == "checkpoints":
                return {"ok": True, "result": self.checkpoints(request)}
            if op == "security_rejections":
                return {"ok": True, "result": self.security_rejections(request)}
            if op == "council_receipt":
                council_id = str(request.get("councilId") or "")
                if not council_id or len(council_id) > 128:
                    return {"ok": False, "error": "COUNCIL_ID_REQUIRED"}
                return {"ok": True, "result": self.store.get_council_receipt(council_id)}
            if op == "provider_failure_diagnostic":
                run_id = str(request.get("driverRunId") or "")
                if not run_id.startswith("dr-") or len(run_id) > 128:
                    return {"ok": False, "error": "DRIVER_RUN_ID_REQUIRED"}
                return {"ok": True, "result": self.store.get_provider_failure_diagnostic(run_id)}
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
            if op == "replay_state_at":
                return {"ok": True, "result": self.replay_state_at(
                    int(request["globalSequence"]), request.get("streamId")
                )}
            if op == "claimguard":
                return {"ok": True, "result": self.claimguard_disposition(
                    request["statement"], request.get("claimId")
                )}
            if op == "verification":
                return {"ok": True, "result": self.verification(request.get("claimId"))}
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
            if op == "mcp_servers":
                if self.mcp_manager is None:
                    return {"ok": True, "result": {
                        "schemaVersion": "1.0.0", "stateDirectory": None, "servers": []
                    }}
                return {"ok": True, "result": self.mcp_manager.snapshot()}
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
    try:
        return recv_json(sock)
    except (FrameProtocolError, ValueError):
        return None


def _send_json(sock: socket.socket, payload: Dict[str, Any]) -> None:
    send_json(sock, payload)


def _acquire_runtime_state_lock(ledger_path: str):
    """Own the runtime state directory before socket/token mutation."""
    lock_path = Path(ledger_path).parent / "runtime.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError(
            "CAPT runtime service already active; already owns state lock: %s" % lock_path
        ) from exc
    handle.seek(0)
    handle.truncate(0)
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def _validate_biocapt_qipc_startup_request(
    *, enabled: bool, source_root: str | None, interpreter: str | None,
) -> None:
    """Reject malformed optional activation BEFORE runtime lock/DB startup."""
    if not enabled:
        if source_root or interpreter:
            raise ValueError("BIOCAPT_QIPC_REQUIRES_EXPLICIT_ENABLE_FLAG")
        return
    if not source_root or not interpreter:
        raise ValueError("BIOCAPT_QIPC_EXPLICIT_SOURCE_AND_INTERPRETER_REQUIRED")


def _register_optional_biocapt_qipc(
    runtime: RuntimeComposition,
    *,
    enabled: bool,
    source_root: str | None,
    interpreter: str | None,
) -> None:
    """Opt-in local cognitive tool registration with zero implicit authority.

    Imports an installed, source-reviewed CAPT Ouroboros adapter only when
    explicitly requested by the operator's startup configuration. Running
    inference, minting a grant, starting a mission and registering a bot are
    NOT side effects of this function. It never adjusts sys.path to point at
    arbitrary executable source trees.
    """
    _validate_biocapt_qipc_startup_request(
        enabled=enabled, source_root=source_root, interpreter=interpreter,
    )
    if not enabled:
        return
    from capt_ouroboros.qipc_tool_broker import attach_biocapt_qipc_to_composition

    adapter = attach_biocapt_qipc_to_composition(
        runtime, source_root=source_root, interpreter=interpreter,
    )
    if runtime.tool_registry.readiness("biocapt.qipc")["status"] != "available":
        raise RuntimeError("BIOCAPT_QIPC_REGISTRATION_NOT_READY")
    if adapter.calls != 0:
        raise RuntimeError("BIOCAPT_QIPC_REGISTRATION_TRIGGERED_EXECUTION")


def serve(
    ledger_path: str, sock_path: Path, token_file: str, seed: bool,
    *, enable_biocapt_qipc: bool = False,
    biocapt_qipc_source_root: str | None = None,
    biocapt_qipc_interpreter: str | None = None,
) -> None:
    _validate_biocapt_qipc_startup_request(
        enabled=enable_biocapt_qipc,
        source_root=biocapt_qipc_source_root,
        interpreter=biocapt_qipc_interpreter,
    )
    lock_handle = _acquire_runtime_state_lock(ledger_path)
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

    runtime = create_runtime(str(ledger_path), enable_mcp=True)
    try:
        _register_optional_biocapt_qipc(
            runtime, enabled=enable_biocapt_qipc,
            source_root=biocapt_qipc_source_root,
            interpreter=biocapt_qipc_interpreter,
        )
    except Exception:
        runtime.close()
        raise
    prompt_compiler = build_prompt_compiler(Path(ledger_path).parent / "ui")
    recovery_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _reconcile_stranded_driver_runs(runtime, recovery_now)
    _reconcile_legacy_issue_task_marker(runtime, recovery_now)
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
    operator_control = OperatorControlStore(
        Path(ledger_path).parent / "operator-control.json",
        {
            "provider": "ollama",
            "model": "qwen3.5-defiant-fable:latest",
            "targetRoot": "",
            "promptIntelligence": "AUTO",
        },
    )

    pi_active_attempts: set[str] = set()
    from desktop.media_registry import load_media_routes, media_credential_provider
    from capt_runtime.media_execution import MediaRouteRegistry
    media_config_error = None
    try:
        media_registry, media_key_refs = load_media_routes(Path(ledger_path).parent / "ui")
    except Exception:
        # Optional malformed media settings cannot take down the resident daemon.
        # Fail closed: ZERO routes, no provider authority, no secret-bearing logs.
        media_registry, media_key_refs = MediaRouteRegistry({}), {}
        media_config_error = "MEDIA_CONFIGURATION_INVALID"
    media_credential_resolver = media_credential_provider(media_key_refs)
    query = RuntimeQueryService(
        store, demo, memory_engine, runtime.mcp_manager, operator_control,
        pi_active_attempts=pi_active_attempts,
        media_registry=media_registry,
        media_config_error=media_config_error,
    )

    token = secrets.token_hex(32)
    tf = Path(token_file)
    tf.parent.mkdir(parents=True, exist_ok=True)
    tf.write_text(token)
    os.chmod(tf, 0o600)
    persisted_token = tf.read_text(encoding="utf-8").strip()
    if not secrets.compare_digest(persisted_token, token):
        raise RuntimeError("CAPT runtime token read-back verification failed")
    token = persisted_token

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
                try:
                    store.record_security_rejection(
                        rejection_id="rej-" + secrets.token_hex(8),
                        rejection_kind="unauthenticated_ipc_attempt",
                        details={"reason": "invalid_or_missing_session_token"},
                    )
                except Exception:
                    # Audit failure must not convert a denial into admission.
                    pass
                _send_json(conn, {"ok": False, "error": "unauthenticated"})
                return
            # Bind operator identity to this authenticated connection.
            # Single-user macOS desktop: the operator is the local user. The
            # session token authenticates the connection; the operator/session
            # binding prevents the desktop from spoofing another operator or
            # reusing a stale session's authority (Phase 3).
            operator_id = "operator-" + (getpass.getuser() or "local")
            session_id = "sess-" + secrets.token_hex(8)
            cmd_svc = runtime.command_service(
                operator_id, session_id, prompt_compiler=prompt_compiler,
                operator_control=operator_control,
            )
            cmd_svc.pi_active_attempts = pi_active_attempts
            cmd_svc.media_registry = media_registry
            cmd_svc.media_credential_resolver = media_credential_resolver
            provider_governor = _build_provider_governor(store)
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
            def _prepare_approved_hermes(command: Dict[str, Any]) -> PreparedApprovedModelExecution:
                """Validate and freeze every deterministic dispatch input."""
                payload = command.get("payload", {})
                objective = str(payload.get("objective", "")).strip()
                raw_target_root = payload.get("targetRoot")
                if not objective or not raw_target_root:
                    raise ValueError("MODEL_TASK_OBJECTIVE_OR_TARGET_MISSING")
                target_root = canonical_execution_target_root(raw_target_root)
                # All deterministic execution inputs are frozen before CAPT consumes
                # the one-use approval. Authored skill bytes are independently
                # re-verified here, then carried in the immutable prepared object;
                # dispatch never re-reads the skill checkout.
                command_id = command["commandId"]
                # P0.1: authority is consumed at authoritative runtime time, never at a
                # command-carried timestamp. A command-carried timestamp that is missing,
                # malformed, or skewed beyond the bound is evidence of tampering or
                # clock failure: fail closed. The command timestamp is retained as
                # provenance evidence (timingEvidence) only.
                command_issued_at = command.get("timestamp")
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                _check_command_timestamp_skew(command_issued_at, now)
                mission_id = payload.get("missionId") or ("m-model-" + command_id)
                task_id = payload.get("taskId") or (mission_id + "-task-1")
                run_id = payload.get("driverRunId") or ("dr-model-" + command_id)
                grant_id = payload.get("grantId") or ("g-model-" + command_id)
                lease_id = payload.get("leaseId") or ("l-model-" + command_id)
                claim_id = payload.get("claimId") or ("cl-model-" + command_id)
                policy_id = payload.get("policyDecisionId") or ("pd-model-" + command_id)
                executable = payload.get("executable") or None
                provider_id = payload.get("provider")
                provider_model = payload.get("model")
                try:
                    reasoning_effort = normalize_reasoning_effort(payload.get("reasoningEffort"))
                except ReasoningConfigurationError as exc:
                    raise ValueError(str(exc)) from exc
                if reasoning_effort and not provider_id:
                    raise ValueError("REASONING_EFFORT_REQUIRES_PROVIDER")
                try:
                    cohort_spec = normalize_cohort_spec(payload.get("cohortSpec"))
                except ValueError as exc:
                    raise ValueError(str(exc)) from exc
                bound_objective = compile_cohort_objective(
                    str(objective), provider=str(provider_id or ""),
                    model=str(provider_model or ""), cohort_spec=cohort_spec,
                )
                provider = None
                provider_key = ""
                if provider_id:
                    from capt_ui.operator.providers import ProviderManager
                    provider = ProviderManager(Path(ledger_path).parent / "ui").get(str(provider_id))
                    if provider is None or not provider_model:
                        raise ValueError("PROVIDER_OR_MODEL_UNAVAILABLE")
                skill_context, skill_names = prepare_runtime_skill_context(
                    payload, state_root=Path(ledger_path).parent
                )
                requested_context_budget = int(payload.get("requestedContextBudget", 32_000))
                effective_budget = effective_context_budget(
                    requested_context_budget, provider.context_limit if provider is not None else 0)
                response_mode = str(payload.get("responseMode", "SPOCK"))
                enhancement_engine = str(payload.get("promptEnhancement", "OFF"))
                human_verification_required = bool(payload.get("humanVerificationRequired", True))
                # Recover proposal identity only from authoritative approval state.
                approval_request_id = payload.get("approvalRequestId")
                if not approval_request_id:
                    raise AuthorityViolation("MODEL_PROMPT_APPROVAL_RECEIPT_REQUIRED")
                approval_state = store.require_state(
                    "human_approval-" + str(approval_request_id)
                )
                approval_scope = approval_state.get("scope") or {}
                approval_binding = approval_scope.get("approvalBinding") or {}

                # Replay the approval-time continuation snapshot. Sequential
                # cohorts may complete between approval and execution; selecting
                # from the live ledger here would mutate the model-visible prompt
                # after the human approved its digest.
                from capt_runtime.continuation_context import (
                    resolve_approved_continuation_context,
                )
                ledger_dir = str(Path(ledger_path).parent)
                try:
                    continuation = resolve_approved_continuation_context(
                        store,
                        str(mission_id),
                        str(task_id),
                        approval_binding=approval_binding,
                        exclude_run_id=str(run_id),
                        ledger_dir=ledger_dir,
                    )
                except ValueError as exc:
                    raise AuthorityViolation(str(exc)) from exc
                context_pack_digest = continuation["contextPackDigest"]
                requested_execution_seconds = int(
                    approval_binding.get("requestedExecutionSeconds", 600)
                )
                if requested_execution_seconds < 60 or requested_execution_seconds > 3600:
                    raise AuthorityViolation("MODEL_EXECUTION_SECONDS_OUT_OF_RANGE")
                frozen_authority = approval_binding.get("authorityProfile")
                authority_profile = (
                    revalidate_normalized_model_authority(
                        frozen_authority, target_root=str(target_root)
                    )
                    if frozen_authority is not None
                    else normalize_model_authority(None, target_root=str(target_root))
                )
                proposal_binding = authoritative_proposal_binding_for_execution(
                    store, str(approval_request_id), str(objective)
                )
                if provider is not None:
                    assert_provider_network_allowed(authority_profile, provider.base_url)
                    from capt_ui.operator.secrets import resolve
                    provider_key = resolve(provider.id, provider.key_ref)
                    if credential_required(provider.id, provider.kind, provider.base_url) and not provider_key:
                        raise ValueError("PROVIDER_CREDENTIAL_UNAVAILABLE")
                prompt_assembly = build_prompt_assembly(
                    human_prompt=bound_objective, response_mode=response_mode,
                    enhancement_engine=enhancement_engine,
                    context_pack_digest=context_pack_digest,
                    tool_schema_digest=contracts.digest({"operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"]}),
                    continuation_context=continuation["records"],
                    authored_skill_context=skill_context,
                )
                # Runtime authority binds human approval to the exact
                # model-visible assembly. Client booleans are provenance only;
                # no client can use OFF/no-transform as a governance bypass.
                bound_assembly = build_bound_model_operator_approval(
                    human_prompt=bound_objective, response_mode=response_mode,
                    enhancement_engine=enhancement_engine, mission_id=str(mission_id),
                    task_id=str(task_id), driver_run_id=str(run_id), target_root=str(target_root),
                    provider=str(provider_id or ""), model=str(provider_model or ""),
                    requested_context_budget=requested_context_budget,
                    requested_execution_seconds=requested_execution_seconds,
                    human_verification_required=human_verification_required,
                    executable=str(executable or ""),
                    reasoning_effort=reasoning_effort,
                    staging_root=staging_root_for_ledger(store.path, str(run_id)),
                    context_pack_digest=context_pack_digest,
                    continuation_context=continuation["records"],
                    authored_skill_context=skill_context,
                    proposal_binding=proposal_binding,
                    authority_profile=authority_profile,
                    cohort_spec=cohort_spec,
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
                        "reasoningEffort": reasoning_effort,
                        "requestedExecutionSeconds": requested_execution_seconds,
                        "cohortSpec": cohort_spec,
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
                        "authorityProfile": authority_profile,
                        "approvalExpiresAt": str(approval_state["expiresAt"]),
                        "timingEvidence": {
                            "commandIssuedAt": command_issued_at,
                            "authorityConsumedAt": now,
                            "timestampSkewBoundSeconds": _COMMAND_TIMESTAMP_SKEW_BOUND_SECONDS,
                        },
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
                    provider = ProviderManager(Path(ledger_path).parent / "ui").get(provider_id)
                    if provider is None or not provider_model:
                        raise ValueError("PROVIDER_OR_MODEL_UNAVAILABLE")
                requested_context_budget = prepared.data["requestedContextBudget"]
                requested_execution_seconds = prepared.data["requestedExecutionSeconds"]
                reasoning_effort = str(prepared.data.get("reasoningEffort") or "")
                effective_budget = prepared.data["effectiveBudget"]
                human_verification_required = prepared.data["humanVerificationRequired"]
                cohort_spec = (
                    dict(prepared.data.get("cohortSpec"))
                    if prepared.data.get("cohortSpec") else None
                )
                output_modality = str((cohort_spec or {}).get("outputModality") or "text")
                output_format = str((cohort_spec or {}).get("outputFormat") or "")
                if not reasoning_effort:
                    reasoning_effort = legacy_cohort_configuration_reasoning_effort(
                        (cohort_spec or {}).get("configurationId")
                    )
                prompt_assembly = prepared.data["promptAssembly"]
                dispatch_prompt = prepared.data["dispatchPrompt"]
                skill_context = (
                    json.loads(json.dumps(prepared.data["authoredSkillContext"]))
                    if prepared.data.get("authoredSkillContext") else None
                )
                skill_names = list(prepared.data.get("skillNames") or ())
                authority_profile = revalidate_normalized_model_authority(
                    dict(prepared.data["authorityProfile"]), target_root=str(target_root)
                )
                if provider is not None:
                    assert_provider_network_allowed(authority_profile, provider.base_url)
                    from capt_ui.operator.secrets import resolve
                    provider_key = resolve(provider.id, provider.key_ref)
                    if credential_required(provider.id, provider.kind, provider.base_url) and not provider_key:
                        raise ValueError("PROVIDER_CREDENTIAL_UNAVAILABLE")
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
                approved_tool_root = str(authority_profile["filesystemRoot"])
                intent = {
                    "schemaVersion": "1.0.0",
                    "missionId": mission_id,
                    "objective": task_title,
                    "scope": {"kind": "filesystem", "rootPath": approved_tool_root, "recursive": True},
                    "requiresApproval": False,
                    "constraints": [{"kind": "resource_boundary", "constraintId": "con-model-1",
                                     "origin": "explicit_user",
                                     "scope": {"kind": "filesystem", "rootPath": approved_tool_root, "recursive": True}}],
                    "successCriteria": [{"criterionId": "sc-model-1",
                                         "statement": "Model task completed with evidence-backed observations.",
                                         "requiresVerification": True}],
                    "terminationCriteria": [{"criterionId": "tc-model-1",
                                             "statement": "Invariant violation terminates the mission.",
                                             "terminalState": "failed"}],
                    "requestedCapability": (
                        "cap.model.tools"
                        if authority_profile["riskClassification"] == "consequential"
                        else "cap.fs.read"
                    ),
                    "resource": target_root,
                    "operation": "ModelOperatorInspection",
                    "riskClassification": authority_profile["riskClassification"],
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
                    "maxUses": 1, "validFrom": now, "validUntil": str(prepared.data["approvalExpiresAt"]),
                    "issuedBy": {"actorId": "gk-1", "kind": "governance_kernel"}, "issuedAt": now,
                }
                svc.issue_grant(grant, gk_meta("issue_grant"))
                lease = {
                    "schemaVersion": "1.0.0", "leaseId": lease_id, "grantId": grant_id,
                    "missionId": mission_id, "taskId": task_id,
                    "executionContextId": "ec-model-" + command_id,
                    "operations": ["repository.read", "filesystem.read", "artifact.create", "analysis.execute"],
                    "scope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
                    "maxUses": 1, "validFrom": now, "validUntil": str(prepared.data["approvalExpiresAt"]),
                    "activatedAt": now,
                }
                svc.activate_lease(lease, gk_meta("activate_lease"))
                dispatch_lease = dict(lease)
                dispatch_lease["scope"] = {**lease["scope"], "allowedPaths": [target_root]}

                # A provider model receives a distinct phase-scoped ToolBroker
                # lease derived only from the already-approved authority profile.
                # This is intentionally separate from the one-use driver lease
                # governing the external model dispatch itself.
                tool_authority = None
                if provider is not None and output_modality == "text":
                    tool_authority = issue_model_tool_authority(
                        service=svc,
                        broker=runtime.tool_broker,
                        authority_profile=authority_profile,
                        target_root=str(target_root),
                        mission_id=str(mission_id),
                        task_id=str(task_id),
                        driver_run_id=str(run_id),
                        operator_id=cmd_svc.operator_id,
                        session_id=cmd_svc.session_id,
                        issued_at=str(now),
                        valid_until=str(prepared.data["approvalExpiresAt"]),
                        metadata_factory=gk_meta,
                        now=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    )
                # 3. DriverHost dispatch with the resolved authoritative task.
                # Authored skill bytes were verified and frozen in `prepare`, before
                # approval consumption. Binding them here does not re-read disk.
                worktree = Path(target_root)
                staging = Path(staging_root_for_ledger(store.path, str(run_id)))
                staging.mkdir(parents=True, exist_ok=True)
                # P0.3: crash-consistent dispatch-boundary recorder. The
                # provider driver invokes this BEFORE crossing each
                # irreversible external boundary (request_started before
                # urlopen, response_started after headers, response_completed
                # after the body, result_persisted after the artifact write).
                # A recording failure propagates out of the driver and aborts
                # dispatch: the run must not cross a boundary its durable
                # record does not show (fail closed).
                # P0.3: every boundary record carries a fresh monotonic sequence so
                # a tool-call loop that legitimately re-opens request_started (or
                # any other recurring boundary) appends a DISTINCT durable event.
                # Reusing one idempotency key per boundary name would make the
                # store return the first round's receipt as a duplicate and leave
                # the durable boundary understated in the unsafe direction.
                _boundary_seq = {"n": 0}
                def _record_dispatch_boundary(driver_run_id: str, boundary: str) -> None:
                    _boundary_seq["n"] += 1
                    seq = _boundary_seq["n"]
                    record_id = "%s:dispatch-boundary:%03d:%s" % (command_id, seq, boundary)
                    boundary_meta = commands.command(
                        command_id=record_id,
                        idempotency_key="%s:dispatch-boundary:%03d:%s" % (key, seq, boundary),
                        operation_fingerprint=commands.fingerprint(
                            "record_driver_dispatch_boundary",
                            {"driverRunId": driver_run_id, "dispatchBoundary": boundary,
                             "sequence": seq},
                        ),
                        correlation_id=correlation_id,
                        actor_id="exec-1",
                        actor_kind="execution_plane",
                        issued_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        replay_policy="never",
                    )
                    svc.record_driver_dispatch_boundary(driver_run_id, boundary, boundary_meta)

                if provider is not None:
                    host = runtime.provider_host(
                        target_repo=str(worktree), staging_root=str(staging),
                        provider_id=provider.id, model=str(provider_model),
                        base_url=provider.base_url, api_key=provider_key,
                        dispatch_prompt=str(dispatch_prompt),
                        output_modality=output_modality,
                        output_format=output_format,
                        reasoning_effort=reasoning_effort,
                        cohort_spec=cohort_spec,
                        governor=provider_governor,
                        tool_bridge=tool_authority.bridge if tool_authority is not None else None,
                        boundary_recorder=_record_dispatch_boundary,
                    )
                else:
                    host = runtime.hermes_host(
                        target_repo=str(worktree), staging_root=str(staging),
                        executable=executable, enforce_memory=False,
                        dispatch_prompt=str(dispatch_prompt),
                    )
                if skill_context is not None:
                    host.bind_prepared_authored_skills(skill_context, skill_names)
                driver_budgets = {
                    "maxSeconds": requested_execution_seconds,
                    "maxArtifacts": 1,
                    "maxObservations": 10,
                }
                if isinstance(effective_budget, int) and not isinstance(effective_budget, bool) and effective_budget > 0:
                    driver_budgets["maxTokens"] = effective_budget
                ctx = host.build_context(
                    {"leaseId": lease["leaseId"], "operations": lease["operations"],
                     "scope": lease["scope"], "validFrom": lease["validFrom"],
                     "validUntil": lease["validUntil"]},
                    ["terminal"], driver_budgets,
                    [{"artifactPath": str(staging / "model-analysis.md"), "artifactKind": "report"}],
                    {"onUnexpectedWrite": "fail"},
                    skill_names=skill_names or None,
                )
                wo = {
                    "schemaVersion": "1.0.0", "driverRunId": run_id, "driverId": "provider" if provider is not None else "hermes",
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
                    try:
                        out = host.dispatch(
                            wo, ctx, {"state": "running"}, now=now, lease=dispatch_lease
                        )
                    finally:
                        # Phase-Fenced Capability Consumption: whether provider
                        # dispatch returns or raises, model tool authority closes
                        # before any normal completion can be recorded.
                        if tool_authority is not None:
                            revoke_model_tool_authority(
                                service=svc,
                                grant_id=tool_authority.grant_id,
                                issued_at=now,
                                reason="provider tool phase closed",
                                metadata=gk_meta("revoke_model_tools"),
                            )
                except Exception as exc:
                    # Durable, bounded diagnostic BEFORE the indeterminate-state
                    # transition. Never write raw exception strings, prompts,
                    # provider bodies, credentials, or tool responses.
                    from capt_runtime.diagnostic_receipts import safe_provider_failure
                    observed_run = store.load_state("driverrun-" + str(run_id)) or {}
                    diagnostic = safe_provider_failure(
                        exc, driver_run_id=str(run_id),
                        provider=str(provider_id or "local"),
                        model=str(provider_model or ""),
                        dispatch_boundary=str(observed_run.get("dispatchBoundary") or "unknown"),
                        request_attempts=observed_run.get("providerHttpRequestAttempts"),
                    )
                    try:
                        store.store_provider_failure_diagnostic(str(run_id), diagnostic)
                    except Exception:
                        # Failure of a diagnostic projection must not erase the
                        # original exception or grant a second external attempt.
                        pass
                    # Dispatch reached an external boundary after reservation. The
                    # absence of a result is not proof that no side effect occurred:
                    # consume indeterminately and require recovery rather than retry.
                    consumption = {
                        "schemaVersion": "1.0.0", "consumptionId": "con-" + command_id,
                        "reservationId": reservation_id, "leaseId": lease_id,
                        "outcome": "indeterminate", "sideEffectIdentity": run_id, "finalizedAt": now,
                    }
                    svc.finalize_use(grant_id, consumption, exec_meta("finalize-indeterminate"))
                    # A dispatch or phase-closure exception after the boundary is
                    # not evidence of failure. Preserve the unknown as lost +
                    # suspended so governed reconciliation, not retry, decides it.
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
                cohort_validation = validate_vessel_artifact(artifact_path, cohort_spec)
                charter_failed = bool(
                    cohort_validation.get("required") and not cohort_validation.get("valid")
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
                accepted = guard_claim(
                    "Provider response and immutable artifact recorded for independent verification."
                )
                claim_record = {
                    "schemaVersion": "1.0.0", "claimId": claim_id, "missionId": mission_id,
                    "taskId": task_id,
                    "kind": "observation" if charter_failed else "completion",
                    "statement": accepted,
                    "evidenceIds": [baseline_ev_id, result_ev_id], "promotionState": "proposed",
                    "proposedBy": {"actorId": "cog-1", "kind": "cognitive_plane"},
                    "proposedAt": now, "sourceProposalId": None,
                }
                claim_meta = commands.command(
                    command_id=command_id + ":claim", idempotency_key=key + ":claim",
                    operation_fingerprint=commands.fingerprint("propose_claim", {"claimId": claim_id}),
                    correlation_id=correlation_id,
                    actor_id="cog-1", actor_kind="cognitive_plane",
                    issued_at=now, replay_policy="never",
                )
                svc.propose_claim_with_evidence(
                    claim_record,
                    [
                        (baseline_evidence, evidence_meta("evidence-baseline", baseline_ev_id)),
                        (result_evidence, evidence_meta("evidence-result", result_ev_id)),
                    ],
                    claim_meta,
                )
                _test_fault("evidence_recorded")
                # A provider response and its immutable artifact are evidence, not
                # verification.  Keep the claim proposed and the task in the
                # aggregate's existing awaiting_verification state; a later
                # verification/ClaimGuard authority must perform any promotion.
                if charter_failed:
                    svc.transition_task(
                        task_id, "failed",
                        "approval-bound Vessel Charter ledger incomplete",
                        exec_meta("taskcohortinvalid"),
                    )
                else:
                    svc.transition_task(
                        task_id, "awaiting_verification",
                        "provider response recorded; independent verification required",
                        exec_meta("taskawaitingverification"),
                    )
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
                    "observations": out.get("observations", []),
                    "driver": "provider" if provider is not None else "hermes",
                    "providerProvenance": out.get("diagnostics", {}) if provider is not None else {},
                    "cognitiveProvenance": cognitive_provenance,
                    "authoredSkills": summarize_skill_context(ctx.get("skillContext")),
                    "cohortValidation": cohort_validation,
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
            srv.close()
        except OSError:
            pass
        try:
            sock_path.unlink()
        except OSError:
            pass
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lock_handle.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--sock", required=True)
    ap.add_argument("--token-file", required=True)
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--enable-biocapt-qipc", action="store_true")
    ap.add_argument("--biocapt-qipc-source-root")
    ap.add_argument("--biocapt-qipc-interpreter")
    args = ap.parse_args()
    serve(
        args.ledger, args.sock, args.token_file, args.seed,
        enable_biocapt_qipc=args.enable_biocapt_qipc,
        biocapt_qipc_source_root=args.biocapt_qipc_source_root,
        biocapt_qipc_interpreter=args.biocapt_qipc_interpreter,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
