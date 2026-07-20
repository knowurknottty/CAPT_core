"""Semantic search adapter interface (extension point).

v0.1 ships a deterministic keyword/metadata fallback so the runtime works with
zero dependencies. A real vector backend can be dropped in later by
implementing :class:`SearchAdapter` and registering it via
:func:`MemoryEngine.set_search_adapter`. The public memory API never changes.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class SearchHit:
    """A single search result returned by a :class:`SearchAdapter`."""

    memory_id: str
    score: float
    snippet: str = ""


class SearchAdapter(abc.ABC):
    """Interface that all semantic-search backends must implement.

    Implementations must be pure-Python and side-effect free with respect to
    the memory store itself (they may maintain their own index files).
    """

    @abc.abstractmethod
    def index(self, memory_id: str, text: str, metadata: dict) -> None:
        """Add or update an entry in the search index."""

    @abc.abstractmethod
    def remove(self, memory_id: str) -> None:
        """Remove an entry from the search index."""

    @abc.abstractmethod
    def search(self, query: str, limit: int = 10) -> List[SearchHit]:
        """Return ranked hits for ``query``."""

    @abc.abstractmethod
    def clear(self) -> None:
        """Drop the entire index (used on import/reset)."""


class KeywordSearchAdapter(SearchAdapter):
    """Default dependency-free adapter.

    Performs case-insensitive token overlap scoring over the stored text and
    tag/namespace metadata. Deterministic and reproducible across machines.
    """

    def __init__(self) -> None:
        self._docs: dict = {}
        self._tokens: dict = {}

    @staticmethod
    def _tokenize(text: str) -> set:
        return {t for t in text.lower().split() if t}

    def index(self, memory_id: str, text: str, metadata: dict) -> None:
        self._docs[memory_id] = text
        blob = text
        if metadata.get("tags"):
            blob += " " + " ".join(metadata["tags"])
        if metadata.get("namespace"):
            blob += " " + str(metadata["namespace"])
        self._tokens[memory_id] = self._tokenize(blob)

    def remove(self, memory_id: str) -> None:
        self._docs.pop(memory_id, None)
        self._tokens.pop(memory_id, None)

    def search(self, query: str, limit: int = 10) -> List[SearchHit]:
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []
        scored = []
        for mid, toks in self._tokens.items():
            if not toks:
                continue
            overlap = len(q_tokens & toks)
            if overlap == 0:
                continue
            # Jaccard-style score, deterministic.
            score = overlap / len(q_tokens | toks)
            snippet = self._docs.get(mid, "")[:160]
            scored.append(SearchHit(memory_id=mid, score=round(score, 6), snippet=snippet))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:limit]

    def clear(self) -> None:
        self._docs.clear()
        self._tokens.clear()


def default_adapter() -> SearchAdapter:
    """Factory used by the engine when no adapter is configured."""
    return KeywordSearchAdapter()
