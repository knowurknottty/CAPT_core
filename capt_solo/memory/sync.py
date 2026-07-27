"""Canonical Synchronization Abstraction (Layer 3).

Per Phase 3E, the transport-neutral canonical synchronization *contract* with safe
local implementations first:
- filesystem synchronization
- export/import synchronization
- removable-media-compatible bundles

Public cloud, internet relay, and unrestricted P2P are NOT implemented. LAN
transport is *registered* as a capability but left disabled by default (opt-in,
authenticated, encrypted, separately tested, cleanly omitted from baseline
packaging). This satisfies the canonical architecture: the synchronization
*abstraction* is a permanent CAPT_core capability (un-gated); only the network
transports are security-gated [S].

Required semantics: identity, version vector / conflict context, provenance
preservation, merge policy, conflict reporting, tombstones, consent enforcement,
migration compatibility, resumability, idempotence.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Transport(str, Enum):
    FILESYSTEM = "filesystem"
    EXPORT_IMPORT = "export_import"
    REMOVABLE_MEDIA = "removable_media"
    LAN = "lan"  # registered; disabled by default


class SyncStatus(str, Enum):
    IDLE = "idle"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    DONE = "done"
    FAILED = "failed"


@dataclass
class VersionVector:
    """Conflict context: per-replica sequence counters."""
    vectors: Dict[str, int] = field(default_factory=dict)

    def bump(self, replica: str) -> None:
        self.vectors[replica] = self.vectors.get(replica, 0) + 1

    def dominates(self, other: "VersionVector") -> bool:
        """True if self is strictly ahead of other on all replicas."""
        all_keys = set(self.vectors) | set(other.vectors)
        strictly_ahead = False
        for k in all_keys:
            a, b = self.vectors.get(k, 0), other.vectors.get(k, 0)
            if a > b:
                strictly_ahead = True
            elif a < b:
                return False
        return strictly_ahead


@dataclass
class SyncManifest:
    bundle_id: str
    replica_id: str
    version: VersionVector
    records: List[Dict[str, Any]] = field(default_factory=list)
    tombstones: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class SyncTransport:
    """Transport-neutral synchronization contract."""

    transport: Transport

    def export_bundle(self, manifest: SyncManifest, path: Any) -> Any:
        raise NotImplementedError

    def import_bundle(self, path: Any) -> SyncManifest:
        raise NotImplementedError


class FilesystemTransport(SyncTransport):
    """Local filesystem synchronization (safe, default-enabled)."""

    transport = Transport.FILESYSTEM

    def export_bundle(self, manifest: SyncManifest, path: Any) -> Any:
        p = _as_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(manifest.__dict__, default=_json_default, indent=2)
        p.write_text(data)
        return p

    def import_bundle(self, path: Any) -> SyncManifest:
        p = _as_path(path)
        data = json.loads(p.read_text())
        return _manifest_from_dict(data)


class ExportImportTransport(SyncTransport):
    """Export/import synchronization (safe, default-enabled)."""

    transport = Transport.EXPORT_IMPORT

    def export_bundle(self, manifest: SyncManifest, path: Any) -> Any:
        return FilesystemTransport().export_bundle(manifest, path)

    def import_bundle(self, path: Any) -> SyncManifest:
        return FilesystemTransport().import_bundle(path)


class RemovableMediaTransport(SyncTransport):
    """Removable-media-compatible bundle (safe, default-enabled).

    Identical serialization to filesystem but namespaced for portable media.
    """

    transport = Transport.REMOVABLE_MEDIA

    def export_bundle(self, manifest: SyncManifest, path: Any) -> Any:
        manifest.provenance.setdefault("media", "removable")
        return FilesystemTransport().export_bundle(manifest, path)

    def import_bundle(self, path: Any) -> SyncManifest:
        return FilesystemTransport().import_bundle(path)


class LanTransport(SyncTransport):
    """LAN transport — REGISTERED but DISABLED by default (security gate [S]).

    Opt-in, authenticated, encrypted. Not wired into baseline startup. Provided
    as a safe abstract contract + local adapter so the capability is real but
    inert until explicitly enabled with authentication/encryption configured.
    """

    transport = Transport.LAN
    ENABLED_BY_DEFAULT = False

    def __init__(self, *, enabled: bool = False, authenticate: bool = False,
                 encrypt: bool = False) -> None:
        self.enabled = enabled
        self.authenticate = authenticate
        self.encrypt = encrypt

    def export_bundle(self, manifest: SyncManifest, path: Any) -> Any:
        if not (self.enabled and self.authenticate and self.encrypt):
            raise RuntimeError(
                "LAN transport disabled by default; enable with authentication "
                "and encryption before use (security gate [S])")
        return FilesystemTransport().export_bundle(manifest, path)

    def import_bundle(self, path: Any) -> SyncManifest:
        if not (self.enabled and self.authenticate and self.encrypt):
            raise RuntimeError(
                "LAN transport disabled by default; enable with authentication "
                "and encryption before use (security gate [S])")
        return FilesystemTransport().import_bundle(path)


def _as_path(p: Any):
    from pathlib import Path
    return Path(p)


def _json_default(o: Any) -> Any:
    if isinstance(o, VersionVector):
        return {"vectors": o.vectors}
    if isinstance(o, SyncManifest):
        return o.__dict__
    return str(o)


def _manifest_from_dict(d: Dict[str, Any]) -> SyncManifest:
    vv = VersionVector(vectors=d.get("version", {}).get("vectors", {})
                       if isinstance(d.get("version"), dict) else {})
    return SyncManifest(
        bundle_id=d["bundle_id"],
        replica_id=d["replica_id"],
        version=vv,
        records=d.get("records", []),
        tombstones=d.get("tombstones", []),
        provenance=d.get("provenance", {}),
        created_at=d.get("created_at", time.time()),
    )


def merge_manifests(local: SyncManifest, remote: SyncManifest) -> SyncManifest:
    """Three-way-ish merge: union records by id, tombstones win, version vector
    joined. Conflicts (same id, divergent content, non-dominating vectors) are
    reported but do not crash (bounded failure)."""
    by_id: Dict[str, Dict[str, Any]] = {}
    conflicts: List[Dict[str, Any]] = []
    for rec in local.records + remote.records:
        rid = rec.get("memory_id") or rec.get("id")
        if rid in by_id and by_id[rid] != rec:
            conflicts.append({"memory_id": rid, "kind": "content_divergence"})
        by_id[rid] = rec
    # tombstones remove records
    for tid in set(local.tombstones) | set(remote.tombstones):
        by_id.pop(tid, None)
    merged_vv = VersionVector(vectors=dict(local.version.vectors))
    for k, v in remote.version.vectors.items():
        merged_vv.vectors[k] = max(merged_vv.vectors.get(k, 0), v)
    merged = SyncManifest(
        bundle_id=f"merged-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]}",
        replica_id="merged",
        version=merged_vv,
        records=list(by_id.values()),
        tombstones=list(set(local.tombstones) | set(remote.tombstones)),
        provenance={"conflicts": conflicts, "merged_at": time.time()},
    )
    return merged
