"""Canonical Research module adapters (Layer 3 — Research).

Per Phase 3K, research-grade modules connect to the canonical architecture through
stable adapters. Research modules are OPTIONAL capabilities (I-09): when an
underlying research module is unavailable, the adapter degrades gracefully to a
local no-op rather than breaking the runtime.

This is a CLEAN adapter contract in CAPT_core. External research modules are NOT
copied into the repo (licensing gate [L]); they register themselves via the
adapter registry when present, or are represented by a local fallback.

Adapter contract:
- name, version, capabilities
- run(input) -> ResearchResult (deterministic where possible; bounded failure)
- health() -> status
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class AdapterStatus(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"      # optional module unavailable; local fallback
    UNAVAILABLE = "unavailable"


@dataclass
class ResearchResult:
    adapter: str
    ok: bool
    output: Any = None
    error: Optional[str] = None
    provenance: str = "research_adapter"
    created_at: float = field(default_factory=time.time)


class ResearchAdapter:
    """Stable interface every research module adapter implements."""

    name: str = "base"
    version: str = "0.0.0"

    def capabilities(self) -> List[str]:
        return []

    def health(self) -> AdapterStatus:
        return AdapterStatus.ACTIVE

    def run(self, input: Any, **kwargs: Any) -> ResearchResult:
        raise NotImplementedError


class LocalFallbackAdapter(ResearchAdapter):
    """Default no-op adapter used when an optional research module is absent.

    Satisfies I-09: optional capabilities degrade gracefully. It records the
    attempt and returns a DEGRADED result without raising.
    """

    name = "local_fallback"
    version = "0.1.0"

    def __init__(self, for_module: str = "unknown") -> None:
        self._for_module = for_module

    def capabilities(self) -> List[str]:
        return []

    def health(self) -> AdapterStatus:
        return AdapterStatus.DEGRADED

    def run(self, input: Any, **kwargs: Any) -> ResearchResult:
        return ResearchResult(
            adapter=self.name,
            ok=False,
            error=f"optional research module '{self._for_module}' unavailable; "
                  f"local fallback (I-09)",
            provenance="local_fallback")


class ResearchAdapterRegistry:
    """Registry of research adapters keyed by module name."""

    def __init__(self) -> None:
        self._adapters: Dict[str, ResearchAdapter] = {}

    def register(self, module_name: str, adapter: ResearchAdapter) -> None:
        self._adapters[module_name] = adapter

    def get(self, module_name: str) -> Optional[ResearchAdapter]:
        return self._adapters.get(module_name)

    def health(self) -> Dict[str, str]:
        return {name: a.health().value for name, a in self._adapters.items()}

    def run(self, module_name: str, input: Any, **kwargs: Any) -> ResearchResult:
        ad = self._adapters.get(module_name)
        if ad is None:
            # optional capability absent -> graceful local fallback (I-09)
            return LocalFallbackAdapter(for_module=module_name).run(input, **kwargs)
        try:
            return ad.run(input, **kwargs)
        except Exception as e:  # bounded failure; do not crash runtime
            return ResearchResult(adapter=ad.name, ok=False,
                                  error=f"{type(e).__name__}: {e}")

    def list_modules(self) -> List[str]:
        return list(self._adapters.keys())


# Module-level default registry (canonical convergence point for research adapters)
DEFAULT_REGISTRY = ResearchAdapterRegistry()
