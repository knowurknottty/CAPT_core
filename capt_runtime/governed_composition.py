"""Derived CAPT governed-composition helpers.

These values are transient, deterministic projections over existing authority.
They never grant capability, replay effects, or create a second ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Set

from .contracts import digest


@dataclass
class DependencyEpoch:
    """Reject late completions after a scoped dependency/configuration change."""
    generation: int = 0
    state: str = "ACTIVE"

    def advance(self) -> int:
        self.generation += 1
        self.state = "RECONCILING"
        return self.generation

    def activate(self, generation: int) -> bool:
        if generation != self.generation:
            return False
        self.state = "ACTIVE"
        return True

    def accepts_completion(self, generation: int) -> bool:
        return self.state == "ACTIVE" and generation == self.generation


def capability_world_digest(manifest: Dict[str, Any]) -> str:
    """Secret-free digest of effective composition, not a grant or policy decision."""
    prohibited = {"api_key", "apikey", "authorization", "password", "secret", "token"}

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: scrub(v) for k, v in value.items() if k.lower().replace("_", "") not in prohibited}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        return value

    return digest(scrub(manifest))


@dataclass
class TopologyAttestation:
    """Tracks only explicitly registered local resources."""
    resources: Set[str] = field(default_factory=set)

    def mount(self, resource_id: str) -> None:
        if resource_id in self.resources:
            raise ValueError("TOPOLOGY_RESOURCE_ALREADY_MOUNTED")
        self.resources.add(resource_id)

    def unmount(self, resource_id: str) -> None:
        self.resources.discard(resource_id)

    def digest(self) -> str:
        return digest(sorted(self.resources))

    def attests_restored(self, before_digest: str) -> bool:
        return self.digest() == before_digest


def runtime_debt(*, epoch: DependencyEpoch, topology: TopologyAttestation,
                 expected_resources: Iterable[str], indeterminate_effects: int = 0) -> Dict[str, Any]:
    expected = set(expected_resources)
    unexpected = sorted(topology.resources - expected)
    stale = 1 if epoch.state != "ACTIVE" else 0
    total = stale + len(unexpected) + max(0, indeterminate_effects)
    return {"runtimeDebt": total, "staleGeneration": stale,
            "unexpectedResources": unexpected, "indeterminateEffects": max(0, indeterminate_effects),
            "quiescent": total == 0}
