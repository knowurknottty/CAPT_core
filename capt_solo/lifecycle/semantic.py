"""CAPT Solo v0.3 — Optional Local Semantic Retrieval (extension point).

This module defines the adapter INTERFACE and a disabled-by-default
optional extra. It does NOT ship a fake embedding implementation
and does NOT force-install a large model.

Design (from the v0.3 spec):
  * Lexical and graph retrieval remain the canonical baseline.
  * No network access required; no remote API key.
  * The semantic index must be rebuildable.
  * The semantic index must NOT be the source of truth.
  * Model identity and version must be stored.
  * Embedding dimensions must be validated.
  * A stale index must be detectable.
  * Adapter absence must NOT break operation.

If no production-realistic local adapter can be added safely, the
extension point is documented and tested WITHOUT claiming semantic
retrieval is implemented. That is the case in this release:
``SemanticAdapter`` is an interface; ``DisabledSemanticAdapter``
is the default no-op. A real adapter can be registered later
(e.g. a sentence-transformer model installed as an optional extra)
without changing any public signature.
"""

from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import ConfigurationError, MemoryError_
from capt_solo.memory.engine import MemoryEngine


@dataclass
class SemanticHit:
    memory_id: str
    score: float
    adapter: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "score": self.score,
            "adapter": self.adapter,
        }


class SemanticAdapter(ABC):
    """Interface for an optional local semantic-retrieval adapter.

    Implementations MUST be local (no network), MUST validate
    embedding dimensions, and MUST store model identity + version
    in ``semantic_index_metadata`` via :meth:`record_metadata`.
    """

    name: str = "abstract"
    model_identity: str = "unknown"
    model_version: str = "unknown"
    dimensions: int = 0

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return a fixed-dimensional embedding for ``text``."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, *, limit: int = 10) -> List[SemanticHit]:
        """Return semantic hits. Must NOT be the source of truth."""
        raise NotImplementedError

    @abstractmethod
    def rebuild(self) -> None:
        """Rebuild the local index from the canonical memory store."""
        raise NotImplementedError

    @abstractmethod
    def is_stale(self) -> bool:
        """Return True if the index is older than the canonical store."""
        raise NotImplementedError

    def record_metadata(self, engine: MemoryEngine) -> None:
        """Persist model identity/version/dimensions (auditable)."""
        engine._conn.execute(
            """INSERT OR REPLACE INTO semantic_index_metadata
               (adapter_name, model_identity, model_version, dimensions,
                built_at, source_version)
               VALUES (?,?,?,?,?)""",
            (self.name, self.model_identity, self.model_version,
             self.dimensions, time.time(),
             engine._conn.execute(
                 "SELECT MAX(version) AS v FROM schema_version"
             ).fetchone()["v"]),
        )
        engine._conn.commit()


class DisabledSemanticAdapter(SemanticAdapter):
    """Default no-op adapter. Operation continues without semantic retrieval."""

    name = "disabled"
    model_identity = "none"
    model_version = "none"
    dimensions = 0

    def embed(self, text: str) -> List[float]:
        raise ConfigurationError(
            "semantic retrieval is disabled by default; no adapter installed")

    def search(self, query: str, *, limit: int = 10) -> List[SemanticHit]:
        # Returns empty: lexical/graph retrieval remains canonical.
        return []

    def rebuild(self) -> None:
        return None

    def is_stale(self) -> bool:
        return False


# Registry of optional adapters. Empty by default; a real local
# adapter (e.g. installed as an optional extra) registers itself here.
_ADAPTERS: Dict[str, type] = {}


def register_adapter(name: str, cls: type) -> None:
    """Register an optional local semantic adapter class (not used by default)."""
    if not issubclass(cls, SemanticAdapter):
        raise MemoryError_("adapter must subclass SemanticAdapter")
    _ADAPTERS[name] = cls


def get_adapter(name: Optional[str] = None) -> SemanticAdapter:
    """Return the named adapter, or the disabled default.

    Absence of a named adapter does NOT break operation.
    """
    if name is None or name == "disabled":
        return DisabledSemanticAdapter()
    cls = _ADAPTERS.get(name)
    if cls is None:
        # graceful fallback: operation continues without semantic retrieval
        return DisabledSemanticAdapter()
    return cls()


def available_adapters() -> List[str]:
    """List registered adapter names (empty unless an extra registered one)."""
    return sorted(_ADAPTERS.keys())
