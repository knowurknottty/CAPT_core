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

import os
import socket
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
    """Return True if a runtime service is reachable at the socket."""
    if not sock.exists():
        return False
    _sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        _sock.settimeout(0.3)
        _sock.connect(str(sock))
        return True
    except OSError:
        return False
    finally:
        try:
            _sock.close()
        except OSError:
            pass
