"""Deterministic directed evidence graph for continuity evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Set

from capt_solo.evidence.providers import OperationalEvidence
from .runtime import ContinuityError, canonical_json, digest


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    node_type: str
    timestamp: str
    digest: str
    dependencies: List[str]
    origin: str
    status: str
    confidence: float

    @classmethod
    def from_evidence(cls, evidence: OperationalEvidence) -> "EvidenceNode":
        try:
            datetime.fromisoformat(evidence.timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContinuityError("invalid evidence timestamp: " + evidence.timestamp) from exc
        if not 0.0 <= evidence.confidence <= 1.0:
            raise ContinuityError("evidence confidence must be in [0,1]")
        return cls(evidence.evidence_id, evidence.kind, evidence.timestamp, evidence.digest,
                   sorted(evidence.dependencies), evidence.origin, evidence.status, evidence.confidence)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class EvidenceGraph:
    def __init__(self, nodes: Iterable[EvidenceNode]) -> None:
        values = sorted(nodes, key=lambda item: item.node_id)
        self._nodes = {item.node_id: item for item in values}
        if len(self._nodes) != len(values):
            raise ContinuityError("duplicate evidence node id")
        missing = [(n.node_id, dep) for n in values for dep in n.dependencies if dep not in self._nodes]
        if missing:
            raise ContinuityError("orphan dependency: " + missing[0][0] + " -> " + missing[0][1])
        if not self.cycle_free():
            raise ContinuityError("evidence graph contains a cycle")

    @classmethod
    def from_providers(cls, providers: Iterable[Any]) -> "EvidenceGraph":
        providers = list(providers)
        if not providers:
            raise ContinuityError("at least one evidence provider is required")
        return cls(EvidenceNode.from_evidence(item) for provider in providers for item in provider.evidence())

    def cycle_free(self) -> bool:
        visiting: Set[str] = set(); visited: Set[str] = set()
        def visit(node_id: str) -> bool:
            if node_id in visiting: return False
            if node_id in visited: return True
            visiting.add(node_id)
            ok = all(visit(dep) for dep in self._nodes[node_id].dependencies)
            visiting.remove(node_id); visited.add(node_id)
            return ok
        return all(visit(node_id) for node_id in sorted(self._nodes))

    def nodes(self) -> List[EvidenceNode]:
        return [self._nodes[key] for key in sorted(self._nodes)]

    def path_to_root(self, node_id: str) -> List[str]:
        if node_id not in self._nodes: return []
        path = [node_id]
        while self._nodes[path[-1]].dependencies:
            path.append(self._nodes[path[-1]].dependencies[0])
        return path

    def to_dict(self) -> Dict[str, Any]:
        nodes = [node.to_dict() for node in self.nodes()]
        return {"nodes": nodes, "digest": digest(nodes)}
