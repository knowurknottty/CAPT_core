"""CAPT-UPG-030: the local terminal backend must reap its whole process group.

Before the fix, a background child (``cmd &``) survived its leader's exit, kept
the stdout pipe open, made the run fail with "output reader did not terminate"
and kept running outside any governance.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from capt_runtime.tools.backends.local import LocalProcessBackend, LocalProcessRequest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX process groups required")


def _group_alive(pgid: int) -> bool:
    """Live (non-zombie) members of the group; zombies cannot run."""
    proc = Path("/proc")
    if (proc / "self" / "stat").exists():
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "stat").read_text(encoding="ascii", errors="replace")
            except OSError:
                continue
            tail = raw[raw.rfind(")") + 2:].split()
            if len(tail) >= 3 and tail[2] == str(pgid) and tail[0] != "Z":
                return True
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_group_gone(pgid: int, seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _group_alive(pgid):
            return True
        time.sleep(0.02)
    return not _group_alive(pgid)


def test_background_child_is_terminated_and_output_is_kept(tmp_path: Path) -> None:
    started = time.monotonic()
    result = LocalProcessBackend().execute(LocalProcessRequest(
        argv=("sh", "-c", "sleep 30 & echo started"),
        cwd=tmp_path, filesystem_root=tmp_path, timeout_seconds=10,
        terminate_grace_seconds=0.5,
    ))
    assert result.exit_code == 0
    assert result.stdout.strip() == "started"
    assert result.descendants_terminated is True
    assert time.monotonic() - started < 5
    assert _wait_group_gone(result.process_group_id)


def test_child_ignoring_sigterm_is_killed(tmp_path: Path) -> None:
    result = LocalProcessBackend().execute(LocalProcessRequest(
        argv=("sh", "-c", "(trap '' TERM; sleep 30) & echo started"),
        cwd=tmp_path, filesystem_root=tmp_path, timeout_seconds=10,
        terminate_grace_seconds=0.3,
    ))
    assert result.exit_code == 0
    assert result.descendants_terminated is True
    assert _wait_group_gone(result.process_group_id)


def test_clean_run_reports_no_descendants(tmp_path: Path) -> None:
    result = LocalProcessBackend().execute(LocalProcessRequest(
        argv=("sh", "-c", "echo ok"), cwd=tmp_path, filesystem_root=tmp_path,
    ))
    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"
    assert result.descendants_terminated is False
