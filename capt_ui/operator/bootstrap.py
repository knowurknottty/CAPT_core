"""Runtime path / connection bootstrap for UI surfaces.

Resolves the authenticated runtime socket + token from the environment or a
well-known default state dir. This is path resolution only — the runtime
service itself is external authority and is not launched or re-implemented
here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple


def default_state_dir() -> Path:
    override = os.environ.get("CAPT_STATE_DIR") or os.environ.get("CAPT_SOLO_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".capt"


def resolve_runtime() -> tuple:
    """Return (sock_path, token_file) for the local runtime.

    Resolution order:
      1. explicit CAPT_SOCK / CAPT_TOKEN env vars
      2. default state dir (runtime.sock / token.txt)
      3. None if not determinable
    """
    sock = os.environ.get("CAPT_SOCK")
    token = os.environ.get("CAPT_TOKEN")
    if sock and token:
        return sock, token
    state = default_state_dir()
    sock_path = state / "runtime.sock"
    token_file = state / "token.txt"
    if sock_path.exists() and token_file.exists():
        return str(sock_path), str(token_file)
    # allow just a sock if token is stored there too
    if sock_path.exists():
        return str(sock_path), str(token_file)
    return None, None


def runtime_available() -> bool:
    sock, token = resolve_runtime()
    return bool(sock and token)