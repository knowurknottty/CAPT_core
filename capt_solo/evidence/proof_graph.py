"""Proof Graph — lightweight indexed relationships among claims, evidence,
verification records, and invalidation events.

Not a general graph database: an in-memory indexed model with deterministic
traversal and cycle protection. Answers:
- what supports a claim?
- which verification established it?
- is that verification still current?
- what invalidated it?
- which conclusions depend on this evidence?
- what remains valid after a scoped change?
- minimum verification needed to restore confidence?
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class _Node:
    node_id: str
    node_type: str   # claim | evidence | verification | invalidation
    ref: str = ""    # external id (record_id, claim_id, etc.)


class ProofGraph:
    def __init__(self) -> None:
        self._nodes: Dict[str, _Node] = {}
        self._edges: Dict[str, Set[str]] = {}   # node_id -> set of supported node_ids
        self._reverse: Dict[str, Set[str]] = {}  # node_id -> set of supporting node_ids

    def add_node(self, node_id: str, node_type: str, ref: str = "") -> None:
        self._nodes[node_id] = _Node(node_id, node_type, ref)
        self._edges.setdefault(node_id, set())
        self._reverse.setdefault(node_id, set())

    def link(self, supporter: str, supported: str) -> None:
        """supporter provides support to supported (e.g. evidence -> claim)."""
        if supporter not in self._nodes:
            self.add_node(supporter, "unknown")
        if supported not in self._nodes:
            self.add_node(supported, "unknown")
        self._edges[supporter].add(supported)
        self._reverse[supported].add(supporter)

    def supports(self, node_id: str) -> List[str]:
        return list(self._edges.get(node_id, set()))

    def supported_by(self, node_id: str) -> List[str]:
        return list(self._reverse.get(node_id, set()))

    def what_supports_claim(self, claim_id: str) -> List[str]:
        """Return evidence/verification node ids that (transitively) support a claim."""
        return self._bfs(claim_id, self._reverse)

    def what_depends_on(self, node_id: str) -> List[str]:
        """Return node ids (claims/conclusions) that depend on this node."""
        return self._bfs(node_id, self._edges)

    def _bfs(self, start: str, adjacency: Dict[str, Set[str]]) -> List[str]:
        seen: List[str] = []
        visited: Set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in adjacency.get(cur, ()):
                if nxt not in visited:
                    visited.add(nxt)
                    seen.append(nxt)
                    stack.append(nxt)
        return seen

    def cycle_free(self) -> bool:
        """Detect cycles via DFS coloring (cycle protection)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in self._nodes}
        def dfs(u: str) -> bool:
            color[u] = GRAY
            for v in self._edges.get(u, ()):
                if color.get(v, WHITE) == GRAY:
                    return True
                if color.get(v, WHITE) == WHITE and dfs(v):
                    return True
            color[u] = BLACK
            return False
        for n in self._nodes:
            if color[n] == WHITE:
                if dfs(n):
                    return False
        return True

    def minimum_verification_to_restore(self, invalidated_node_id: str) -> List[str]:
        """The set of nodes whose re-verification would restore confidence in
        everything depending on the invalidated node (i.e. the invalidated node
        plus its dependency closure)."""
        return [invalidated_node_id] + self.what_depends_on(invalidated_node_id)
