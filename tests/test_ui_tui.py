"""Headless tests for the CAPT TUI (Textual) using Textual's test pilot.

Verifies the TUI mounts, renders, connects to the live runtime through the
shared operator layer, and that keyboard actions (verbosity cycling/refresh)
do not raise. No display required.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def runtime_env():
    """Require a live runtime or skip. Uses CAPT_STATE_DIR or defaults."""
    from capt_ui.operator.bootstrap import resolve_runtime
    sock, token = resolve_runtime()
    if not (sock and token):
        pytest.skip("no running CAPT runtime for TUI headless test")
    return sock, token


def test_tui_mounts_and_shows_status(runtime_env):
    from textual.pilot import Pilot  # noqa: F401
    from capt_ui.surfaces.tui.app import CaptTUI

    app = CaptTUI()
    # run_test drives the app event loop headlessly
    from textual.app import App  # noqa: F401
    import asyncio

    async def run():
        async with app.run_test():
            status = app.query_one("#status")
            assert status is not None

    asyncio.run(run())


def test_tui_refresh_and_verbosity_cycle(runtime_env):
    from capt_ui.surfaces.tui.app import CaptTUI
    import asyncio

    app = CaptTUI()
    async def run():
        async with app.run_test():
            # connect against live runtime
            app.action_refresh()
            st = app.query_one("#status").status
            assert "model" in st or "health" in st
            # verbosity toggle should not raise
            app.action_cyclev()
            app.action_cyclev()

    asyncio.run(run())
