"""Utility scoring for CAPT-SOMA experiments."""

from __future__ import annotations

from typing import Dict


def utility_density(*, retained_utility: float, retained_tokens: int) -> float:
    """Measure preserved value per token."""
    if retained_tokens <= 0:
        return 0.0
    return retained_utility / retained_tokens


def compare_result(
    *,
    baseline_success: float,
    candidate_success: float,
    token_ratio: float,
) -> Dict[str, float]:
    return {
        "success_delta": candidate_success - baseline_success,
        "token_ratio": token_ratio,
        "efficiency": candidate_success / max(token_ratio, 0.001),
    }
