"""Robust Node.js binary discovery for cross-language parity checks.

The CAPT runtime has NO JavaScript runtime dependency. Node is only needed by
the conformance suite to prove that the generated TypeScript bindings validate
fixtures identically to the generated Python bindings. This helper makes that
discovery explicit and portable without hard-coding a username or silently
passing when Node is unavailable.

Resolution order (preference per mission Part 2):
  1. Explicit override via CAPT_NODE_BIN (validated, must exist, must not be a
     shell string — we resolve a real file, never execute arbitrary commands).
  2. PATH resolution via shutil.which("node").
  3. A small, documented list of standard local binary locations, tried only
     when PATH resolution fails.
  4. None — caller should skip with an actionable reason.

No shell is ever spawned to "find" node; we only ever pass the resolved
absolute path to subprocess.run, so the resolver cannot execute arbitrary
commands.
"""

from __future__ import annotations

import os
import shutil
from typing import List, Optional

# Documented fallback locations. These are STANDARD install prefixes only;
# the current username is intentionally NOT hard-coded here.
_STANDARD_LOCATIONS = (
    "/usr/local/bin/node",
    "/usr/bin/node",
    "/opt/homebrew/bin/node",
    os.path.expanduser("~/.local/bin/node"),
    os.path.expanduser("~/.npm-global/bin/node"),
)


def _is_executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def discover_node_bin(extra_locations: Optional[List[str]] = None) -> Optional[str]:
    """Return an absolute path to a node executable, or None if not found.

    Never executes arbitrary shell commands. The CAPT_NODE_BIN override is
    validated as a real existing executable file; a non-existent or
    non-executable override returns None so the caller can report it.
    """
    override = os.environ.get("CAPT_NODE_BIN")
    if override:
        # Resolve and validate; reject anything that is not a real file we can
        # execute. We do NOT run it here — only return the path.
        if _is_executable(override):
            return os.path.abspath(override)
        return None

    found = shutil.which("node")
    if found and _is_executable(found):
        return os.path.abspath(found)

    candidates = list(_STANDARD_LOCATIONS)
    if extra_locations:
        candidates = candidates + list(extra_locations)
    for candidate in candidates:
        if _is_executable(candidate):
            return os.path.abspath(candidate)
    return None


def require_node_bin(extra_locations: Optional[List[str]] = None) -> str:
    """Return a node path or raise FileNotFoundError with an actionable message."""
    node = discover_node_bin(extra_locations)
    if node is None:
        override_hint = os.environ.get("CAPT_NODE_BIN")
        if override_hint:
            raise FileNotFoundError(
                "CAPT_NODE_BIN=%r is not an executable file. Set it to a real "
                "node binary or ensure 'node' is on PATH." % override_hint
            )
        raise FileNotFoundError(
            "Node.js not found on PATH or in standard locations. Install Node, "
            "add it to PATH, or set CAPT_NODE_BIN to the absolute path of the "
            "node executable. The CAPT runtime itself has no JavaScript "
            "dependency; Node is only required for cross-language parity checks."
        )
    return node
