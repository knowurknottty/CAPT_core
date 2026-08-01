"""Runner lifecycle + authenticated READY handshake.

Launches the canonical CAPT Agent Runner as a supervised subprocess and accepts
readiness **only** from an authenticated local socket channel.

Hard rules enforced here:

* ``shell=False`` always; argv is a list; no model-controlled strings reach it.
* the parent environment is not inherited wholesale (see ``resolver.runner_env``).
* the launch nonce travels in the environment, never in argv (``ps`` safety).
* the socket lives in a ``0700`` directory and is checked for uid ownership.
* readiness is a structured, digest-checked, nonce-authenticated event — never a
  log-line substring, never model text, never a hand-written file.
* the runner gets its own process group so cancellation reaches the whole tree.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from capt_solo.bridge.contracts import (
    BLOCK_READY_MALFORMED,
    BLOCK_READY_NOT_RECEIVED,
    BLOCK_RUNNER_DIED,
    BLOCK_RUNNER_START_FAILED,
    BLOCK_RUNNER_TIMEOUT,
    BridgeReadyEvent,
)
from capt_solo.bridge.lease import (
    DuplicateRunnerError,
    acquire_runner_lease,
    read_held_lease,
    refresh_lease,
    release_runner_lease,
)
from capt_solo.bridge.protocol import (
    BridgeConnectionDescriptor,
    make_auth_token,
)
from capt_solo.bridge.resolver import CaptSource, redact_argv, runner_env

DEFAULT_STARTUP_TIMEOUT_S = 90.0
_MAX_CAPTURED_BYTES = 64 * 1024  # bounded stdout/stderr


@dataclass
class RunnerHandle:
    """A live (or terminated) runner and everything proven about it."""

    argv: Tuple[str, ...]
    pid: int = 0
    pgid: int = 0
    socket_path: str = ""
    turn_socket_path: str = ""
    runtime_id: str = ""
    runtime_generation: int = 0
    turn_auth: str = ""
    ready_event: Optional[BridgeReadyEvent] = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    exit_code: Optional[int] = None
    block_codes: Tuple[str, ...] = ()
    block_reason: str = ""
    notes: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def ready(self) -> bool:
        return self.ready_event is not None and not self.block_codes


class _ReadyListener:
    """Single-connection unix-socket listener for the READY event.

    AF_UNIX paths are limited to ~104 bytes on macOS (108 on Linux). A deep
    workspace path silently overflows that limit, so when the preferred
    workspace-scoped directory would produce an over-long path we fall back to a
    private ``mkdtemp`` directory. Both locations are 0700 and owner-checked;
    the socket is ephemeral IPC, not durable CAPT state.
    """

    _MAX_SOCKET_PATH = 100

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        name = f"ready-{secrets.token_hex(8)}.sock"
        self._ephemeral_dir: Optional[str] = None
        if len(str(directory / name)) > self._MAX_SOCKET_PATH:
            directory = Path(tempfile.mkdtemp(prefix="capt-br-"))
            os.chmod(directory, 0o700)
            self._ephemeral_dir = str(directory)
        self._dir = directory
        self.path = str(directory / name)
        self._srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._srv.bind(self.path)
        os.chmod(self.path, 0o600)
        self._srv.listen(1)
        self._payload: Optional[bytes] = None
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()

    def _accept(self) -> None:
        try:
            conn, _ = self._srv.accept()
        except Exception:
            return
        try:
            chunks: List[bytes] = []
            total = 0
            conn.settimeout(10.0)
            while total < _MAX_CAPTURED_BYTES:
                data = conn.recv(8192)
                if not data:
                    break
                chunks.append(data)
                total += len(data)
            self._payload = b"".join(chunks)
        except Exception:
            self._payload = None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def secure(self) -> bool:
        """Directory 0700 and socket owned by this uid."""
        try:
            dst = os.stat(self._dir)
            sst = os.stat(self.path)
        except OSError:
            return False
        return (
            dst.st_uid == os.getuid()
            and (dst.st_mode & 0o077) == 0
            and sst.st_uid == os.getuid()
        )

    def poll(self) -> Optional[bytes]:
        return self._payload

    def close(self) -> None:
        try:
            self._srv.close()
        except Exception:
            pass
        try:
            os.unlink(self.path)
        except OSError:
            pass
        if self._ephemeral_dir:
            try:
                os.rmdir(self._ephemeral_dir)
            except OSError:
                pass


def _lock_path(workspace: Path, mission_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in mission_id)
    return workspace / ".capt" / "bridge" / f"runner-{safe}.lease"


def _lock_path_local(workspace: Path, mission_id: str) -> Path:
    return _lock_path(workspace, mission_id)


def _rewrite_lease(lock: Path, lease) -> None:
    """Atomically rewrite the lease with updated pid/pgid (rename over)."""
    import json as _json

    data = _json.dumps(lease.to_dict(), sort_keys=True).encode("utf-8")
    tmp = lock.with_name(f"{lock.name}.upd.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(str(tmp), str(lock))
    os.chmod(lock, 0o600)


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


def _make_connection_descriptor(
    *,
    runtime_id: str,
    runtime_generation: int,
    mission_id: str,
    session_id: str,
    turn_socket: str,
    auth_token: str,
    ttl_s: float = 3600.0,
) -> BridgeConnectionDescriptor:
    now = time.time()
    return BridgeConnectionDescriptor(
        protocol_version=1,
        runtime_id=runtime_id,
        runtime_generation=runtime_generation,
        mission_id=mission_id,
        session_id=session_id,
        socket_path=turn_socket,
        auth_token=auth_token,
        issued_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        expires_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + ttl_s)),
    )


def _tail(path: Path, limit: int = _MAX_CAPTURED_BYTES) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) > limit:
        data = data[-limit:]
    return data.decode("utf-8", errors="replace")


def launch_runner(
    source: CaptSource,
    *,
    workspace: Path,
    mission_id: str,
    resume: bool = True,
    timeout_s: float = DEFAULT_STARTUP_TIMEOUT_S,
    session_id: str = "",
) -> RunnerHandle:
    """Launch and supervise the canonical runner until READY, timeout, or death."""
    if not mission_id:
        return RunnerHandle(
            argv=(),
            block_codes=("MISSION_REQUIRED",),
            block_reason="explicit mission id is required; the bridge never guesses",
        )

    # The runner is launched as the bridge serve loop: it boots through
    # canonical CAPT governance, emits the authenticated READY event, and then
    # serves governed turns. ``--json`` is a TOP-LEVEL flag in the real CLI.
    argv: List[str] = [
        *source.launch_argv,
        "--json",
        "bridge",
        "serve",
        "--workspace",
        str(workspace),
        "--mission",
        mission_id,
        "--mode",
        "resume" if resume else "start",
    ]
    if session_id:
        argv += ["--session", session_id]

    # The bridge assigns the runtime identity + generation up front so the lease,
    # the connection descriptor, and the runner all agree on authority. The
    # runner reads these from the environment and adopts them (it does not mint
    # its own conflicting identity).
    runtime_id = secrets.token_hex(16)
    runtime_generation = 1

    try:
        lease = acquire_runner_lease(
            workspace,
            mission_id,
            runtime_id=runtime_id,
            runtime_generation=runtime_generation,
            pid=0,  # filled after Popen; lease re-written below
            pgid=0,
            session_id=session_id,
        )
    except DuplicateRunnerError as exc:
        return RunnerHandle(
            argv=redact_argv(argv),
            block_codes=("DUPLICATE_RUNNER",),
            block_reason=str(exc),
        )

    base = workspace / ".capt" / "bridge"
    listener = _ReadyListener(base / "sock")
    if not listener.secure():
        listener.close()
        release_runner_lease(workspace, mission_id, lease=lease)
        return RunnerHandle(
            argv=redact_argv(argv),
            block_codes=(BLOCK_RUNNER_START_FAILED,),
            block_reason="READY channel directory is not private (0700, owner-only)",
        )

    nonce = secrets.token_hex(32)
    # Same AF_UNIX length constraint as the READY socket: co-locate the turn
    # socket with the (possibly relocated) listener directory.
    turn_socket = str(Path(listener.path).parent / f"turn-{secrets.token_hex(8)}.sock")
    turn_auth = make_auth_token()
    descriptor = _make_connection_descriptor(
        runtime_id=runtime_id,
        runtime_generation=runtime_generation,
        mission_id=mission_id,
        session_id=session_id,
        turn_socket=turn_socket,
        auth_token=turn_auth,
    )
    env = runner_env(
        nonce,
        listener.path,
        extra={
            "CAPT_BRIDGE_TURN_SOCKET": turn_socket,
            "CAPT_BRIDGE_TURN_AUTH": turn_auth,
            "CAPT_BRIDGE_RUNTIME_ID": runtime_id,
            "CAPT_BRIDGE_RUNTIME_GENERATION": str(runtime_generation),
        },
    )

    out_f = tempfile.NamedTemporaryFile(
        prefix="capt-runner-out-", suffix=".log", delete=False
    )
    err_f = tempfile.NamedTemporaryFile(
        prefix="capt-runner-err-", suffix=".log", delete=False
    )
    out_path, err_path = Path(out_f.name), Path(err_f.name)

    try:
        proc = subprocess.Popen(  # noqa: S603 - argv list, shell=False, fixed program
            argv,
            stdout=out_f,
            stderr=err_f,
            stdin=subprocess.DEVNULL,
            cwd=str(source.root),
            env=env,
            shell=False,
            start_new_session=True,  # own process group for signal propagation
            close_fds=True,
        )
    except Exception as exc:
        out_f.close()
        err_f.close()
        listener.close()
        return RunnerHandle(
            argv=redact_argv(argv),
            block_codes=(BLOCK_RUNNER_START_FAILED,),
            block_reason=f"failed to start runner: {type(exc).__name__}: {exc}",
        )

    try:
        pgid = os.getpgid(proc.pid)
    except Exception:
        pgid = proc.pid

    # Re-write the lease with the real pid/pgid (atomic rename inside lease).
    lease.pid = proc.pid
    lease.pgid = pgid
    from capt_solo.bridge.lease import _read_lease  # local import to avoid cycle

    lock = _lock_path_local(workspace, mission_id)
    _rewrite_lease(lock, lease)

    handle = RunnerHandle(
        argv=redact_argv(argv),
        pid=proc.pid,
        pgid=pgid,
        socket_path=listener.path,
        turn_socket_path=turn_socket,
        runtime_id=runtime_id,
        runtime_generation=runtime_generation,
        turn_auth=turn_auth,
    )

    def _finish(codes: Tuple[str, ...], reason: str) -> RunnerHandle:
        out_f.flush()
        err_f.flush()
        handle.stdout_tail = _tail(out_path)
        handle.stderr_tail = _tail(err_path)
        handle.block_codes = codes
        handle.block_reason = reason
        handle.exit_code = proc.poll()
        listener.close()
        for f in (out_f, err_f):
            try:
                f.close()
            except Exception:
                pass
        for p in (out_path, err_path):
            try:
                p.unlink()
            except OSError:
                pass
        if codes:
            terminate_runner(handle)
            release_runner_lease(workspace, mission_id, lease=lease)
        return handle

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        payload = listener.poll()
        if payload:
            try:
                data = json.loads(payload.decode("utf-8"))
            except Exception as exc:
                return _finish(
                    (BLOCK_READY_MALFORMED,), f"READY payload is not valid JSON: {exc}"
                )
            if not isinstance(data, dict):
                return _finish((BLOCK_READY_MALFORMED,), "READY payload is not an object")
            event = BridgeReadyEvent.from_mapping(data)
            ok, codes, reason = event.validate(
                expected_nonce=nonce,
                expected_mission_id=mission_id,
                expected_pid=proc.pid,
            )
            if not ok:
                return _finish(codes, reason)
            handle.ready_event = event
            out_f.flush()
            err_f.flush()
            handle.stdout_tail = _tail(out_path)
            handle.stderr_tail = _tail(err_path)
            listener.close()
            return handle
        if proc.poll() is not None:
            return _finish(
                (BLOCK_RUNNER_DIED,),
                f"runner exited with code {proc.returncode} before emitting READY",
            )
        time.sleep(0.05)

    return _finish(
        (BLOCK_RUNNER_TIMEOUT,),
        f"runner did not emit a validated READY event within {timeout_s:g}s",
    )


def terminate_runner(handle: RunnerHandle, *, grace_s: float = 5.0) -> None:
    """Signal the runner's whole process group, then escalate."""
    if not handle.pid:
        return
    target = handle.pgid or handle.pid
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(target, sig)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(handle.pid, sig)
            except (ProcessLookupError, PermissionError, OSError):
                return
        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            if not _live_pid(handle.pid):
                return
            time.sleep(0.05)


def runner_alive(handle: RunnerHandle) -> bool:
    return _live_pid(handle.pid)


def emit_ready_event(event: BridgeReadyEvent) -> Tuple[bool, str]:
    """Runner-side: send a READY event over the bridge channel.

    Called from inside the canonical runner. The nonce is read from the
    environment the bridge supplied; it is never logged or echoed.
    """
    sock_path = os.environ.get("CAPT_BRIDGE_SOCKET", "")
    nonce = os.environ.get("CAPT_BRIDGE_NONCE", "")
    if not sock_path or not nonce:
        return False, "no bridge channel in environment"
    event.bridge_nonce = nonce
    event.runner_pid = os.getpid()
    event.with_digest()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10.0)
            s.connect(sock_path)
            s.sendall(
                json.dumps(
                    {**event.__dict__, "bridge_nonce": nonce}, sort_keys=True, default=str
                ).encode("utf-8")
            )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, ""
