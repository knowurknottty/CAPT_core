"""Canonical research subsystem (Layer 3 — Research).

Phase 3K convergence: research modules connect via stable adapters and degrade
gracefully when optional (I-09). See capt_solo.research.adapter.
"""
from __future__ import annotations

from capt_solo.research.adapter import (
    AdapterStatus,
    DEFAULT_REGISTRY,
    LocalFallbackAdapter,
    ResearchAdapter,
    ResearchAdapterRegistry,
    ResearchResult,
)

__all__ = [
    "ResearchAdapter",
    "ResearchAdapterRegistry",
    "ResearchResult",
    "AdapterStatus",
    "LocalFallbackAdapter",
    "DEFAULT_REGISTRY",
]
