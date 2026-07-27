"""Canonical execution boundaries (Layer 3 — Execution).

Phase 3H convergence: explicit, auditable boundaries for skill/plugin execution.
See capt_solo.execution.boundaries for the ExecutionBoundary contract.
"""
from __future__ import annotations

from capt_solo.execution.boundaries import (
    BoundaryResult,
    BoundaryViolation,
    Capabilities,
    ExecutionBoundary,
    capability_from_dict,
)

__all__ = [
    "ExecutionBoundary",
    "Capabilities",
    "BoundaryResult",
    "BoundaryViolation",
    "capability_from_dict",
]
