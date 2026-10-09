"""Optional local bioCAPT cohort observation, under CAPT EventStore authority.

This is a real read-only native Unix socket integration. It NEVER launches
cogitation, dispatches models, approves actions, or claims that module presence
is cognitive evidence. It is opt-in; a persisted CAPT grant/lease is mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import time
from typing import Any

from .aggregates.capability import CapabilityAggregate
from .errors import CapabilityDenied

EXPECTED_SCHEMA = "biocapt.live-introspection/1"
MAX_BYTES = 32768


@dataclass(frozen=True)
class BioCAPTObservation:
    schema: str
    status: str
    health: str
    authority: str
    cognition_executed: bool
    has_recent_cogitation: bool
    source_pid: int | None
    snapshot_digest: str | None
    module_count: int
    recorded_at: str
    reasons: tuple[str, ...]
    provider_calls: int = 0
    actuation_allowed: bool = False


class BioCAPTLocalCohortReader:
    """An optional CAPT-native cohort source, not a provider or execution driver."""

    def __init__(self, store: Any, socket_path: str, *, max_age_seconds: int = 12):
        self.store = store
        self.socket_path = Path(socket_path)
        if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 120:
            raise ValueError("INVALID_BIOCAPT_MAX_AGE")
        self.max_age_seconds = max_age_seconds

    def _authorize(self, grant_id: str, lease_id: str, *,
                   mission_id: str, task_id: str, actor_id: str) -> None:
        # Grant MUST come from the live EventStore, not model-supplied JSON.
        if not all(isinstance(x, str) and x for x in
                   (grant_id, lease_id, mission_id, task_id, actor_id)):
            raise CapabilityDenied("BIOCAPT_IDENTITY_MISSING")
        state = self.store.load_state(CapabilityAggregate.stream_id(grant_id))
        if not isinstance(state, dict) or state.get("grantState") != "leased":
            raise CapabilityDenied("BIOCAPT_GRANT_NOT_LEASED")
        if state.get("subjectActorId") != actor_id or state.get("grantId") != grant_id:
            raise CapabilityDenied("BIOCAPT_GRANT_SUBJECT_MISMATCH")
        lease = state.get("lease")
        if not isinstance(lease, dict) or lease.get("leaseId") != lease_id:
            raise CapabilityDenied("BIOCAPT_LEASE_ID_MISMATCH")
        if lease.get("missionId") != mission_id or lease.get("taskId") != task_id:
            raise CapabilityDenied("BIOCAPT_LEASE_MISSION_TASK_MISMATCH")
        # Read-only projection must not bypass bounded-use reservations or
        # unimplemented policy conditions.
        if state.get("maxUses") is not None or lease.get("maxUses") is not None:
            raise CapabilityDenied("BIOCAPT_BOUNDED_USE_REQUIRES_RESERVATION")
        if state.get("conditions"):
            raise CapabilityDenied("BIOCAPT_UNSUPPORTED_GRANT_CONDITIONS")
        path = self.socket_path
        if path.is_symlink() or path.parent.is_symlink():
            raise CapabilityDenied("BIOCAPT_SYMLINKED_SOCKET_PATH")
        if not path.exists() or not stat.S_ISSOCK(path.lstat().st_mode):
            raise CapabilityDenied("BIOCAPT_SOCKET_UNAVAILABLE")
        parent = path.parent.stat()
        sock = path.stat()
        if parent.st_uid != os.geteuid() or sock.st_uid != os.geteuid():
            raise CapabilityDenied("BIOCAPT_SOCKET_OWNER_MISMATCH")
        if parent.st_mode & 0o077 or sock.st_mode & 0o077:
            raise CapabilityDenied("BIOCAPT_SOCKET_PERMISSIONS_EXCESSIVE")
        scope = {"kind": "filesystem", "rootPath": str(path.resolve()),
                 "recursive": False}
        CapabilityAggregate.check_lease(
            state, lease_id, "filesystem.read", scope,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    def _read(self, route: str) -> dict:
        if route not in ("/v1/manifest", "/v1/snapshot"):
            raise ValueError("UNRECOGNIZED_BIOCAPT_ROUTE")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(2.0)
            conn.connect(str(self.socket_path))
            conn.sendall(f"GET {route} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
            data = bytearray()
            while len(data) < MAX_BYTES + 4096:
                part = conn.recv(min(4096, MAX_BYTES + 4096 - len(data)))
                if not part:
                    break
                data.extend(part)
        try:
            header, body = bytes(data).split(b"\r\n\r\n", 1)
            if not header.startswith(b"HTTP/1.1 200 "):
                raise ValueError("BIOCAPT_HTTP_STATUS_NOT_OK")
            if len(body) > MAX_BYTES:
                raise ValueError("BIOCAPT_RESPONSE_TOO_LARGE")
            value = json.loads(body)
            if not isinstance(value, dict):
                raise ValueError("BIOCAPT_RESPONSE_NOT_OBJECT")
            return value
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("BIOCAPT_BAD_RESPONSE") from exc

    def observe(self, *, grant_id: str, lease_id: str, mission_id: str,
                task_id: str, actor_id: str) -> BioCAPTObservation:
        self._authorize(grant_id, lease_id, mission_id=mission_id,
                        task_id=task_id, actor_id=actor_id)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            manifest = self._read("/v1/manifest")
            if (manifest.get("schema") != EXPECTED_SCHEMA
                    or manifest.get("writes") is not False
                    or "GET /v1/snapshot" not in manifest.get("methods", [])):
                raise ValueError("BIOCAPT_MANIFEST_INCOMPATIBLE")
            snapshot = self._read("/v1/snapshot")
            if (snapshot.get("schema") != EXPECTED_SCHEMA
                    or snapshot.get("evidence") != "live_same_process"):
                raise ValueError("BIOCAPT_EVIDENCE_INVALID")
            pid = snapshot.get("capt_pid")
            if type(pid) is not int or pid <= 0:
                raise ValueError("BIOCAPT_PID_INVALID")
            sampled = snapshot.get("observed_at")
            core = snapshot.get("core")
            if (not isinstance(sampled, (int, float)) or isinstance(sampled, bool)
                    or not isinstance(core, dict)):
                raise ValueError("BIOCAPT_HEALTH_UNAVAILABLE")
            if abs(time.time() - sampled) > self.max_age_seconds:
                return self._result("UNKNOWN", "UNKNOWN", timestamp, ("STALE_SNAPSHOT",), pid)
            if core.get("initialized") is not True:
                return self._result("UNKNOWN", "UNHEALTHY", timestamp, ("NOT_INITIALIZED",), pid)
            completed = snapshot.get("last_cogitation")
            if completed is None:
                return self._result("NO_VOTE", "HEALTHY", timestamp, ("NO_COGITATION_RECEIPT",), pid)
            if not isinstance(completed, dict):
                raise ValueError("BIOCAPT_COGITATION_RECEIPT_INVALID")
            outputs = completed.get("module_outputs")
            if not isinstance(outputs, dict):
                raise ValueError("BIOCAPT_MODULE_RECEIPTS_INVALID")
            # Module presence and PULSE completion are observable; not truth.
            processed = bool(outputs) and completed.get("pulse_success") is True
            status = "PROPOSED" if processed else "UNKNOWN"
            subset = {"pid": pid, "sequence": snapshot.get("sequence"),
                      "observed_at": sampled, "module_names": sorted(outputs.keys()),
                      "pulse_success": completed.get("pulse_success")}
            receipt = hashlib.sha256(json.dumps(subset, sort_keys=True,
                                                 separators=(",", ":")).encode()).hexdigest()
            return BioCAPTObservation("capt.biocapt-observation/1", status,
                                     "HEALTHY", "advisory_only", False,
                                     processed, pid, receipt, len(outputs),
                                     timestamp, (), 0, False)
        except (OSError, TimeoutError, ValueError, TypeError):
            return self._result("UNHEALTHY", "UNHEALTHY", timestamp, ("PROBE_FAILURE",), None)

    @staticmethod
    def _result(status: str, health: str, timestamp: str,
                reasons: tuple[str, ...], pid: int | None) -> BioCAPTObservation:
        return BioCAPTObservation("capt.biocapt-observation/1", status, health,
                                 "advisory_only", False, False, pid, None,
                                 0, timestamp, reasons, 0, False)
