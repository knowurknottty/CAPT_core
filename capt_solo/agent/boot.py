"""CAPT Agent Runner — fail-closed boot pipeline (BOOT_CONTRACT, ADR-0001).

Boot is an ORCHESTRATION layer over canonical CAPT facilities. It does not
construct a second memory engine, checkpoint system, ContextPack implementation,
gate, or runtime — it composes the single composition root
(:class:`capt_solo.runtime.CAPTRuntime`, injected) and the durable mission store
(:class:`capt_solo.evidence.CheckpointStore`). The MemoryUseGate check here is
the exact ``MemoryUseGate.prepare`` that ``CAPTRuntime.execute_model_task``
enforces before any provider invocation; no provider is reachable from this
module.

Authority is CAPT state + repository evidence, never the transcript. Any
mandatory failure yields ``execution_mode == BLOCKED``; the runner must not
invoke a provider on BLOCKED. BOOTSTRAP_DEGRADED requires authorization recorded
in DURABLE state (a mission-checkpoint field), not inferred from the request.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from capt_solo.agent.contracts import (
    EXECUTION_MODE_BLOCKED,
    EXECUTION_MODE_BOOTSTRAP_DEGRADED,
    EXECUTION_MODE_GOVERNED,
    AgentBootRequest,
    AgentBootResult,
    AgentMemoryBootTrace,
    IntentRecord,
    OutputPolicy,
)
from capt_solo.contextpack import MissionIntent, RecordRef
from capt_solo.evidence import CheckpointStore, MissionCheckpoint, detect_divergence
from capt_solo.runtime import CAPTRuntime, GateDecision

# Compatible checkpoint schema markers. The MissionCheckpoint dataclass is v1
# (no explicit schema_version field); a future field can gate this.
_SUPERSESSION_MARKERS = ("supersede", "superseded", "corrected to", "rejected", "overstated")
_DEGRADED_AUTH_MARKER = "BOOTSTRAP_DEGRADED_AUTHORIZED"


# ---------------------------------------------------------------------------
# workspace identity
# ---------------------------------------------------------------------------
def _git(workspace: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(workspace), *args],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def resolve_workspace(workspace_path: str) -> Tuple[Path, str, str]:
    """Return (resolved_path, git_sha, git_branch). SHA/branch '' outside git."""
    path = Path(workspace_path).resolve()
    return path, _git(path, "rev-parse", "HEAD"), _git(path, "rev-parse", "--abbrev-ref", "HEAD")


def _digest(payload: Dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# mission resolution — evidence-backed precedence, no newest-wins guessing
# ---------------------------------------------------------------------------
def resolve_mission(
    store: CheckpointStore,
    *,
    requested_mission_id: Optional[str],
    session_bound_mission_id: Optional[str],
) -> Tuple[Optional[MissionCheckpoint], List[str], str, str]:
    """Resolve the active mission checkpoint by explicit precedence.

    Precedence (BOOT_CONTRACT / directive):
      1. Explicit mission id in the request.
      2. Mission binding recovered from the applicable session checkpoint.
      3. Canonical active-mission discovery: exactly ONE non-completed mission.
      4. Otherwise BLOCKED (ambiguous or missing) — never guess by recency.

    Returns (checkpoint, all_ids, resolved_id, selector) where ``selector`` names
    which precedence rule fired ("explicit" / "session" / "discovery" /
    "ambiguous" / "missing").
    """
    ids = store.list_ids()
    if requested_mission_id:
        return store.load(requested_mission_id), ids, requested_mission_id, "explicit"
    if session_bound_mission_id:
        return store.load(session_bound_mission_id), ids, session_bound_mission_id, "session"
    active: List[MissionCheckpoint] = []
    for mid in ids:
        cp = store.load(mid)
        if cp is not None and cp.status not in ("completed",):
            active.append(cp)
    if len(active) == 1:
        return active[0], ids, active[0].mission_id, "discovery"
    if not active:
        return None, ids, "", "missing"
    return None, ids, "", "ambiguous"


# ---------------------------------------------------------------------------
# directive resolution + explicit supersession (STATE_AUTHORITY)
# ---------------------------------------------------------------------------
def resolve_directives(cp: MissionCheckpoint) -> Tuple[List[str], List[str]]:
    active, superseded = [], []
    for d in cp.decisions_made:
        low = d.lower()
        (superseded if any(k in low for k in _SUPERSESSION_MARKERS) else active).append(d)
    return active, superseded


# ---------------------------------------------------------------------------
# checkpoint validation
# ---------------------------------------------------------------------------
def validate_checkpoint(
    cp: MissionCheckpoint,
    *,
    resolved_mission_id: str,
    workspace: Path,
    git_sha: str,
    git_branch: str,
) -> Tuple[bool, str, str, Dict[str, str]]:
    """Validate a checkpoint before use.

    Checks mission identity, digest/integrity, workspace/project identity, and
    required state fields. Returns (ok, code, reason, divergence).
    """
    # mission identity
    if cp.mission_id != resolved_mission_id:
        return False, "MISSION_IDENTITY", (
            f"checkpoint mission {cp.mission_id} != resolved {resolved_mission_id}"
        ), {}
    # digest / integrity
    payload = cp.to_dict().copy()
    recorded = payload.pop("event_digest", "")
    expected = CheckpointStore._digest(payload)
    if recorded and recorded != expected:
        return False, "CHECKPOINT_INTEGRITY", (
            f"checkpoint {cp.mission_id} digest mismatch"
        ), {}
    # workspace / project identity: the checkpoint's project must match the
    # workspace directory name (foreign-workspace rejection).
    if cp.project_id and cp.project_id != workspace.name:
        return False, "FOREIGN_WORKSPACE", (
            f"checkpoint project_id {cp.project_id!r} != workspace {workspace.name!r}"
        ), {}
    # required state fields
    if not cp.objective:
        return False, "CHECKPOINT_INCOMPLETE", "checkpoint missing objective", {}
    # divergence vs current repo (stale detection; not fatal by itself)
    divergence: Dict[str, str] = {}
    if git_sha:
        divergence = detect_divergence(
            cp, current_head=git_sha, current_branch=git_branch,
            current_files=_tracked_and_changed_files(workspace),
        )
    return True, "", "", divergence


# ---------------------------------------------------------------------------
# boot pipeline
# ---------------------------------------------------------------------------
def boot(
    request: AgentBootRequest,
    *,
    runtime: CAPTRuntime,
    session_bound_mission_id: Optional[str] = None,
    objective_override: Optional[str] = None,
) -> AgentBootResult:
    """Run the fail-closed boot pipeline. ``runtime`` is the single injected root."""
    agent_run_id = "agentrun-" + uuid.uuid4().hex[:16]
    policy = OutputPolicy.for_mode(request.output_mode)
    workspace, sha, branch = resolve_workspace(request.workspace_path)

    def _blocked(reason: str, codes: Tuple[str, ...], mission_id: str = "") -> AgentBootResult:
        _safe_publish(runtime, "agent.boot.failed", {
            "agent_run_id": agent_run_id, "mission_id": mission_id or (request.mission_id or ""),
            "reason": reason, "block_codes": list(codes), "git_sha": sha,
        })
        return AgentBootResult(
            execution_mode=EXECUTION_MODE_BLOCKED, workspace_path=str(workspace),
            git_sha=sha, git_branch=branch, mission_id=mission_id or (request.mission_id or ""),
            session_id=request.session_id or "", checkpoint_id="", active_directive_ids=(),
            output_policy=policy, gate_result="BLOCKED", block_reason=reason, block_codes=codes,
        )

    _safe_publish(runtime, "agent.boot.requested", {
        "agent_run_id": agent_run_id, "mission_id": request.mission_id or "", "git_sha": sha,
    })

    # 1. workspace identity mandatory
    if not workspace.exists():
        return _blocked(f"workspace path does not exist: {workspace}", ("WORKSPACE_MISSING",))

    # 2. mission resolution (from store; explicit > session-bound > discovery)
    store = CheckpointStore(str(workspace), create=False)
    cp, all_ids, resolved_mid, selector = resolve_mission(
        store, requested_mission_id=request.mission_id,
        session_bound_mission_id=session_bound_mission_id,
    )
    if selector == "ambiguous":
        return _blocked(
            f"mission ambiguous; candidates={all_ids}; no canonical selector. Specify --mission.",
            ("MISSION_AMBIGUOUS",),
        )
    if cp is None:
        if request.mission_id or session_bound_mission_id:
            return _blocked(
                f"mission not found in store: {resolved_mid or request.mission_id}",
                ("MISSION_NOT_FOUND",), resolved_mid,
            )
        return _blocked(
            f"no active mission in store; candidates={all_ids}.", ("MISSION_MISSING",),
        )

    # 3. checkpoint validation (identity/integrity/workspace/required fields)
    ok, code, reason, divergence = validate_checkpoint(
        cp, resolved_mission_id=cp.mission_id, workspace=workspace,
        git_sha=sha, git_branch=branch,
    )
    if not ok:
        return _blocked(reason, (code,), cp.mission_id)
    checkpoint_id = f"{cp.mission_id}@{cp.current_phase}"

    # 4. session (reuse or create)
    session_id = request.session_id or runtime.lifecycle.sessions.begin(
        request.namespace, objective=cp.objective
    )

    # 5-6. directives + supersession
    active_directives, superseded = resolve_directives(cp)

    # 7. mint bounded Intent from recovered state (Intent is first-class here)
    objective = objective_override or cp.next_safe_action or cp.objective
    intent = IntentRecord.mint(
        mission_id=cp.mission_id, session_id=session_id,
        turn_id=f"{agent_run_id}:boot", requested_goal=cp.objective,
        current_goal=objective, owner_constraints=tuple(cp.constraints),
        completion_criteria=tuple(cp.acceptance_criteria), output_policy=policy,
    )

    # 8-10. selection classification + ContextPack + MemoryUseGate (mandatory)
    evidence_refs, rendered = _boot_evidence(cp, sha, branch, objective, divergence)
    mission_intent = MissionIntent(
        purpose=objective, priority="critical",
        tradeoffs=("governance strictness", "speed"),
        success_definition="boot completes with a validated ContextPack and a passed MemoryUseGate",
        safety_constraints=("no model invocation before gate PASS", "no transcript fallback"),
    )
    records = {
        "selected": f"mission={cp.mission_id} phase={cp.current_phase} head={(cp.latest_verified_state or sha)[:12]} selector={selector}",
        "rejected": "; ".join(superseded)[:400] or "none",
        "stale": "; ".join(f"{k}:{v}" for k, v in divergence.items())[:400] or "none",
        "missing": "; ".join(cp.blockers)[:400] or "none",
        "conflicting": "; ".join(cp.unresolved_invalidations)[:400] or "none",
    }
    selection_ids = runtime.gate.record_selection(
        cp.mission_id, objective, records=records, namespace=request.namespace
    )
    _safe_publish(runtime, "agent.boot.memory_retrieved", {
        "agent_run_id": agent_run_id, "mission_id": cp.mission_id, "selection_ids": selection_ids,
    })
    decision: GateDecision = runtime.gate.prepare(
        cp.mission_id, objective, intent=mission_intent, assumptions=(),
        evidence=tuple(evidence_refs), invariants=(), rendered_context=rendered,
        namespace=request.namespace,
    )
    retrieved = decision.retrieved or {}

    def _ids(kind: str) -> Tuple[str, ...]:
        return tuple(m.memory_id for m in retrieved.get(kind, []))

    cp_digest = decision.pack.digest if decision.pack else ""
    gate_pass = bool(decision.allowed)

    # BOOTSTRAP_DEGRADED requires authorization in DURABLE state, not the request
    durably_authorized = _degraded_authorized(cp)
    if not gate_pass:
        execution_mode = (
            EXECUTION_MODE_BOOTSTRAP_DEGRADED if durably_authorized else EXECUTION_MODE_BLOCKED
        )
        gate_result = "DEGRADED" if durably_authorized else "BLOCKED"
    else:
        execution_mode = EXECUTION_MODE_GOVERNED
        gate_result = "PASS"

    next_action = cp.next_safe_action or "resolve next mission action"
    trace = AgentMemoryBootTrace(
        agent_run_id=agent_run_id, mission_id=cp.mission_id, session_id=session_id,
        checkpoint_id=checkpoint_id, workspace_path=str(workspace), git_branch=branch,
        git_sha=sha, active_directive_ids=tuple(active_directives),
        superseded_directive_ids=tuple(superseded), selected_memory_ids=_ids("selected"),
        rejected_memory_ids=_ids("rejected"), stale_memory_ids=_ids("stale"),
        conflict_ids=_ids("conflicting"), missing_memory_ids=_ids("missing"),
        intent_id=intent.intent_id, intent_digest=intent.digest,
        contextpack_digest=cp_digest, memory_use_decision_id=(cp_digest[-16:] if cp_digest else ""),
        gate_result=gate_result, execution_mode=execution_mode, output_mode=policy.mode,
        next_justified_action=next_action,
    )
    trace, artifact_id = _persist_boot_trace(runtime, trace)

    if execution_mode == EXECUTION_MODE_BLOCKED:
        _safe_publish(runtime, "agent.boot.failed", {
            "agent_run_id": agent_run_id, "mission_id": cp.mission_id,
            "gate": "BLOCKED", "block_codes": list(decision.block_codes),
        })
        return _blocked_with_trace(
            workspace, sha, branch, cp.mission_id, session_id, checkpoint_id,
            active_directives, trace, policy, decision.block_codes,
            "MemoryUseGate did not PASS: " + ", ".join(decision.block_codes),
        )

    _safe_publish(runtime, "agent.boot.context_validated", {
        "agent_run_id": agent_run_id, "mission_id": cp.mission_id,
        "contextpack_digest": cp_digest, "gate": gate_result,
    })
    _safe_publish(runtime, "agent.boot.completed", {
        "agent_run_id": agent_run_id, "mission_id": cp.mission_id,
        "session_id": session_id, "execution_mode": execution_mode,
        "intent_id": intent.intent_id, "boot_artifact_id": artifact_id,
    })
    return AgentBootResult(
        execution_mode=execution_mode, workspace_path=str(workspace), git_sha=sha,
        git_branch=branch, mission_id=cp.mission_id, session_id=session_id,
        checkpoint_id=checkpoint_id, active_directive_ids=tuple(active_directives),
        boot_trace=trace, output_policy=policy, gate_result=gate_result,
        block_reason=("" if gate_pass else "gate did not PASS; degraded authorized in durable state"),
        block_codes=(() if gate_pass else tuple(decision.block_codes)),
        degraded_missing_controls=(() if gate_pass else ("memory_use_gate_pass",)),
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _safe_publish(runtime: CAPTRuntime, topic: str, payload: Dict[str, Any]) -> None:
    try:
        runtime.bus.publish(topic, payload)
    except Exception:
        pass


def _degraded_authorized(cp: MissionCheckpoint) -> bool:
    """True only when durable checkpoint state explicitly authorizes degraded mode."""
    hay = " ".join(cp.decisions_made + cp.required_user_decisions + [cp.next_safe_action])
    return _DEGRADED_AUTH_MARKER in hay


def _tracked_and_changed_files(workspace: Path) -> List[str]:
    files = set()
    tracked = _git(workspace, "ls-files")
    if tracked:
        files.update(tracked.splitlines())
    for line in _git(workspace, "status", "--porcelain").splitlines():
        name = line[3:].strip() if len(line) > 3 else line.strip()
        if name:
            files.add(name)
    return sorted(files)


def _boot_evidence(
    cp: MissionCheckpoint, sha: str, branch: str, objective: str, divergence: Dict[str, str],
) -> Tuple[List[RecordRef], str]:
    """Build boot ContextPack evidence + rendered context.

    Protected facts derived from evidence (mission id, phase, head, branch) MUST
    appear in ``rendered`` or the gate fidelity check BLOCKs — the runtime
    proving the recovered state is actually carried into the request.
    """
    head12 = (cp.latest_verified_state or sha)[:12]
    embedded = {
        "mission_id": cp.mission_id, "phase": cp.current_phase,
        "head": head12, "branch": branch or "unknown",
    }
    ref = RecordRef("evidence:boot-state", _digest(embedded).split(":", 1)[1], "capt-agent-boot", embedded)
    rendered = (
        f"MISSION {cp.mission_id} phase={cp.current_phase} head={head12} "
        f"branch={branch or 'unknown'} objective={objective} | "
        f"{json.dumps(embedded, sort_keys=True)}"
    )
    if divergence:
        rendered += " | divergence=" + json.dumps(divergence, sort_keys=True)
    return [ref], rendered


def _persist_boot_trace(
    runtime: CAPTRuntime, trace: AgentMemoryBootTrace,
) -> Tuple[AgentMemoryBootTrace, str]:
    """Persist the boot trace as an evidence artifact; return (trace_with_hash, id).

    Uses the runtime's evidence dir; hashes the trace content (excluding the
    hash field). Records the artifact hash as proof evidence bound to the run.
    """
    import dataclasses

    body = json.dumps(trace.digest_dict(), indent=2, sort_keys=True, default=str)
    artifact_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    trace = dataclasses.replace(trace, artifact_hash=f"sha256:{artifact_hash}")
    try:
        base = runtime.config.evidence_dir or (Path.home() / ".capt" / "evidence")
        d = Path(base) / "agent-boot"
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = d / f"{trace.agent_run_id}.json"
        path.write_text(
            json.dumps(trace.to_dict(), indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
        path.with_suffix(".json.sha256").write_text(
            f"sha256:{artifact_hash}  {path.name}\n", encoding="utf-8"
        )
        runtime.proof.record(
            "artifact_hash", f"agent-boot:{trace.agent_run_id}", artifact_hash,
            "capt agent boot trace", scope=trace.mission_id,
        )
    except Exception:
        pass
    return trace, f"agent-boot:{trace.agent_run_id}"


def _blocked_with_trace(
    workspace: Path, sha: str, branch: str, mission_id: str, session_id: str,
    checkpoint_id: str, active_directives: List[str], trace: AgentMemoryBootTrace,
    policy: OutputPolicy, block_codes: Any, reason: str,
) -> AgentBootResult:
    return AgentBootResult(
        execution_mode=EXECUTION_MODE_BLOCKED, workspace_path=str(workspace), git_sha=sha,
        git_branch=branch, mission_id=mission_id, session_id=session_id,
        checkpoint_id=checkpoint_id, active_directive_ids=tuple(active_directives),
        boot_trace=trace, output_policy=policy, gate_result="BLOCKED",
        block_reason=reason, block_codes=tuple(block_codes),
    )
