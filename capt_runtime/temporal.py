"""Temporal model (ADR-DT-PLANE-CONV, Gate 13).

A canonical TemporalContext distinguishing wall-clock, monotonic, logical,
causal, mission-relative, lease-expiration, policy-effective, evidence-observation,
verification, memory-freshness, training-cutoff, and replay times. This is NOT a
Time Plane; it is a cross-cutting model owned by no plane.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .contracts import require


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_temporal_context(
    *,
    monotonic: float,
    logical: int,
    causal: str,
    mission_relative: float,
    lease_expiration: Optional[str] = None,
    policy_effective: Optional[str] = None,
    evidence_observation: Optional[str] = None,
    verification_time: Optional[str] = None,
    memory_freshness: Optional[str] = None,
    training_cutoff: Optional[str] = None,
    replay_time: Optional[str] = None,
) -> Dict[str, Any]:
    ctx = {
        "schemaVersion": "1.0.0",
        "wallClock": now_iso(),
        "monotonic": float(monotonic),
        "logical": int(logical),
        "causal": causal,
        "missionRelative": float(mission_relative),
        "leaseExpiration": lease_expiration,
        "policyEffective": policy_effective,
        "evidenceObservation": evidence_observation,
        "verificationTime": verification_time,
        "memoryFreshness": memory_freshness,
        "trainingCutoff": training_cutoff,
        "replayTime": replay_time,
    }
    return require("TemporalContext", ctx)


def is_expired(expiration_iso: Optional[str], now: Optional[str] = None) -> bool:
    """Return True if an expiration timestamp is in the past (stale lease/approval)."""
    if expiration_iso is None:
        return False
    ref = now or now_iso()
    return ref >= expiration_iso


def causal_order_ok(parent_causal: str, child_causal: str) -> bool:
    """Replay ordering: a child's causal reference must point to its parent."""
    return child_causal.startswith(parent_causal) or child_causal == parent_causal


def observation_before_verification(obs_iso: Optional[str], ver_iso: Optional[str]) -> bool:
    """Evidence observation time must precede verification time."""
    if obs_iso is None or ver_iso is None:
        return True
    return obs_iso <= ver_iso


def no_future_leak_into_history(
    historical_cutoff: Optional[str],
    candidate_time: Optional[str],
) -> bool:
    """Reject future information leaking into historical simulation/replay."""
    if historical_cutoff is None or candidate_time is None:
        return True
    return candidate_time <= historical_cutoff
