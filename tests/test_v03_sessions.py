"""CAPT Solo v0.3 — Session Runtime tests.

Covers: session creation, checkpoint persistence, interruption detection,
resume after restart, consolidation, close, abandonment, restart-packet
fidelity, open-transaction detection.
"""

import json
import time

import pytest

from capt_solo.lifecycle.sessions import SessionRuntime, SESSION_STATUSES
from capt_solo.memory.engine import MemoryEngine
from capt_solo.lifecycle.manager import LifecycleManager
from capt_solo.khsb.bus import KHSB
from capt_solo.ctp.journal import CTPRuntime


@pytest.fixture
def sess(mem_engine):
    sr = SessionRuntime(mem_engine)
    yield sr


def test_session_begin_and_status(sess):
    sid = sess.begin("proj", objective="build v0.3")
    assert isinstance(sid, str) and sid
    st = sess.status(sid)
    assert st["status"] == "active"
    assert st["project_namespace"] == "proj"
    assert st["objective"] == "build v0.3"


def test_session_checkpoint_persists(sess):
    sid = sess.begin("proj")
    cid = sess.checkpoint(sid, objective="o", progress="p",
                          next_action="next", safety_warning="careful")
    assert cid
    cps = sess.list_checkpoints(sid)
    assert len(cps) == 1
    assert cps[0]["next_action"] == "next"
    assert cps[0]["safety_warning"] == "careful"
    # immutable: version recorded
    assert cps[0]["version"] == 1


def test_session_checkpoint_immutable(sess):
    sid = sess.begin("proj")
    cid = sess.checkpoint(sid, progress="v1")
    # re-checkpoint creates a new version, old one unchanged
    cid2 = sess.checkpoint(sid, progress="v2")
    cps = sess.list_checkpoints(sid)
    assert len(cps) == 2
    by_id = {c["checkpoint_id"]: c for c in cps}
    assert by_id[cid]["progress"] == "v1"
    assert by_id[cid2]["progress"] == "v2"


def test_interruption_detection(sess):
    sid = sess.begin("proj")
    sess.checkpoint(sid, progress="mid-way")
    # simulate crash: status active with a STALE last_checkpoint (>1h old)
    old = time.time() - 7200.0
    sess._eng._conn.execute(
        "UPDATE sessions SET status='active', last_checkpoint=?, start_time=? "
        "WHERE session_id=?",
        (old, old, sid))
    sess._eng._conn.commit()
    st = sess.status(sid)
    assert st["status"] == "active"
    # interruption detectable: active with stale checkpoint
    assert st["interrupted"] is True


def test_resume_after_restart(sess):
    sid = sess.begin("proj", objective="obj")
    sess.checkpoint(sid, progress="done", next_action="ship")
    # simulate restart: new SessionRuntime on same DB
    sr2 = SessionRuntime(sess._eng)
    pkt = sr2.resume(sid)
    assert pkt.project == "proj"
    assert pkt.objective == "obj"
    assert pkt.recommended_next == "ship"
    assert pkt.session_id == sid


def test_restart_packet_fidelity(sess):
    sid = sess.begin("proj", objective="o")
    sess.checkpoint(sid, progress="p", latest_verified_result="v",
                   current_hypothesis="h", unresolved_failure="f",
                   files_in_scope=["a.py"], next_action="n", safety_warning="sw")
    pkt = sess.build_restart_packet(sid)
    d = pkt.to_dict()
    assert d["objective"] == "o"
    assert d["recommended_next"] == "n"
    assert d["project"] == "proj"
    assert isinstance(d["uncertainty"], list)
    assert isinstance(d["active_constraints"], list)
    # checkpoint-level detail is preserved separately
    cps = sess.list_checkpoints(sid)
    assert cps[0]["progress"] == "p"
    assert cps[0]["unresolved_failure"] == "f"
    assert "a.py" in cps[0]["files_in_scope"]
    assert cps[0]["safety_warning"] == "sw"
    # recommendations labeled, not asserted as fact
    assert "recommended_next" in d


def test_session_close(sess):
    sid = sess.begin("proj")
    sess.close(sid, outcome="completed")
    assert sess.status(sid)["status"] == "completed"


def test_session_abandon(sess):
    sid = sess.begin("proj")
    sess.abandon(sid, reason="lost context")
    assert sess.status(sid)["status"] == "abandoned"


def test_session_consolidation(sess):
    sid = sess.begin("proj", objective="o")
    sess.checkpoint(sid, progress="p", next_action="n")
    cid = sess.consolidate(sid)
    assert cid
    st = sess.status(sid)
    assert st["status"] == "consolidating" or st["status"] == "active"
    # consolidation record exists
    row = sess._eng._conn.execute(
        "SELECT * FROM session_consolidations WHERE session_id=?",
        (sid,)).fetchone()
    assert row is not None


def test_open_transaction_detection(sess):
    sid = sess.begin("proj")
    # record a pending tx reference in session ctp_transactions
    sess._eng._conn.execute(
        "UPDATE sessions SET ctp_transactions=? WHERE session_id=?",
        (json.dumps(["tx123"]), sid))
    sess._eng._conn.commit()
    pkt = sess.build_restart_packet(sid)
    assert "tx123" in pkt.open_transactions


def test_session_list(sess):
    s1 = sess.begin("a")
    s2 = sess.begin("b")
    lst = sess.list()
    ids = {s["session_id"] for s in lst}
    assert s1 in ids and s2 in ids


def test_manager_session_begin_with_ctp(lifecycle_manager):
    r = lifecycle_manager.session_begin_with_ctp("proj", objective="o")
    assert r["ok"] is True
    assert r["session_id"]
    assert r["receipt"]["status"] == "committed"
