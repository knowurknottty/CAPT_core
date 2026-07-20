"""CAPT Solo v0.2 — deterministic trust layer.

Trust is NOT based on repetition, retrieval frequency, or graph popularity.
It is computed from explicit, auditable inputs (source type, verification
status, contradiction state, derivation depth, CTP receipt linkage, etc.).

An inference or generated summary is NEVER silently promoted to a verified fact.
All transitions are recorded and auditable.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from capt_solo.memory.models import MemoryKind, TrustState

# Base trust weights per source type. These are defaults; configuration may
# override. Higher = more trustworthy by default, before adjustments.
_BASE_WEIGHTS: Dict[TrustState, float] = {
    TrustState.VERIFIED_RESULT: 1.0,
    TrustState.TOOL_RESULT: 0.85,
    TrustState.OBSERVED_FACT: 0.8,
    TrustState.USER_FACT: 0.75,
    TrustState.INSTRUCTION: 0.7,
    TrustState.PREFERENCE: 0.65,
    TrustState.GENERATED_SUMMARY: 0.5,
    TrustState.HYPOTHESIS: 0.4,
    TrustState.INFERENCE: 0.35,
    TrustState.CONFLICTED: 0.1,
    TrustState.SUPERSEDED: 0.05,
    TrustState.REJECTED: 0.0,
}

# Allowed transitions. A transition not listed here is rejected by
# ``apply_transition`` so trust state cannot drift silently.
_ALLOWED: Dict[TrustState, List[TrustState]] = {
    TrustState.USER_FACT: [TrustState.VERIFIED_RESULT, TrustState.CONFLICTED,
                            TrustState.SUPERSEDED, TrustState.REJECTED],
    TrustState.OBSERVED_FACT: [TrustState.VERIFIED_RESULT, TrustState.CONFLICTED,
                               TrustState.SUPERSEDED, TrustState.REJECTED],
    TrustState.TOOL_RESULT: [TrustState.VERIFIED_RESULT, TrustState.CONFLICTED,
                             TrustState.SUPERSEDED, TrustState.REJECTED],
    TrustState.INFERENCE: [TrustState.HYPOTHESIS, TrustState.OBSERVED_FACT,
                           TrustState.CONFLICTED, TrustState.REJECTED],
    TrustState.HYPOTHESIS: [TrustState.OBSERVED_FACT, TrustState.VERIFIED_RESULT,
                             TrustState.CONFLICTED, TrustState.REJECTED],
    TrustState.GENERATED_SUMMARY: [TrustState.CONFLICTED, TrustState.SUPERSEDED,
                                   TrustState.REJECTED],
    TrustState.INSTRUCTION: [TrustState.CONFLICTED, TrustState.SUPERSEDED,
                             TrustState.REJECTED],
    TrustState.PREFERENCE: [TrustState.CONFLICTED, TrustState.SUPERSEDED,
                            TrustState.REJECTED],
    TrustState.VERIFIED_RESULT: [TrustState.CONFLICTED, TrustState.SUPERSEDED,
                                 TrustState.REJECTED],
    TrustState.CONFLICTED: [TrustState.VERIFIED_RESULT, TrustState.REJECTED,
                             TrustState.SUPERSEDED],
    TrustState.SUPERSEDED: [TrustState.REJECTED],
    TrustState.REJECTED: [TrustState.USER_FACT, TrustState.OBSERVED_FACT],
}


def base_weight(state: TrustState) -> float:
    return _BASE_WEIGHTS.get(state, 0.3)


def can_transition(frm: TrustState, to: TrustState) -> bool:
    return to in _ALLOWED.get(frm, [])


def apply_transition(frm: TrustState, to: TrustState) -> TrustState:
    """Validate and return the target state. Raises ValueError if disallowed."""
    if not can_transition(frm, to):
        raise ValueError(f"disallowed trust transition: {frm.value} -> {to.value}")
    return to


def compute_trust(
    source_type: TrustState,
    *,
    confidence: float = 1.0,
    contradiction: bool = False,
    superseded: bool = False,
    verified: bool = False,
    derivation_depth: int = 0,
    has_ctp_receipt: bool = False,
    age_days: float = 0.0,
) -> Tuple[float, List[str]]:
    """Deterministic trust score in [0,1] from explicit inputs.

    Never promotes an inference/hypothesis to verified automatically — that
    requires an explicit ``apply_transition`` call (e.g. after a test passes).
    """
    notes: List[str] = []
    score = base_weight(source_type) * max(0.0, min(1.0, confidence))

    if contradiction:
        score *= 0.3
        notes.append("contradiction penalty")
    if superseded:
        score *= 0.1
        notes.append("superseded penalty")
    if verified and source_type in (TrustState.INFERENCE, TrustState.HYPOTHESIS,
                                   TrustState.GENERATED_SUMMARY):
        # explicit verification is allowed to raise, but only via transition
        notes.append("verification noted; explicit transition required to promote")
    if derivation_depth > 0:
        score *= max(0.5, 1.0 - 0.1 * derivation_depth)
        notes.append(f"derivation depth {derivation_depth} penalty")
    if has_ctp_receipt:
        score = min(1.0, score + 0.05)
        notes.append("ctp receipt linkage bonus")
    if age_days > 365:
        score *= 0.95
        notes.append("stale age penalty")
    return max(0.0, min(1.0, score)), notes


def trust_from_kind(kind: MemoryKind) -> TrustState:
    """Map a memory kind to a default trust state (never auto-verified)."""
    mapping = {
        MemoryKind.FACT: TrustState.OBSERVED_FACT,
        MemoryKind.CLAIM: TrustState.USER_FACT,
        MemoryKind.DECISION: TrustState.INSTRUCTION,
        MemoryKind.PROCEDURE: TrustState.INSTRUCTION,
        MemoryKind.OBSERVATION: TrustState.OBSERVED_FACT,
        MemoryKind.HYPOTHESIS: TrustState.HYPOTHESIS,
        MemoryKind.REQUIREMENT: TrustState.INSTRUCTION,
        MemoryKind.CONSTRAINT: TrustState.INSTRUCTION,
        MemoryKind.FAILURE: TrustState.OBSERVED_FACT,
        MemoryKind.LESSON: TrustState.USER_FACT,
        MemoryKind.TASK: TrustState.INSTRUCTION,
        MemoryKind.ARTIFACT_REF: TrustState.TOOL_RESULT,
        MemoryKind.TRANSACTION_REF: TrustState.TOOL_RESULT,
        MemoryKind.SESSION_SUMMARY: TrustState.GENERATED_SUMMARY,
    }
    return mapping.get(kind, TrustState.USER_FACT)
