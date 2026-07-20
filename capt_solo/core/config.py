"""Runtime configuration and path resolution.

CAPT Solo is fully portable: all state lives under a single root directory
(default ``~/.capt-solo``). No environment variables are required, but
``CAPT_SOLO_HOME`` may override the root for testing or relocation.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_HOME = Path(os.path.expanduser("~")) / ".capt-solo"


def home_dir() -> Path:
    """Return the CAPT Solo root directory (honours ``CAPT_SOLO_HOME``)."""
    override = os.environ.get("CAPT_SOLO_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_HOME


def data_dir() -> Path:
    return home_dir() / "data"


def memory_db_path() -> Path:
    return data_dir() / "memory.db"


def ctp_journal_dir() -> Path:
    return data_dir() / "ctp"


def khsb_dir() -> Path:
    return data_dir() / "khsb"


def backup_dir() -> Path:
    return home_dir() / "backups"


def ensure_dirs() -> None:
    """Create all runtime directories if missing. Idempotent."""
    for d in (home_dir(), data_dir(), ctp_journal_dir(), khsb_dir(), backup_dir()):
        d.mkdir(parents=True, exist_ok=True)


def reset_paths_for_test(home: Path) -> None:
    """Test helper: point the runtime at a temporary root."""
    os.environ["CAPT_SOLO_HOME"] = str(home)
    ensure_dirs()
