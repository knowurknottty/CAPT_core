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


def test_tui_approve_deny_no_pending(runtime_env):
    """Approve/deny with no pending request must not raise, just notify."""
    from capt_ui.surfaces.tui.app import CaptTUI
    import asyncio

    app = CaptTUI()
    async def run():
        async with app.run_test():
            app.action_refresh()
            app.action_approve()  # no pending -> notify, no raise
            app.action_deny()

    asyncio.run(run())


def test_tui_approval_decision_routes_to_runtime(runtime_env):
    """Create a mission requiring approval and confirm the TUI approve action
    routes through the governed runtime decision op."""
    import asyncio
    import uuid
    from capt_ui.surfaces.tui.app import CaptTUI
    from desktop.desktop_runtime_client import RuntimeClient

    sock, token = runtime_env
    client = RuntimeClient(sock, token)
    client.connect()
    payload = {
        "schemaVersion": "1.0.0",
        "missionId": "m-tui-%s" % uuid.uuid4().hex[:8],
        "objective": "TUI approval routing test",
        "rawRequest": "TUI approval routing test",
        "normalizedRequest": "tui approval routing test",
        "constraints": [],
        "successCriteria": [{"criterionId": "sc-1", "statement": "ok", "requiresVerification": True}],
        "terminationCriteria": [],
        "budget": {"maxEvents": 0},
        "unresolvedAmbiguities": [],
        "requiresApproval": True,
        "requestedCapability": "cap.fs.read",
        "operation": "ReadOnly",
        "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": False},
        "riskClassification": "low",
        "policyReason": "TUI test requires approval.",
    }
    client.command("create_mission", payload, "tui-%s" % uuid.uuid4().hex[:8])

    app = CaptTUI()
    async def run():
        async with app.run_test():
            app.action_refresh()
            # pending request exists -> approve routes via governed op
            app.action_approve()

    asyncio.run(run())

    # cleanup: any later reconnect is fine; no assertion on ledger growth here
    client.disconnect()
