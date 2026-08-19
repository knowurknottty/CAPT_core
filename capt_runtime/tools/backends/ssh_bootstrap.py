"""Fixed remote bootstrap used by the SSH backend.

The bootstrap is transmitted as trusted code in the SSH command string. User
argv/cwd data is sent separately as JSON on stdin and never interpolated into
that shell-parsed command string.
"""
from __future__ import annotations

import base64
import shlex

REMOTE_BOOTSTRAP_SOURCE = r'''
import base64
import json
import os
import signal
import subprocess
import sys
import threading
import time

PROTOCOL = "capt-ssh-exec-v1"
SAFE_ENV = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TERM")


def emit(payload):
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    sys.stdout.write("\n")
    sys.stdout.flush()


def deny(reason):
    emit({"protocol": PROTOCOL, "status": "denied", "reason": str(reason)[:4096]})
    raise SystemExit(0)


def indeterminate(reason, pid=None, pgid=None):
    emit({
        "protocol": PROTOCOL,
        "status": "indeterminate",
        "reason": str(reason)[:4096],
        "remotePid": pid,
        "remoteProcessGroupId": pgid,
    })
    raise SystemExit(0)


class Collector:
    def __init__(self, limit):
        self.limit = limit
        self.buffer = bytearray()
        self.total = 0

    def drain(self, pipe):
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


def terminate_group(proc, grace):
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=max(grace, 0.1))


def bounded_int(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int):
        deny(name + " must be an integer")
    if value < minimum or value > maximum:
        deny(name + " out of bounds")
    return value


try:
    request = json.load(sys.stdin)
except Exception as exc:
    deny("invalid request JSON: " + type(exc).__name__)

argv = request.get("argv")
if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x and "\x00" not in x for x in argv):
    deny("argv must be a non-empty array of strings")
if len(argv) > 1024 or sum(len(x.encode("utf-8")) for x in argv) > 65536:
    deny("argv exceeds remote bounds")

root_raw = request.get("filesystemRoot")
cwd_raw = request.get("cwd")
if not isinstance(root_raw, str) or not root_raw.startswith("/") or "\x00" in root_raw:
    deny("filesystemRoot must be an absolute path")
if not isinstance(cwd_raw, str) or not cwd_raw.startswith("/") or "\x00" in cwd_raw:
    deny("cwd must be an absolute path")
root = os.path.realpath(root_raw)
cwd = os.path.realpath(cwd_raw)
try:
    if os.path.commonpath([root, cwd]) != root:
        deny("remote cwd escapes admitted filesystem root")
except ValueError:
    deny("remote cwd escapes admitted filesystem root")
if not os.path.isdir(cwd):
    deny("remote cwd is not a directory")

timeout_ms = bounded_int(request.get("timeoutMs", 30000), "timeoutMs", 1, 3600000)
stdout_limit = bounded_int(request.get("stdoutLimitBytes", 1048576), "stdoutLimitBytes", 0, 4194304)
stderr_limit = bounded_int(request.get("stderrLimitBytes", 1048576), "stderrLimitBytes", 0, 4194304)
grace_ms = bounded_int(request.get("terminateGraceMs", 500), "terminateGraceMs", 0, 10000)
env = {key: os.environ[key] for key in SAFE_ENV if key in os.environ}

proc = None
try:
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        close_fds=True,
        start_new_session=True,
    )
    stdout = Collector(stdout_limit)
    stderr = Collector(stderr_limit)
    threads = [
        threading.Thread(target=stdout.drain, args=(proc.stdout,), daemon=True),
        threading.Thread(target=stderr.drain, args=(proc.stderr,), daemon=True),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    deadline = time.monotonic() + timeout_ms / 1000.0
    while proc.poll() is None:
        if time.monotonic() >= deadline:
            timed_out = True
            terminate_group(proc, grace_ms / 1000.0)
            break
        time.sleep(0.01)
    if proc.poll() is None:
        proc.wait()
    for thread in threads:
        thread.join(timeout=max(grace_ms / 1000.0, 0.5) + 1.0)
        if thread.is_alive():
            indeterminate("remote output collector did not terminate", proc.pid, proc.pid)
    emit({
        "protocol": PROTOCOL,
        "status": "completed",
        "exitCode": proc.returncode,
        "stdoutB64": base64.b64encode(bytes(stdout.buffer)).decode("ascii"),
        "stderrB64": base64.b64encode(bytes(stderr.buffer)).decode("ascii"),
        "stdoutTotalBytes": stdout.total,
        "stderrTotalBytes": stderr.total,
        "stdoutTruncated": stdout.total > len(stdout.buffer),
        "stderrTruncated": stderr.total > len(stderr.buffer),
        "timedOut": timed_out,
        "remotePid": proc.pid,
        "remoteProcessGroupId": proc.pid,
        "remoteCwd": cwd,
    })
except SystemExit:
    raise
except Exception as exc:
    if proc is not None:
        try:
            terminate_group(proc, grace_ms / 1000.0)
        except Exception:
            pass
        indeterminate("remote bootstrap failed after process start: " + type(exc).__name__, proc.pid, proc.pid)
    deny("remote bootstrap failed before process start: " + type(exc).__name__)
'''


def bootstrap_command(remote_python: str) -> str:
    """Return a shell-parsed command containing trusted constants only."""
    payload = base64.b64encode(REMOTE_BOOTSTRAP_SOURCE.encode("utf-8")).decode("ascii")
    decoder = f'import base64;exec(base64.b64decode("{payload}"))'
    return f"{shlex.quote(remote_python)} -c {shlex.quote(decoder)}"
