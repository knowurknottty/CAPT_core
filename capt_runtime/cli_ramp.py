#!/usr/bin/env python3
"""CAPT CLI on-ramp helpers (P0 onboarding).

Provides the normal-human default lifecycle surface:

    capt start      start the governed runtime with sensible defaults
    capt status     report runtime health and version
    capt stop       stop the running runtime
    capt doctor     diagnose the local environment
    capt evidence   show a human-readable evidence/verification view

These are thin convenience wrappers over the existing RuntimeService. They do
NOT introduce new architecture: `capt harness ...` remains the full expert
surface, and authority stays in RuntimeService.
"""
from __future__ import annotations

import json
import os
import socket
import stat
import struct
from pathlib import Path
from typing import Dict


def default_state_dir() -> Path:
    """Return the default directory for CAPT runtime local state.

    Resolution order:
      1. $CAPT_STATE_DIR (explicit override)
      2. ~/.capt (per-user default)
    """
    override = os.environ.get("CAPT_STATE_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".capt"


def default_paths() -> Dict[str, Path]:
    """Return default ledger/socket/token paths for a local runtime."""
    d = default_state_dir()
    return {
        "state_dir": d,
        "ledger": d / "runtime.db",
        "sock": d / "runtime.sock",
        "token": d / "runtime.token",
        "pid": d / "runtime.pid",
    }


def is_running(sock: Path) -> bool:
    """Check RuntimeService *authenticated* IPC instead of a bare socket probe.

    The old connect-then-close health check generated a security rejection
    on every status call; the once-per-minute goal watchdog multiplied this
    into thousands of false unauthenticated_ipc_attempt audit records.
    """
    sock = Path(sock)
    token_file = sock.with_name("runtime.token")
    if not sock.is_socket() or not token_file.is_file():
        return False
    try:
        meta = token_file.stat()
        if meta.st_uid != os.getuid() or meta.st_mode & 0o077 or not stat.S_ISREG(meta.st_mode):
            return False
        token = token_file.read_text(encoding="utf-8").strip()
        if not token:
            return False
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(1.0)
            conn.connect(str(sock))
            packet = json.dumps({"token":token},separators=(",",":")).encode("utf-8")
            conn.sendall(struct.pack(">I",len(packet))+packet)
            def exact(n):
                data=bytearray()
                while len(data)<n:
                    fragment=conn.recv(n-len(data))
                    if not fragment:
                        raise OSError("runtime authentication handshake incomplete")
                    data.extend(fragment)
                return bytes(data)
            length = struct.unpack(">I",exact(4))[0]
            if not 1 <= length <= 65536:
                return False
            response=json.loads(exact(length))
            return isinstance(response,dict) and response.get("ok") is True and response.get("authenticated") is True
    except (OSError,ValueError,UnicodeError,struct.error):
        return False
