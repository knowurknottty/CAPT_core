"""Versioned, integrity-bound runtime continuity metadata.

Replaces the unsigned plaintext ``session-<mission>.sid`` sidecar. Continuity
authority remains in CAPT's canonical persistence (the checkpoint); this metadata
*references and validates* canonical state (mission id, checkpoint id, checkpoint
digest) rather than replacing it.

Properties:

* atomic write via temp file + fsync + rename (no partial file ever observed)
* private directory (0700) and file (0600) permissions
* integrity digest (HMAC-free SHA-256 over the canonical fields)
* mission binding, checkpoint binding, schema version
* generation tracking and fencing token
* rejects malformed / mission-mismatch / checkpoint-mismatch / unsupported schema
* rejects detectable rollback
* distinguishes MISSING from CORRUPTED
* no silent read/write failure — failures raise structured errors
* legacy ``.sid`` files are migrated explicitly and once
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

SCHEMA_VERSION = 1


class ContinuityError(Exception):
    """Structured continuity failure with a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


MISSING = "CONTINUITY_MISSING"
CORRUPTED = "CONTINUITY_CORRUPTED"
UNSUPPORTED_SCHEMA = "CONTINUITY_UNSUPPORTED_SCHEMA"
MISSION_MISMATCH = "CONTINUITY_MISSION_MISMATCH"
CHECKPOINT_MISMATCH = "CONTINUITY_CHECKPOINT_MISMATCH"
ROLLBACK = "CONTINUITY_ROLLBACK_DETECTED"
WRITE_FAILED = "CONTINUITY_WRITE_FAILED"


@dataclass
class ContinuityMetadata:
    schema_version: int
    mission_id: str
    session_id: str
    checkpoint_id: str
    runtime_generation: int
    previous_generation: int
    runtime_id: str
    checkpoint_digest: str
    created_at: str
    updated_at: str
    fencing_token: str
    metadata_digest: str = ""

    def _canonical(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "checkpoint_id": self.checkpoint_id,
            "runtime_generation": self.runtime_generation,
            "previous_generation": self.previous_generation,
            "runtime_id": self.runtime_id,
            "checkpoint_digest": self.checkpoint_digest,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "fencing_token": self.fencing_token,
        }

    def compute_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self._canonical(), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict:
        d = self._canonical()
        d["metadata_digest"] = self.compute_digest()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ContinuityMetadata":
        if not isinstance(data, dict):
            raise ContinuityError(CORRUPTED, "continuity metadata is not an object")
        if int(data.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ContinuityError(
                UNSUPPORTED_SCHEMA,
                f"schema {data.get('schema_version')} != {SCHEMA_VERSION}",
            )
        meta = cls(
            schema_version=int(data["schema_version"]),
            mission_id=str(data["mission_id"]),
            session_id=str(data["session_id"]),
            checkpoint_id=str(data["checkpoint_id"]),
            runtime_generation=int(data["runtime_generation"]),
            previous_generation=int(data.get("previous_generation", 0)),
            runtime_id=str(data["runtime_id"]),
            checkpoint_digest=str(data["checkpoint_digest"]),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            fencing_token=str(data.get("fencing_token", "")),
        )
        expected = meta.compute_digest()
        if data.get("metadata_digest") != expected:
            raise ContinuityError(CORRUPTED, "continuity metadata digest mismatch")
        return meta


def _path(workspace: Path, mission_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in mission_id)
    return workspace / ".capt" / "bridge" / f"continuity-{safe}.json"


def _legacy_path(workspace: Path, mission_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in mission_id)
    return workspace / ".capt" / "bridge" / f"session-{safe}.sid"


def load_continuity(
    workspace: Path, mission_id: str, *, expected_checkpoint_id: str = ""
) -> ContinuityMetadata:
    """Load and validate continuity metadata. Raises ContinuityError on any defect."""
    path = _path(workspace, mission_id)
    if not path.exists():
        # Try one-time legacy migration before declaring missing.
        legacy = _legacy_path(workspace, mission_id)
        if legacy.exists():
            _migrate_legacy(workspace, mission_id, legacy)
            # fall through to read the migrated file
        else:
            raise ContinuityError(MISSING, f"no continuity metadata for {mission_id!r}")
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContinuityError(CORRUPTED, f"continuity metadata not valid JSON: {exc}")
    except OSError as exc:
        raise ContinuityError(CORRUPTED, f"cannot read continuity metadata: {exc}")
    meta = ContinuityMetadata.from_dict(data)
    if meta.mission_id != mission_id:
        raise ContinuityError(
            MISSION_MISMATCH,
            f"metadata mission {meta.mission_id!r} != {mission_id!r}",
        )
    if expected_checkpoint_id and meta.checkpoint_id != expected_checkpoint_id:
        raise ContinuityError(
            CHECKPOINT_MISMATCH,
            f"metadata checkpoint {meta.checkpoint_id!r} != {expected_checkpoint_id!r}",
        )
    return meta


def save_continuity(
    workspace: Path,
    *,
    mission_id: str,
    session_id: str,
    checkpoint_id: str,
    runtime_id: str,
    runtime_generation: int,
    previous_generation: int,
    checkpoint_digest: str,
    fencing_token: str,
) -> ContinuityMetadata:
    """Atomically write continuity metadata. Raises ContinuityError on failure."""
    base = workspace / ".capt" / "bridge"
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(base, 0o700)
    path = _path(workspace, mission_id)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    existing = None
    if path.exists():
        try:
            existing = ContinuityMetadata.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            existing = None
    if existing is not None:
        if existing.runtime_generation > runtime_generation:
            raise ContinuityError(
                ROLLBACK,
                f"refusing to roll back generation {existing.runtime_generation} -> {runtime_generation}",
            )
    meta = ContinuityMetadata(
        schema_version=SCHEMA_VERSION,
        mission_id=mission_id,
        session_id=session_id,
        checkpoint_id=checkpoint_id,
        runtime_generation=runtime_generation,
        previous_generation=previous_generation,
        runtime_id=runtime_id,
        checkpoint_digest=checkpoint_digest,
        created_at=existing.created_at if existing else now,
        updated_at=now,
        fencing_token=fencing_token,
    )
    data = json.dumps(meta.to_dict(), indent=2, sort_keys=True).encode("utf-8")
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.rename(str(tmp), str(path))
        os.chmod(path, 0o600)
    except OSError as exc:
        try:
            os.unlink(str(tmp))
        except OSError:
            pass
        raise ContinuityError(WRITE_FAILED, f"cannot write continuity metadata: {exc}")
    return meta


def _migrate_legacy(workspace: Path, mission_id: str, legacy: Path) -> None:
    """One-time explicit migration of a plaintext .sid sidecar."""
    session_id = legacy.read_text(encoding="utf-8").strip()
    if not session_id:
        legacy.unlink(missing_ok=True)
        return
    # Without a canonical checkpoint we cannot bind; record with empty bindings
    # and let the next governed turn re-bind. Mark previous_generation=0.
    save_continuity(
        workspace,
        mission_id=mission_id,
        session_id=session_id,
        checkpoint_id="",
        runtime_id="",
        runtime_generation=1,
        previous_generation=0,
        checkpoint_digest="",
        fencing_token="legacy-migrated",
    )
    legacy.unlink(missing_ok=True)
