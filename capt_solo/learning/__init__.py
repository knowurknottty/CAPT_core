"""Canonical learning subsystem (Layer 3 / Learning).

Phase 3I/3J convergence: DREAM consolidation and Continuous Learning.
"""
from __future__ import annotations

from capt_solo.learning.continuous import (
    ContinuousLearner,
    FeedbackKind,
    LearningEvent,
)
from capt_solo.learning.dream import DreamConsolidator, DreamSession

__all__ = [
    "DreamConsolidator",
    "DreamSession",
    "ContinuousLearner",
    "FeedbackKind",
    "LearningEvent",
]
