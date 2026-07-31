"""CAPT Agent Runner — data contracts (v1, frozen, versioned).

Design rules (ADR-0001, BOOT_CONTRACT, STATE_AUTHORITY):
  * Reuse repo types. Do NOT duplicate Mission/MissionIntent/Assumption/
    RecordRef/ProtectedFact/TokenBudget (contextpack/core.py),
    Checkpoint/RestartPacket (lifecycle/sessions.py), or ModelTaskRequest/
    ModelTaskResult/ModelIdentity (model_task.py). Those are the canonical
    shapes; the runner threads them, it does not re-declare them.
  * Everything here is a frozen dataclass with a schema_version so legacy
    records can be migrated by a reader rather than silently misread.

Intent is a FIRST-CLASS runtime object, distinct from memory and planning:
  * Not memory  — it is not retrieved/stored as semantic/episodic content; it
    is the bounded contract for the CURRENT execution, minted per turn.
  * Not planning — it does not enumerate steps; it declares the goal, owner
    constraints, allowed/prohibited scope, completion criteria, and the
    OutputPolicy that govern one execution.
  * It bounds what the runner is permitted to do this turn. The runner reads
    it; the provider never authors it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

AGENT_SCHEMA_VERSION = "capt.agent.v1"

# Execution modes (BOOT_CONTRACT). Default is BLOCKED on any mandatory failure.
EXECUTION_MODE_GOVERNED = "GOVERNED"
EXECUTION_MODE_BOOTSTRAP_DEGRADED = "BOOTSTRAP_DEGRADED"
EXECUTION_MODE_BLOCKED = "BLOCKED"

# OutputPolicy modes. CaveCAPT ("cave") is the runtime default: visible output
# is blockers, phase completion, and the final summary — no narration. Safety /
# blocker / gate-failure messages ALWAYS bypass caps (see output.py consumers).
OUTPUT_MODE_CAVE = "cave"
OUTPUT_MODE_NORMAL = "normal"
OUTPUT_MODE_VERBOSE = "verbose"
OUTPUT_MODE_SILENT = "silent"
OUTPUT_MODE_AUDIT = "audit"
OUTPUT_MODES = (
    OUTPUT_MODE_CAVE,
    OUTPUT_MODE_NORMAL,
    OUTPUT_MODE_VERBOSE,
    OUTPUT_MODE_SILENT,
    OUTPUT_MODE_AUDIT,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(payload: Dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# OutputPolicy — runtime-owned. The provider cannot decide verbosity.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OutputPolicy:
    """Runtime-owned rendering policy for a run/turn.

    ``mode`` is one of :data:`OUTPUT_MODES`. Regardless of mode, safety,
    blocker, and gate-failure messages bypass ``max_visible_chars`` — a cap
    must never truncate a blocker (BOOT_CONTRACT / ADR-0001).
    """

    mode: str = OUTPUT_MODE_CAVE
    show_blockers: bool = True
    show_phase_completion: bool = True
    show_final_summary: bool = True
    show_narration: bool = False
    max_visible_chars: int = 4000
    schema_version: str = AGENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.mode not in OUTPUT_MODES:
            raise ValueError(
                f"OutputPolicy.mode must be one of {OUTPUT_MODES}, got {self.mode!r}"
            )

    @classmethod
    def for_mode(cls, mode: str) -> "OutputPolicy":
        """Canonical policy per mode. CaveCAPT is the default."""
        mode = mode or OUTPUT_MODE_CAVE
        if mode == OUTPUT_MODE_CAVE:
            return cls(mode=mode, show_narration=False)
        if mode == OUTPUT_MODE_NORMAL:
            return cls(mode=mode, show_narration=False, max_visible_chars=8000)
        if mode == OUTPUT_MODE_VERBOSE:
            return cls(mode=mode, show_narration=True, max_visible_chars=32000)
        if mode == OUTPUT_MODE_SILENT:
            return cls(
                mode=mode,
                show_phase_completion=False,
                show_final_summary=False,
                show_narration=False,
                max_visible_chars=0,
            )
        if mode == OUTPUT_MODE_AUDIT:
            return cls(mode=mode, show_narration=True, max_visible_chars=1_000_000)
        raise ValueError(f"unknown output mode: {mode!r}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# IntentRecord — first-class bounded contract for the current execution.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class IntentRecord:
    """The bounded contract governing ONE execution (turn).

    Intent is neither memory nor planning: it is the authorization envelope for
    what the runner may do this turn — the goal, owner constraints, the scope it
    may and may not touch, the criteria that define completion, and the output
    policy. It is minted from CAPT state + the current-task input, carried into
    the governed model task, and persisted as part of the turn evidence.
    """

    intent_id: str

    mission_id: str
    session_id: str
    turn_id: str

    requested_goal: str
    current_goal: str

    owner_constraints: Tuple[str, ...] = ()

    allowed_scope: Tuple[str, ...] = ()
    prohibited_scope: Tuple[str, ...] = ()

    completion_criteria: Tuple[str, ...] = ()

    output_policy: OutputPolicy = field(default_factory=OutputPolicy)

    created_at: str = field(default_factory=_now_iso)
    schema_version: str = AGENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "owner_constraints",
            "allowed_scope",
            "prohibited_scope",
            "completion_criteria",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    @classmethod
    def mint(
        cls,
        *,
        mission_id: str,
        session_id: str,
        turn_id: str,
        requested_goal: str,
        current_goal: Optional[str] = None,
        owner_constraints: Tuple[str, ...] = (),
        allowed_scope: Tuple[str, ...] = (),
        prohibited_scope: Tuple[str, ...] = (),
        completion_criteria: Tuple[str, ...] = (),
        output_policy: Optional[OutputPolicy] = None,
    ) -> "IntentRecord":
        """Deterministically mint an intent id from its bounding fields."""
        payload = {
            "mission_id": mission_id,
            "session_id": session_id,
            "turn_id": turn_id,
            "requested_goal": requested_goal,
            "current_goal": current_goal or requested_goal,
            "owner_constraints": list(owner_constraints),
            "allowed_scope": list(allowed_scope),
            "prohibited_scope": list(prohibited_scope),
            "completion_criteria": list(completion_criteria),
        }
        intent_id = "intent-" + hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return cls(
            intent_id=intent_id,
            mission_id=mission_id,
            session_id=session_id,
            turn_id=turn_id,
            requested_goal=requested_goal,
            current_goal=current_goal or requested_goal,
            owner_constraints=tuple(owner_constraints),
            allowed_scope=tuple(allowed_scope),
            prohibited_scope=tuple(prohibited_scope),
            completion_criteria=tuple(completion_criteria),
            output_policy=output_policy or OutputPolicy(),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["output_policy"] = self.output_policy.to_dict()
        return d

    @property
    def digest(self) -> str:
        return _digest(self.to_dict())


# ---------------------------------------------------------------------------
# AgentMemoryBootTrace — durable record of what boot selected/rejected.
# (Shape per BOOT_CONTRACT.)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AgentMemoryBootTrace:
    """Durable, self-contained record of a boot decision (BOOT_CONTRACT).

    Carries every field the directive requires to be persisted: run/mission/
    session/checkpoint identity, workspace + git identity, active vs superseded
    directives, the full memory selection classification, the minted Intent
    identity + digest, the ContextPack digest, the MemoryUseDecision id, the
    gate result, execution mode, output mode, the next justified action, and the
    artifact hash of the persisted trace itself (set post-persist).
    """

    agent_run_id: str
    mission_id: str
    session_id: str
    checkpoint_id: str
    workspace_path: str
    git_branch: str
    git_sha: str
    active_directive_ids: Tuple[str, ...]
    superseded_directive_ids: Tuple[str, ...]
    selected_memory_ids: Tuple[str, ...]
    rejected_memory_ids: Tuple[str, ...]
    stale_memory_ids: Tuple[str, ...]
    conflict_ids: Tuple[str, ...]
    missing_memory_ids: Tuple[str, ...]
    intent_id: str
    intent_digest: str
    contextpack_digest: str
    memory_use_decision_id: str
    gate_result: str  # PASS | BLOCKED | DEGRADED
    execution_mode: str
    output_mode: str
    next_justified_action: str
    model_request_artifact_id: str = ""
    artifact_hash: str = ""
    created_at: str = field(default_factory=_now_iso)
    schema_version: str = AGENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "active_directive_ids",
            "superseded_directive_ids",
            "selected_memory_ids",
            "rejected_memory_ids",
            "stale_memory_ids",
            "conflict_ids",
            "missing_memory_ids",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    def to_dict(self) -> Dict[str, Any]:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(self).items()}

    def digest_dict(self) -> Dict[str, Any]:
        """Trace content EXCLUDING the artifact_hash (which is derived from it)."""
        d = self.to_dict()
        d.pop("artifact_hash", None)
        return d


# ---------------------------------------------------------------------------
# Boot request / result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AgentBootRequest:
    """Inputs to the boot pipeline. Lookups only — nothing here is authority.

    ``mission_id`` may be omitted; boot resolves the active mission from the
    store (it is never hard-coded into the runner). ``workspace_path`` is used
    for the workspace-identity binding (git SHA/branch).
    """

    workspace_path: str
    mission_id: Optional[str] = None
    session_id: Optional[str] = None
    output_mode: str = OUTPUT_MODE_CAVE
    authorize_bootstrap_degraded: bool = False
    namespace: str = "capt-solo"
    schema_version: str = AGENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.output_mode not in OUTPUT_MODES:
            raise ValueError(f"unknown output_mode: {self.output_mode!r}")


@dataclass(frozen=True)
class AgentBootResult:
    """Outcome of boot. ``execution_mode`` is one of the EXECUTION_MODE_* consts.

    When ``execution_mode == BLOCKED`` the runner must NOT invoke a provider.
    ``block_reason`` / ``block_codes`` explain the fail-closed decision.
    """

    execution_mode: str
    workspace_path: str
    git_sha: str
    git_branch: str
    mission_id: str
    session_id: str
    checkpoint_id: str
    active_directive_ids: Tuple[str, ...]
    boot_trace: Optional[AgentMemoryBootTrace] = None
    output_policy: OutputPolicy = field(default_factory=OutputPolicy)
    gate_result: str = ""  # PASS | BLOCKED | DEGRADED
    block_reason: str = ""
    block_codes: Tuple[str, ...] = ()
    degraded_missing_controls: Tuple[str, ...] = ()
    created_at: str = field(default_factory=_now_iso)
    schema_version: str = AGENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("active_directive_ids", "block_codes", "degraded_missing_controls"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.execution_mode not in (
            EXECUTION_MODE_GOVERNED,
            EXECUTION_MODE_BOOTSTRAP_DEGRADED,
            EXECUTION_MODE_BLOCKED,
        ):
            raise ValueError(f"invalid execution_mode: {self.execution_mode!r}")

    @property
    def ok(self) -> bool:
        return self.execution_mode in (
            EXECUTION_MODE_GOVERNED,
            EXECUTION_MODE_BOOTSTRAP_DEGRADED,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "execution_mode": self.execution_mode,
            "workspace_path": self.workspace_path,
            "git_sha": self.git_sha,
            "git_branch": self.git_branch,
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "checkpoint_id": self.checkpoint_id,
            "active_directive_ids": list(self.active_directive_ids),
            "boot_trace": self.boot_trace.to_dict() if self.boot_trace else None,
            "output_policy": self.output_policy.to_dict(),
            "gate_result": self.gate_result,
            "block_reason": self.block_reason,
            "block_codes": list(self.block_codes),
            "degraded_missing_controls": list(self.degraded_missing_controls),
            "created_at": self.created_at,
            "schema_version": self.schema_version,
        }
        return d


# ---------------------------------------------------------------------------
# Run state (mutable handle carried across turns within one process)
# ---------------------------------------------------------------------------
@dataclass
class AgentRunState:
    agent_run_id: str
    execution_mode: str
    mission_id: str
    session_id: str
    workspace_path: str
    git_sha: str
    output_policy: OutputPolicy
    turn_counter: int = 0
    last_checkpoint_id: str = ""
    schema_version: str = AGENT_SCHEMA_VERSION

    def next_turn_id(self) -> str:
        self.turn_counter += 1
        return f"{self.agent_run_id}:turn:{self.turn_counter}"


# ---------------------------------------------------------------------------
# Turn request / result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AgentTurnRequest:
    """One turn's CURRENT-TASK input plus the bounding Intent.

    ``user_input`` is treated as current-task input, never as continuity state
    (STATE_AUTHORITY: transcript never re-enters as authority).
    """

    intent: IntentRecord
    user_input: str
    capability_id: Optional[str] = None
    claim_text: Optional[str] = None
    schema_version: str = AGENT_SCHEMA_VERSION


@dataclass(frozen=True)
class AgentTurnResult:
    ok: bool
    turn_id: str
    intent_id: str
    mission_id: str
    session_id: str
    tx_id: str
    checkpoint_id: str
    response_text: str
    contextpack_digest: str
    gate_result: str
    claim_supported: Optional[bool] = None
    claim_language: str = ""
    provider: str = ""
    model_id: str = ""
    visible_output: str = ""
    block_reason: str = ""
    evidence_path: str = ""
    created_at: str = field(default_factory=_now_iso)
    schema_version: str = AGENT_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
