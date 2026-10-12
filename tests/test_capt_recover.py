from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capt_recover.py"
spec = importlib.util.spec_from_file_location("capt_recover", SCRIPT)
assert spec and spec.loader
capt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capt)


def test_missing_profile_is_not_provisioned(tmp_path: Path):
    assert capt.local_runtime(tmp_path)["state"] == "not_installed"


def test_local_socket_probe_checks_live_accept(tmp_path: Path):
    path = tmp_path / "actual.sock"
    assert not capt.is_live(str(path))
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    server.listen(1)
    try:
        assert capt.is_live(str(path))
        incoming, _ = server.accept()
        incoming.close()
    finally:
        server.close()


def test_headless_refresh_refuses_before_mutation(tmp_path: Path):
    candidate = tmp_path / "absent-config.json"
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--recover", "--config", str(candidate)],
        input="", capture_output=True, text=True, timeout=12, check=False
    )
    assert p.returncode == 2
    assert "requires physical operator terminal" in p.stderr
    assert not candidate.exists()
    assert not (tmp_path / ".capt-refresh.lock").exists()
