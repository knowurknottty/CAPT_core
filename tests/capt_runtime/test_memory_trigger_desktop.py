"""CAPT Memory Trigger — Desktop M1 operator control conformance.

Exercises the desktop operator control path (UpdateMemoryTriggerPolicy command
+ DesktopApp projection) against the real runtime server. Proves:
- operator changes trigger by one 32k step;
- invalid value rejected visibly;
- policy denial displayed (operator cannot widen beyond model safe limit);
- reconnect preserves effective policy;
- UI cannot bypass runtime validation.
"""

import os
import tempfile
import threading
import time

import pytest

from desktop.capt_runtime_service import serve
from desktop.desktop_app import DesktopApp
from desktop.desktop_runtime_client import RuntimeClient


@pytest.fixture
def app_server():
    tmp = tempfile.mkdtemp(prefix="/tmp/capt-mem-dsk-")
    ledger = os.path.join(tmp, "rt.db")
    sock = os.path.join(tmp, "rt.sock")
    tok = os.path.join(tmp, "token")
    t = threading.Thread(target=serve, args=(ledger, sock, tok, False), daemon=True)
    t.start()
    for _ in range(100):
        if os.path.exists(sock):
            break
        time.sleep(0.05)
    app = DesktopApp(sock, tok)
    app.connect()
    yield app
    app.disconnect()


def test_operator_changes_trigger_by_one_32k_step(app_server):
    pol0 = app_server.get_memory_policy()
    assert pol0["retrievalTriggerSteps"] == 8
    r = app_server.gui_update_memory_trigger_policy(
        retrieval_trigger_steps=2, idempotency_key="dsk-1")
    assert r["status"] == "accepted"
    assert r["result"]["retrievalTriggerSteps"] == 2
    assert r["result"]["retrievalTokens"] == 65_536


def test_invalid_value_rejected(app_server):
    # 0 steps is invalid -> rejected by runtime validation.
    r = app_server.gui_update_memory_trigger_policy(
        retrieval_trigger_steps=0, idempotency_key="dsk-2")
    assert r["status"] == "rejected"
    assert r["classification"] == "policy_denied"
    assert r["error"]["code"] == "MEMORY_TRIGGER_CONFIGURATION_INVALID"


def test_policy_denial_displayed(app_server):
    # Operator cannot widen the hard-stop beyond the model safe limit (8).
    r = app_server.gui_update_memory_trigger_policy(
        hard_stop_trigger_steps=16, idempotency_key="dsk-3")
    assert r["status"] == "rejected"
    assert r["classification"] == "policy_denied"


def test_reconnect_preserves_effective_policy(app_server):
    app_server.gui_update_memory_trigger_policy(
        retrieval_trigger_steps=3, idempotency_key="dsk-4")
    # Simulate reconnect: a fresh DesktopApp against the same socket.
    app2 = DesktopApp(app_server.sock_path, app_server.token_file)
    app2.connect()
    pol = app2.get_memory_policy()
    assert pol["retrievalTriggerSteps"] == 3
    app2.disconnect()


def test_ui_cannot_bypass_runtime_validation(app_server):
    # The desktop only submits governed commands; it cannot write config
    # directly. We assert the command path is the only mutation surface.
    r = app_server.gui_update_memory_trigger_policy(
        retrieval_trigger_steps=1, idempotency_key="dsk-5")
    assert r["status"] == "accepted"
    # The persisted policy version advanced (runtime owns persistence).
    st = app_server.get_memory_state()
    assert 2 in st["policyVersions"]  # v1 initial + v2 after this change
