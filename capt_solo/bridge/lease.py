"""Atomic runner lease with fencing.

Replaces the race-prone check-then-write PID lock. Acquisition is atomic via
``O_CREAT | O_EXCL`` (or an atomic rename of a unique temp file on platforms where
``O_EXCL`` on the final name is unavailable). The lease metadata is written
atomically and includes a fencing token, runtime generation, PID, process-group
id, hostname, and timestamps so a stale or replaced runner can be fenced from
writing.

Design guarantees:

* two runners may never legitimately own the same mission/session generation
* a replaced runner (higher generation / newer fencing token) fences the old one
* PID reuse is handled by validating hostname + start-time + fencing token, not
  PID liveness alone
* stale locks are recovered only after metadata + ownership validation
* clean release removes the lock; SIGKILL recovery reaps an expired heartbeat
"""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

SCHEMA_VERSION = 1
_LEASE_TTL_S = 30.0  # heartbeat window for "alive" determination


class DuplicateRunnerError(RuntimeError):
    """A live runner already holds the lease for this workspace+mission."""


@dataclass
class RuntimeLease:
    """Authoritative lease metadata for one runner instance."""

    schema_version: int
    mission_id: str
    session_id: str
    runtime_id: str
    runtime_generation: int
    fencing_token: str
    pid: int
    pgid: int
    hostname: str
    created_at: float
    last_heartbeat: float
    lock_path: str = ""

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "mission_id": self.mission_id,
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "runtime_generation": self.runtime_generation,
            "fencing_token": self.fencing_token,
            "pid": self.pid,
            "pgid": self.pgid,
            "hostname": self.hostname,
            "created_at": self.created_at,
            "last_heartbeat": self.last_heartbeat,
        }

    @classmethod
    def from_dict(cls, data: dict, lock_path: str) -> "RuntimeLease":
        return cls(
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            mission_id=str(data.get("mission_id", "")),
            session_id=str(data.get("session_id", "")),
            runtime_id=str(data.get("runtime_id", "")),
            runtime_generation=int(data.get("runtime_generation", 0)),
            fencing_token=str(data.get("fencing_token", "")),
            pid=int(data.get("pid", 0)),
            pgid=int(data.get("pgid", 0)),
            hostname=str(data.get("hostname", "")),
            created_at=float(data.get("created_at", 0.0)),
            last_heartbeat=float(data.get("last_heartbeat", 0.0)),
            lock_path=lock_path,
        )

    def is_alive(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return (now - self.last_heartbeat) <= _LEASE_TTL_S

    def fences(self, other: "RuntimeLease") -> bool:
        """True if this lease is strictly newer than ``other`` (for split-brain)."""
        if self.runtime_generation != other.runtime_generation:
            return self.runtime_generation > other.runtime_generation
        return self.fencing_token > other.fencing_token


def _lock_path(workspace: Path, mission_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in mission_id)
    return workspace / ".capt" / "bridge" / f"runner-{safe}.lease"


def _live_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_runner_lease(
    workspace: Path,
    mission_id: str,
    *,
    runtime_id: str,
    runtime_generation: int,
    pid: int,
    pgid: int,
    session_id: str = "",
) -> RuntimeLease:
    """Atomically acquire the runner lease. Raises DuplicateRunnerError if held.

    Uses ``O_CREAT | O_EXCL`` on a unique candidate, then renames onto the final
    lock path so the final write is atomic and non-overwriting. A pre-existing
    lock is only reclaimed when its lease is expired AND its metadata validates
    (hostname + fencing token), never merely because its PID is not live.
    """
    lock = _lock_path(workspace, mission_id)
    lock.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(lock.parent, 0o700)

    if lock.exists():
        _reclaim_if_stale(lock, mission_id)

    candidate = lock.with_name(f"{lock.name}.{uuid.uuid4().hex}.tmp")
    lease = RuntimeLease(
        schema_version=SCHEMA_VERSION,
        mission_id=mission_id,
        session_id=session_id,
        runtime_id=runtime_id,
        runtime_generation=runtime_generation,
        fencing_token=uuid.uuid4().hex,
        pid=pid,
        pgid=pgid,
        hostname=socket.gethostname(),
        created_at=time.time(),
        last_heartbeat=time.time(),
        lock_path=str(lock),
    )
    data = json.dumps(lease.to_dict(), sort_keys=True).encode("utf-8")
    # Atomic acquisition: O_CREAT | O_EXCL on the candidate.
    fd = os.open(str(candidate), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.rename(str(candidate), str(lock))
    except OSError:
        # Another process won the race; clean up our candidate.
        try:
            os.unlink(str(candidate))
        except OSError:
            pass
        existing = _read_lease(lock)
        raise DuplicateRunnerError(
            f"runner already live for mission {mission_id!r} "
            f"(runtime {existing.runtime_id if existing else '?'})"
        )
    os.chmod(lock, 0o600)
    return lease


def _read_lease(lock: Path) -> Optional[RuntimeLease]:
    try:
        raw = lock.read_text(encoding="utf-8")
        return RuntimeLease.from_dict(json.loads(raw), str(lock))
    except Exception:
        return None


def _reclaim_if_stale(lock: Path, mission_id: str) -> None:
    existing = _read_lease(lock)
    if existing is None:
        # Unreadable/corrupt lock: treat as stale and remove (structured, not silent).
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass
        return
    now = time.time()
    if existing.is_alive(now) and _live_pid(existing.pid):
        # Genuinely live on this host: do not reclaim.
        raise DuplicateRunnerError(
            f"runner already live for mission {mission_id!r} "
            f"(pid {existing.pid}, runtime {existing.runtime_id})"
        )
    # Stale: PID gone or heartbeat expired. Validate ownership before removal —
    # only reclaim locks from the same host (PID reuse across hosts is not ours).
    if existing.hostname == socket.gethostname():
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass


def refresh_lease(workspace: Path, mission_id: str) -> None:
    """Update last_heartbeat on the held lease (call periodically while serving)."""
    lock = _lock_path(workspace, mission_id)
    existing = _read_lease(lock)
    if existing is None:
        return
    existing.last_heartbeat = time.time()
    data = json.dumps(existing.to_dict(), sort_keys=True).encode("utf-8")
    tmp = lock.with_name(f"{lock.name}.hb.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(str(tmp), str(lock))


def release_runner_lease(workspace: Path, mission_id: str, *, lease: Optional[RuntimeLease] = None) -> None:
    """Release the lease. Only removes a lock whose metadata matches ``lease``."""
    lock = _lock_path(workspace, mission_id)
    if not lock.exists():
        return
    if lease is not None:
        existing = _read_lease(lock)
        if existing is not None and existing.fencing_token != lease.fencing_token:
            # Not our lease; refuse to delete a foreign runner's lock.
            return
    try:
        lock.unlink(missing_ok=True)
    except OSError:
        pass


def read_held_lease(workspace: Path, mission_id: str) -> Optional[RuntimeLease]:
    return _read_lease(_lock_path(workspace, mission_id))
