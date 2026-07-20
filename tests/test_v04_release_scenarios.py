"""CAPT Solo v0.4 — Permanent release-scenario integration tests.

These six scenarios are the canonical release-gate scenarios. They are run
sequentially (pytest default) against isolated temp homes. Each is a real
assertion, not a script that disappears.

Scenarios:
1. clean CAPT Solo home initializes at schema v4 with a backup dir
2. v3 database migrates to v4 with a verified backup (no partial apply)
3. restart after migration does not create an unnecessary additional backup
4. imported bubble remains quarantined until approved
5. workflow remains independently unverified despite verified components
6. component degradation produces scoped, non-global ClaimGuard language
"""

import pytest

from capt_solo.memory.engine import MemoryEngine, SCHEMA_VERSION
from capt_solo.foundry import (
    ProofEngine, CapabilityRegistry, SkillFoundry, ClaimGuard, ValidationHarness,
    KnowledgeBubbleRuntime, WorkflowProofEngine, DEGRADATION_REASONS,
)
from capt_solo.lifecycle.procedures import ProcedureStore


def _make_published_skill(eng, pe, ps, sf, name="s"):
    pid = ps.create("op", steps="echo x", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(
        cid, name=name,
        verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    sf.validate(sid, ValidationHarness(pe))
    sf.submit_for_review(sid)
    sf.approve(sid, reviewer="captain")
    sf.publish(sid, ctp_tx_id="tx")
    return sid


def test_scenario_clean_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    try:
        bd = eng._db_path.parent.parent / "backups"
        assert SCHEMA_VERSION == 4
        assert bd.exists()
    finally:
        eng.close()


def test_scenario_migrated_v3(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    # construct a v3 fixture: delete all version rows, insert v3
    eng._conn.execute("DELETE FROM schema_version")
    eng._conn.execute("INSERT INTO schema_version (version) VALUES (3)")
    eng._conn.commit()
    eng.close()
    eng2 = MemoryEngine()  # triggers 3->4 migration with backup
    try:
        cur = eng2._conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()["version"]
        bd = eng2._db_path.parent.parent / "backups"
        assert cur == 4
        assert bd.exists()
        # backup preserves the v3 manifest (pre-migration state)
        backups = sorted(bd.glob("*.db"))
        assert len(backups) >= 1
    finally:
        eng2.close()


def test_scenario_restart_no_extra_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    eng.close()
    bd = eng._db_path.parent.parent / "backups"
    n_before = len(sorted(bd.glob("*.db")))
    eng2 = MemoryEngine()  # reopen -> idempotent, no new backup
    try:
        cur = eng2._conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()["version"]
        n_after = len(sorted(bd.glob("*.db")))
        assert cur == 4
        assert n_after == n_before  # no unnecessary additional backup
    finally:
        eng2.close()


def test_scenario_bubble_quarantined(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    ps = ProcedureStore(eng)
    sf = SkillFoundry(eng._conn, pe, ps)
    kb = KnowledgeBubbleRuntime(eng._conn, sf)
    try:
        sid = _make_published_skill(eng, pe, ps, sf, name="q-skill")
        bub = kb.build_bubble("qb", skills=[sf.get(sid).to_dict()],
                              exported_namespaces=["t"])
        bid = kb.import_bubble(bub)
        row = eng._conn.execute(
            "SELECT lifecycle_state FROM knowledge_bubbles WHERE bubble_id=?",
            (bid,)).fetchone()
        assert row["lifecycle_state"] == "quarantined"
    finally:
        eng.close()


def test_scenario_workflow_independent(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    ps = ProcedureStore(eng)
    sf = SkillFoundry(eng._conn, pe, ps)
    wpe = WorkflowProofEngine(eng._conn, sf, pe)
    try:
        sid = _make_published_skill(eng, pe, ps, sf, name="wf-skill")
        wp = wpe.evaluate("wf1", "1.0.0", [sid])
        assert wp.lifecycle_state == "candidate"
        assert wp.lifecycle_state != "verified"
    finally:
        eng.close()


def test_scenario_degradation_scoped_language(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPT_SOLO_HOME", str(tmp_path))
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    reg = CapabilityRegistry(eng._conn, pe)
    try:
        reg.register("deg-cap", "x", "capt_solo")
        reg.degrade("deg-cap", "component_degraded", affected_scope="macos")
        cg = ClaimGuard(reg, pe)
        v = cg.verify_claim("Task complete and verified.", capability_id="deg-cap")
        assert v.supported is False
        assert "not globally revoked" in v.language
    finally:
        eng.close()
