"""Bounded Local terminal/process backend.

No shell interpolation, no inherited arbitrary secrets, no direct authority.
ToolBroker admission must occur before this backend is called in production.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Tuple

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.scope import require_scoped_path

SAFE_PARENT_ENV = frozenset({
    "PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "TMP", "TEMP",
    "LANG", "LC_ALL", "LC_CTYPE", "TERM",
})
MAX_CAPTURE_BYTES = 16 * 1024 * 1024
MAX_STDIN_BYTES = 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LocalProcessRequest:
    argv: Tuple[str, ...]
    cwd: Path
    filesystem_root: Path
    timeout_seconds: float = 30.0
    stdout_limit_bytes: int = 1024 * 1024
    stderr_limit_bytes: int = 1024 * 1024
    env_allowlist: Tuple[str, ...] = tuple(sorted(SAFE_PARENT_ENV))
    env_overrides: Mapping[str, str] = field(default_factory=dict)
    cancel_event: Optional[threading.Event] = None
    terminate_grace_seconds: float = 0.5
    stdin_data: Optional[bytes] = None


@dataclass(frozen=True)
class LocalProcessResult:
    exit_code: Optional[int]
    stdout: str
    stderr: str
    stdout_total_bytes: int
    stderr_total_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool
    started_at: str
    completed_at: str
    pid: int
    process_group_id: int
    timed_out: bool
    cancelled: bool


class _BoundedCollector:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.buffer = bytearray()
        self.total = 0

    def drain(self, pipe) -> None:
        try:
            while True:
                chunk = pipe.read(65536)
                if not chunk:
                    return
                self.total += len(chunk)
                remaining = self.limit - len(self.buffer)
                if remaining > 0:
                    self.buffer.extend(chunk[:remaining])
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    @property
    def truncated(self) -> bool:
        return self.total > len(self.buffer)

    def text(self) -> str:
        return bytes(self.buffer).decode("utf-8", errors="replace")


def _validate_env_key(key: str) -> None:
    if not key or "=" in key or "\x00" in key:
        raise ValueError(f"invalid environment variable name: {key!r}")


def _child_env(request: LocalProcessRequest) -> dict[str, str]:
    allowed = SAFE_PARENT_ENV.intersection(request.env_allowlist)
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    for key, value in request.env_overrides.items():
        _validate_env_key(key)
        text = str(value)
        if "\x00" in text:
            raise ValueError(f"environment value contains NUL: {key}")
        env[key] = text
    return env


def _validate_request(request: LocalProcessRequest) -> Path:
    if not request.argv:
        raise ValueError("argv must not be empty")
    for arg in request.argv:
        if not isinstance(arg, str) or not arg or "\x00" in arg:
            raise ValueError(f"invalid argv element: {arg!r}")
    if request.timeout_seconds <= 0 or request.timeout_seconds > 3600:
        raise ValueError("timeout_seconds must be in (0, 3600]")
    if request.terminate_grace_seconds < 0 or request.terminate_grace_seconds > 10:
        raise ValueError("terminate_grace_seconds must be in [0, 10]")
    for name, limit in (
        ("stdout_limit_bytes", request.stdout_limit_bytes),
        ("stderr_limit_bytes", request.stderr_limit_bytes),
    ):
        if limit < 0 or limit > MAX_CAPTURE_BYTES:
            raise ValueError(f"{name} must be in [0, {MAX_CAPTURE_BYTES}]")
    if request.stdin_data is not None:
        if not isinstance(request.stdin_data, bytes):
            raise ValueError("stdin_data must be bytes or None")
        if len(request.stdin_data) > MAX_STDIN_BYTES:
            raise ValueError(f"stdin_data exceeds {MAX_STDIN_BYTES} bytes")
    cwd = require_scoped_path(request.filesystem_root, request.cwd)
    if not cwd.is_dir():
        raise AuthorityViolation(f"process cwd is not a directory: {cwd}")
    return cwd


def _terminate_process_group(proc: subprocess.Popen[bytes], grace_seconds: float) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=max(grace_seconds, 0.1))
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"process group {proc.pid} did not terminate after SIGKILL")


class LocalProcessBackend:
    backend_id = "local"
    adapter_id = "backend-local-process"

    @staticmethod
    def readiness() -> dict[str, object]:
        return {
            "status": "available" if os.name == "posix" else "unavailable",
            "reason": "POSIX process groups available" if os.name == "posix" else "Slice A local backend requires POSIX",
        }

    def execute(self, request: LocalProcessRequest) -> LocalProcessResult:
        if os.name != "posix":
            raise RuntimeError("Slice A LocalProcessBackend requires POSIX process groups")
        cwd = _validate_request(request)
        env = _child_env(request)
        started_at = _now()
        proc = subprocess.Popen(
            list(request.argv),
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE if request.stdin_data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            start_new_session=True,
        )
        assert proc.stdout is not None and proc.stderr is not None
        stdin_thread: Optional[threading.Thread] = None
        if request.stdin_data is not None:
            assert proc.stdin is not None

            def _write_stdin() -> None:
                try:
                    proc.stdin.write(request.stdin_data or b"")
                    proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                finally:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass

            stdin_thread = threading.Thread(target=_write_stdin, daemon=True)
            stdin_thread.start()
        stdout = _BoundedCollector(request.stdout_limit_bytes)
        stderr = _BoundedCollector(request.stderr_limit_bytes)
        threads = [
            threading.Thread(target=stdout.drain, args=(proc.stdout,), daemon=True),
            threading.Thread(target=stderr.drain, args=(proc.stderr,), daemon=True),
        ]
        for thread in threads:
            thread.start()

        timed_out = False
        cancelled = False
        deadline = time.monotonic() + request.timeout_seconds
        while proc.poll() is None:
            if request.cancel_event is not None and request.cancel_event.is_set():
                cancelled = True
                _terminate_process_group(proc, request.terminate_grace_seconds)
                break
            if time.monotonic() >= deadline:
                timed_out = True
                _terminate_process_group(proc, request.terminate_grace_seconds)
                break
            time.sleep(0.01)

        if proc.poll() is None:
            proc.wait()
        for thread in threads:
            thread.join(timeout=max(request.terminate_grace_seconds, 0.5) + 1.0)
            if thread.is_alive():
                raise RuntimeError("process output reader did not terminate")
        if stdin_thread is not None:
            stdin_thread.join(timeout=max(request.terminate_grace_seconds, 0.5) + 1.0)
            if stdin_thread.is_alive():
                raise RuntimeError("process stdin writer did not terminate")

        return LocalProcessResult(
            exit_code=proc.returncode,
            stdout=stdout.text(),
            stderr=stderr.text(),
            stdout_total_bytes=stdout.total,
            stderr_total_bytes=stderr.total,
            stdout_truncated=stdout.truncated,
            stderr_truncated=stderr.truncated,
            started_at=started_at,
            completed_at=_now(),
            pid=proc.pid,
            process_group_id=proc.pid,
            timed_out=timed_out,
            cancelled=cancelled,
        )
