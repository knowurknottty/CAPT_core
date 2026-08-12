"""Headless tests for the CAPT Desktop surface (Phase 6).

The desktop surface is framework-agnostic (view-model over the shared operator
layer) so it can be verified headless and later driven by a SwiftUI client.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capt_ui.operator.providers import ProviderManager  # noqa: E402
from capt_ui.operator.models import ModelManager  # noqa: E402
from capt_ui.surfaces.desktop.surface import DesktopSurface  # noqa: E402


def test_sidebar_shape(cfg):
    surf = DesktopSurface()
    items = surf.sidebar_items()
    names = [n for n, _ in items]
    for expected in ("Sessions", "Missions", "Memory", "Providers", "Evidence"):
        assert expected in names


def test_inspector_shape(cfg):
    surf = DesktopSurface()
    insp = surf.inspector()
    for k in ("current model", "provider", "mission", "checkpoint", "ledger",
              "evidence", "verification", "memory", "context", "driver", "latency"):
        assert k in insp


def test_status_line_contains_verbosity(cfg):
    surf = DesktopSurface()
    line = surf.status_line()
    assert "Verbosity" in line and "Normal" in line


def test_desktop_headless_with_live_runtime():
    from capt_ui.operator.bootstrap import resolve_runtime
    sock, token = resolve_runtime()
    if not (sock and token):
        pytest.skip("no running CAPT runtime for live desktop surface test")
    from capt_ui.surfaces.desktop.surface import headless_projection
    out = headless_projection()
    assert "CAPT Desktop Operator Surface" in out
    assert "SIDEBAR" in out and "RIGHT INSPECTOR" in out


@pytest.fixture
def cfg(tmp_path):
    return tmp_path / "ui"
