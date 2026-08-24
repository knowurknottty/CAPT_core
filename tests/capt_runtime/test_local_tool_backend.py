from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.local import (
    LocalProcessBackend,
    LocalProcessRequest,
)
from capt_runtime.tools.scope import require_scoped_path


def test_symlink_cwd_escape_is_denied(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AuthorityViolation):
        require_scoped_path(root, root / "escape")


def test_write_target_through_symlink_parent_escape_is_denied(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AuthorityViolation):
        require_scoped_path(root, root / "escape" / "x.txt", for_write=True)


def _request(tmp_path: Path, argv: list[str], **kw) -> LocalProcessRequest:
    return LocalProcessRequest(
        argv=tuple(argv), cwd=tmp_path, filesystem_root=tmp_path,
        timeout_seconds=kw.pop("timeout_seconds", 5.0),
        stdout_limit_bytes=kw.pop("stdout_limit_bytes", 4096),
        stderr_limit_bytes=kw.pop("stderr_limit_bytes", 4096),
        **kw,
    )


def test_stdout_and_stderr_are_bounded_while_drained(tmp_path: Path) -> None:
    backend = LocalProcessBackend()
    code = "import sys; sys.stdout.write('x'*200000); sys.stderr.write('y'*150000)"
    result = backend.execute(_request(tmp_path, [sys.executable, "-c", code]))
    assert len(result.stdout.encode("utf-8")) <= 4096
    assert len(result.stderr.encode("utf-8")) <= 4096
    assert result.stdout_total_bytes >= 200000
    assert result.stderr_total_bytes >= 150000
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    assert result.exit_code == 0


def test_parent_secret_is_not_inherited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAPT_TEST_SECRET_TOKEN", "should-not-leak")
    backend = LocalProcessBackend()
    code = "import os; print(os.getenv('CAPT_TEST_SECRET_TOKEN'))"
    result = backend.execute(_request(tmp_path, [sys.executable, "-c", code]))
    assert result.stdout.strip() == "None"


def test_timeout_kills_descendant_process_group(tmp_path: Path) -> None:
    backend = LocalProcessBackend()
    marker = tmp_path / "child-survived.txt"
    child = (
        "import time; from pathlib import Path; "
        f"time.sleep(0.5); Path({str(marker)!r}).write_text('survived')"
    )
    parent = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}]); "
        "time.sleep(30)"
    )
    started = time.monotonic()
    result = backend.execute(_request(
        tmp_path, [sys.executable, "-c", parent], timeout_seconds=0.15,
    ))
    assert result.timed_out is True
    assert time.monotonic() - started < 2.0
    time.sleep(0.65)
    assert not marker.exists()


def test_cancellation_kills_process_and_returns_cancelled(tmp_path: Path) -> None:
    backend = LocalProcessBackend()
    cancel = threading.Event()
    timer = threading.Timer(0.1, cancel.set)
    timer.start()
    try:
        result = backend.execute(_request(
            tmp_path, [sys.executable, "-c", "import time; time.sleep(30)"],
            cancel_event=cancel,
        ))
    finally:
        timer.cancel()
    assert result.cancelled is True
    assert result.timed_out is False


def test_local_backend_can_send_bounded_stdin_without_inheriting_terminal(tmp_path: Path) -> None:
    backend = LocalProcessBackend()
    payload = b"CAPT_STDIN_OK\n"
    result = backend.execute(
        LocalProcessRequest(
            argv=(sys.executable, "-c", "import sys; data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data)"),
            cwd=tmp_path,
            filesystem_root=tmp_path,
            stdin_data=payload,
        )
    )
    assert result.exit_code == 0
    assert result.stdout == payload.decode()


def test_local_backend_rejects_oversized_stdin_before_dispatch(tmp_path: Path) -> None:
    backend = LocalProcessBackend()
    with pytest.raises(ValueError, match="stdin_data exceeds"):
        backend.execute(
            LocalProcessRequest(
                argv=(sys.executable, "-c", "print('must not run')"),
                cwd=tmp_path,
                filesystem_root=tmp_path,
                stdin_data=b"x" * (1024 * 1024 + 1),
            )
        )
