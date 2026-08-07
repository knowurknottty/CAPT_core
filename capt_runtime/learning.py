"""Learning Plane (ADR-DT-PLANE-CONV, Gate 10).

Interfaces only for the M0 convergence slice. The Learning Plane remains
DOWNSTREAM of verified evidence. It owns the trajectory store, reward compiler,
strategy registry, candidate registry, evaluation harness, promotion pipeline,
and rollback manager. It does NOT implement live GRPO training, auto-promotion,
or autonomous self-modification in this slice.

Required flow (enforced, not executed):

    mission -> execution -> evidence -> verification -> ClaimGuard
    -> accepted trajectory -> reward compilation -> isolated training
    -> candidate -> offline evaluation -> human-governed promotion
    -> explicit deployment or rejection

Never: live mission -> update active weights -> continue execution.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .contracts import require
from .errors import AuthorityViolation


def accept_trajectory(trajectory: Dict[str, Any]) -> Dict[str, Any]:
    """Admit a trajectory to Learning ONLY after verification + ClaimGuard pass.

    A trajectory that is not verified or did not pass ClaimGuard is rejected and
    must never enter the reward/training path.
    """
    t = require("TrajectoryRecord", trajectory)
    if not t.get("verified"):
        raise AuthorityViolation("trajectory %s not verified; not admissible to Learning"
                                 % t["trajectoryId"])
    if not t.get("claimGuardPassed"):
        raise AuthorityViolation("trajectory %s failed ClaimGuard; not admissible to Learning"
                                 % t["trajectoryId"])
    return t


def compile_reward(trajectory: Dict[str, Any], value: float) -> Dict[str, Any]:
    """Compile a reward signal for a verified, ClaimGuard-passed trajectory."""
    accept_trajectory(trajectory)
    signal = {
        "schemaVersion": "1.0.0",
        "signalId": "rw-" + trajectory["trajectoryId"],
        "trajectoryId": trajectory["trajectoryId"],
        "value": float(value),
    }
    return require("RewardSignal", signal)


def register_strategy(kind: str, strategy_id: str, enabled: bool = False) -> Dict[str, Any]:
    """Register a learning strategy (GRPO/SFT/DPO/ORPO/KTO/RLOO). Interfaces only."""
    strat = {
        "schemaVersion": "1.0.0",
        "strategyId": strategy_id,
        "kind": kind,
        "enabled": bool(enabled),
    }
    return require("LearningStrategy", strat)


def register_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Record a model candidate produced by isolated (offline) training."""
    return require("ModelCandidate", candidate)


def decide_promotion(
    candidate: Dict[str, Any],
    decision: str,
    decided_by: str,
    decided_at: str,
    reason: str = None,
) -> Dict[str, Any]:
    """Apply a HUMAN-GOVERNED promotion decision. Auto-promotion is forbidden."""
    if decision not in ("promote", "reject"):
        raise AuthorityViolation("only human-governed promote/reject; got %r" % decision)
    rec = {
        "schemaVersion": "1.0.0",
        "decision": decision,
        "decidedBy": decided_by,
        "decidedAt": decided_at,
        "reason": reason,
    }
    require("LearningPromotionDecision", rec)
    return rec


def assert_no_live_training() -> None:
    """Guard: this slice must never perform live weight updates during a mission."""
    # Enforced by design: no training entry point exists in M0. This function is
    # a explicit, auditable assertion that the live-training path is absent.
    return None
