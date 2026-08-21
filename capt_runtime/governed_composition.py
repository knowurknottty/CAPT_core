"""Derived CAPT governed-composition helpers.

These values are transient, deterministic projections over existing authority.
They never grant capability, replay effects, or create a second ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Set
from urllib.parse import urlsplit, urlunsplit

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


_SECRET_KEYS = {
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}
_REFERENCE_KEYS = {"credentialref", "secretref", "keyref"}


def _normalized_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _sanitize_url(value: str) -> str:
    """Remove userinfo and query/fragment material from URL-like values."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc:
        return value
    host = parsed.hostname or ""
    if parsed.port is not None:
        host = "%s:%s" % (host, parsed.port)
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def capability_world_digest(manifest: Dict[str, Any]) -> str:
    """Digest effective composition without credential material.

    Raw secrets are omitted. Secret *references* are represented only by a digest
    so two different credential bindings remain composition-distinct without
    persisting the reference or its resolved value.
    """

    def scrub(value: Any, key: str = "") -> Any:
        normalized = _normalized_key(key)
        if normalized in _REFERENCE_KEYS:
            return {"credentialBindingDigest": digest(str(value))}
        if normalized in _SECRET_KEYS:
            return {"redacted": True}
        if isinstance(value, dict):
            return {
                str(child_key): scrub(child_value, str(child_key))
                for child_key, child_value in sorted(value.items(), key=lambda item: str(item[0]))
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        if isinstance(value, str):
            return _sanitize_url(value)
        return value

    return digest(scrub(manifest))


@dataclass
class TopologyAttestation:
    """Track explicitly registered local resources and teardown anomalies."""

    resources: Set[str] = field(default_factory=set)
    anomalies: Set[str] = field(default_factory=set)

    def mount(self, resource_id: str) -> None:
        if resource_id in self.resources:
            raise ValueError("TOPOLOGY_RESOURCE_ALREADY_MOUNTED")
        self.resources.add(resource_id)

    def unmount(self, resource_id: str) -> None:
        if resource_id not in self.resources:
            self.anomalies.add("unmount-missing:%s" % resource_id)
            raise ValueError("TOPOLOGY_RESOURCE_NOT_MOUNTED")
        self.resources.remove(resource_id)

    def digest(self) -> str:
        return digest(sorted(self.resources))

    def attests_restored(self, before_digest: str) -> bool:
        return self.digest() == before_digest and not self.anomalies


def runtime_debt(
    *,
    epoch: DependencyEpoch,
    topology: TopologyAttestation,
    expected_resources: Iterable[str],
    indeterminate_effects: int = 0,
    failed_cleanups: int = 0,
    pending_compensations: int = 0,
) -> Dict[str, Any]:
    expected = set(expected_resources)
    unexpected = sorted(topology.resources - expected)
    missing = sorted(expected - topology.resources)
    stale = 1 if epoch.state != "ACTIVE" else 0
    indeterminate = max(0, indeterminate_effects)
    cleanup_failures = max(0, failed_cleanups)
    compensations = max(0, pending_compensations)
    anomaly_count = len(topology.anomalies)
    total = (
        stale
        + len(unexpected)
        + len(missing)
        + indeterminate
        + cleanup_failures
        + compensations
        + anomaly_count
    )
    return {
        "runtimeDebt": total,
        "epochState": epoch.state,
        "staleGeneration": stale,
        "unexpectedResources": unexpected,
        "missingExpectedResources": missing,
        "topologyAnomalies": sorted(topology.anomalies),
        "indeterminateEffects": indeterminate,
        "failedCleanups": cleanup_failures,
        "pendingCompensations": compensations,
        "quiescent": total == 0,
    }
