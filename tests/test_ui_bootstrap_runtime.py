"""Regression tests for the UI operator runtime bootstrap.

The UI surfaces (TUI, desktop, operator CLI) connect to the CAPT runtime via
``capt_ui.operator.bootstrap.resolve_runtime``. That resolver MUST agree with
the canonical on-ramp path layout produced by ``capt start``
(``capt_runtime.cli_ramp.default_paths``): socket ``runtime.sock`` and token
``runtime.token`` under the same state dir.

Regression: the resolver previously looked for a non-canonical ``token.txt``
filename, which is never written by ``capt start``, so ``capt-ui status`` could
not connect to a running runtime. This test pins the canonical token filename.
"""

import os
import tempfile
from pathlib import Path

import pytest

from capt_ui.operator.bootstrap import resolve_runtime


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Isolate the resolver from any ambient CAPT_* env vars."""
    for k in ("CAPT_STATE_DIR", "CAPT_SOLO_HOME", "CAPT_SOCK", "CAPT_TOKEN"):
        monkeypatch.delenv(k, raising=False)


def test_resolve_runtime_uses_canonical_token_filename(tmp_path, monkeypatch):
    """resolve_runtime must find the runtime token written as runtime.token,
    matching capt_runtime.cli_ramp.default_paths()."""
    monkeypatch.setenv("CAPT_STATE_DIR", str(tmp_path))
    # Simulate a runtime started by `capt start` on the canonical pattern.
    (tmp_path / "runtime.sock").touch()
    (tmp_path / "runtime.token").write_text("test-token")

    sock, token = resolve_runtime()
    assert sock == str(tmp_path / "runtime.sock")
    assert token == str(tmp_path / "runtime.token")


def test_resolve_runtime_not_fooled_by_noncanonical_token_file(tmp_path, monkeypatch):
    """A stray token.txt (old, non-canonical layout) must not be used as the
    runtime token. The canonical on-ramp writes runtime.token."""
    monkeypatch.setenv("CAPT_STATE_DIR", str(tmp_path))
    (tmp_path / "runtime.sock").touch()
    (tmp_path / "token.txt").write_text("stale")

    sock, token = resolve_runtime()
    assert sock == str(tmp_path / "runtime.sock")
    # canonical token file absent -> the resolver must not silently pick token.txt
    assert token == str(tmp_path / "runtime.token")


def test_resolve_runtime_returns_none_without_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_STATE_DIR", str(tmp_path))
    assert resolve_runtime() == (None, None)