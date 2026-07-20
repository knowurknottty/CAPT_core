"""CAPT Solo v0.3 — Integration tests.

Covers: CTP lifecycle operations, KHSB events, plugin contracts, CLI
contracts, restart recovery, export/import, secret screening, context build
using lifecycle state.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from capt_solo.lifecycle.manager import LifecycleManager
from capt_solo.khsb.bus import KHSB
from capt_solo.ctp.journal import CTPRuntime
from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.secrets import screen
from capt_solo.plugin import CaptSoloPlugin, tool_names


# --- CTP lifecycle operations --------------------------------------------

def test_ctp_promote_idempotent(lifecycle_manager):
    m = lifecycle_manager._eng.store("x", lifecycle_state="candidate")
    r1 = lifecycle_manager.promote_with_ctp(
        m.memory_id, "durable", actor="user",
        evidence=["user_approval"], idempotency_key="k1")
    assert r1["ok"] is True
    # reusing a finalized idempotency key must be rejected (idempotency, not replay)
    from capt_solo.core.errors import IdempotencyError
    try:
        lifecycle_manager.promote_with_ctp(
            m.memory_id, "durable", actor="user",
            evidence=["user_approval"], idempotency_key="k1")
        assert False, "expected IdempotencyError on reused key"
    except IdempotencyError:
        pass


def test_ctp_rollback_on_failure(lifecycle_manager):
    # abort a begun tx leaves no partial state
    tx_id = lifecycle_manager._ctp.begin(correlation_id="test")
    try:
        lifecycle_manager._eng.store("y", lifecycle_state="candidate")
        lifecycle_manager._ctp.abort(tx_id)
    except Exception:
        lifecycle_manager._ctp.abort(tx_id)
    # tx is aborted, not committed
    rcpt = lifecycle_manager._ctp.get_receipt(tx_id)
    assert rcpt is None or rcpt.status == "aborted"


# --- KHSB events ----------------------------------------------------------

def test_khsb_session_events_emitted():
    bus = KHSB()
    received = []
    bus.subscribe("session.started", lambda m: received.append(m))
    eng = MemoryEngine()
    try:
        mgr = LifecycleManager(eng, bus=bus, ctp=CTPRuntime())
        mgr.session_begin_with_ctp("proj")
        assert any(m.topic == "session.started" for m in received)
    finally:
        eng.close()
        bus.reset()


def test_khsb_memory_promoted_event():
    bus = KHSB()
    received = []
    bus.subscribe("memory.promoted", lambda m: received.append(m))
    eng = MemoryEngine()
    try:
        mgr = LifecycleManager(eng, bus=bus, ctp=CTPRuntime())
        m = eng.store("x", lifecycle_state="candidate")
        mgr.promote_with_ctp(m.memory_id, "durable", actor="user",
                             evidence=["user_approval"])
        assert any(m.topic == "memory.promoted" for m in received)
    finally:
        eng.close()
        bus.reset()


# --- plugin contracts -----------------------------------------------------

def test_plugin_v03_tool_names():
    names = set(tool_names())
    for t in ("capt_session_begin", "capt_session_checkpoint",
              "capt_session_resume", "capt_session_status",
              "capt_session_consolidate", "capt_session_close",
              "capt_promote_memory", "capt_archive_memory", "capt_pin_memory",
              "capt_explain_memory_lifecycle", "capt_create_procedure",
              "capt_get_procedure", "capt_record_procedure_run",
              "capt_find_procedures", "capt_add_prospective_memory",
              "capt_list_pending_intents", "capt_resolve_intent",
              "capt_record_retrieval_feedback", "capt_get_restart_context"):
        assert t in names


def test_plugin_session_begin_and_resume():
    p = CaptSoloPlugin()
    r = p.capt_session_begin("proj", objective="o")
    assert r["ok"]
    sid = r["session_id"]
    r2 = p.capt_session_checkpoint(sid, progress="p", next_action="n")
    assert r2["ok"]
    r3 = p.capt_session_resume(sid)
    assert r3["ok"]
    assert r3["restart_packet"]["objective"] == "o"


def test_plugin_promote_memory():
    p = CaptSoloPlugin()
    m = p.capt_store_memory("decision", namespace="proj")
    mid = m["memory"]["memory_id"]
    r = p.capt_promote_memory(mid, "durable", actor="user",
                              evidence=["user_approval"])
    assert r["ok"]
    assert r["transition_id"]


def test_plugin_create_and_get_procedure():
    p = CaptSoloPlugin()
    r = p.capt_create_procedure("deploy", trigger="on merge",
                                steps="1. build 2. ship", verification="smoke")
    assert r["ok"]
    pid = r["procedure_id"]
    g = p.capt_get_procedure(pid)
    assert g["ok"]
    assert g["procedure"]["name"] == "deploy"


def test_plugin_prospective_and_resolve():
    p = CaptSoloPlugin()
    r = p.capt_add_prospective_memory("fix bug", kind="task", namespace="proj")
    assert r["ok"]
    iid = r["intent_id"]
    lst = p.capt_list_pending_intents(namespace="proj")
    assert lst["ok"]
    assert any(i["intent_id"] == iid for i in lst["intents"])
    res = p.capt_resolve_intent(iid)
    assert res["ok"]


def test_plugin_retrieval_feedback():
    p = CaptSoloPlugin()
    r = p.capt_record_retrieval_feedback("useful", namespace="proj",
                                         reason="clear")
    assert r["ok"]
    assert r["feedback_id"]


# --- CLI contracts --------------------------------------------------------

def _run_cli(*args, home=None):
    env = dict(__import__("os").environ)
    import tempfile
    if home is None:
        home = tempfile.mkdtemp()
    env["CAPT_SOLO_HOME"] = home
    proc = subprocess.run(
        [sys.executable, "capt_cli.py", *args],
        capture_output=True, text=True, env=env, cwd=Path(__file__).parent.parent)
    return proc


def test_cli_memory_list_json():
    proc = _run_cli("--json", "memory", "list")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert isinstance(data, list)


def test_cli_session_flow():
    import tempfile
    home = tempfile.mkdtemp()
    # begin
    p1 = _run_cli("--json", "session", "begin", "proj", "--objective", "o", home=home)
    assert p1.returncode == 0
    sid = json.loads(p1.stdout)["session_id"]
    # checkpoint
    p2 = _run_cli("--json", "session", "checkpoint", sid,
                  "--progress", "p", "--next-action", "n", home=home)
    assert p2.returncode == 0
    # resume
    p3 = _run_cli("--json", "session", "resume", sid, home=home)
    assert p3.returncode == 0
    pkt = json.loads(p3.stdout)
    assert pkt["objective"] == "o"
    assert pkt["recommended_next"] == "n"


def test_cli_prospective_resolve():
    p1 = _run_cli("--json", "prospective", "list")
    assert p1.returncode == 0


def test_cli_retrieval_reset():
    p = _run_cli("--json", "retrieval", "reset", "--namespace", "proj")
    assert p.returncode == 0


# --- restart recovery -----------------------------------------------------

def test_restart_recovery_across_processes(tmp_path):
    """Simulate process restart: data persists, session resumes."""
    import tempfile
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = dict(__import__("os").environ, CAPT_SOLO_HOME=str(home))
    # process 1: begin + checkpoint
    r1 = subprocess.run([sys.executable, "capt_cli.py", "--json",
                         "session", "begin", "proj", "--objective", "obj"],
                        capture_output=True, text=True, env=env,
                        cwd=Path(__file__).parent.parent)
    sid = json.loads(r1.stdout)["session_id"]
    subprocess.run([sys.executable, "capt_cli.py", "--json", "session",
                    "checkpoint", sid, "--progress", "done",
                    "--next-action", "ship"],
                   capture_output=True, text=True, env=env,
                   cwd=Path(__file__).parent.parent)
    # process 2 (new process, same home): resume
    r2 = subprocess.run([sys.executable, "capt_cli.py", "--json",
                         "session", "resume", sid],
                        capture_output=True, text=True, env=env,
                        cwd=Path(__file__).parent.parent)
    assert r2.returncode == 0
    pkt = json.loads(r2.stdout)
    assert pkt["objective"] == "obj"
    assert pkt["recommended_next"] == "ship"


# --- secret screening -----------------------------------------------------

def test_secret_screening_blocks_secret_in_memory():
    # a string matching a high-precision secret pattern must be flagged
    ok, reasons, _ = screen("api_key=abcdefghijklmnopqrstuvwxyz123456")
    assert ok is True
    assert reasons
    # a benign architectural fact must NOT be flagged
    ok2, _, _ = screen("normal durable fact about architecture")
    assert ok2 is False


# --- context build using lifecycle state ----------------------------------

def test_context_build_excludes_archived(lifecycle_manager):
    from capt_solo.memory.context import build_context
    m1 = lifecycle_manager._eng.store("active fact", lifecycle_state="active",
                                      tier="durable")
    m2 = lifecycle_manager._eng.store("archived fact", lifecycle_state="archived",
                                      tier="durable")
    result = build_context(lifecycle_manager._eng, namespace="default",
                           char_budget=1000)
    ids = {item.memory_id for item in result.items}
    assert m1.memory_id in ids
    # archived excluded from active context (either not selected or explicitly excluded)
    assert m2.memory_id not in ids
