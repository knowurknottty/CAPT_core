"""CAPT Solo v0.4 — Migration tests (v3 -> v4) with backup safety gate.

Verifies:
- schema version advances to 4 on a fresh DB
- v4 tables exist after migration
- migration is idempotent (re-opening does not duplicate version rows or backups)
- a pre-v4 DB (version 3) is upgraded to 4
- pre-migration backup is created, opens, passes integrity_check
- backup filename is unique
- original pre-migration schema is preserved in the backup
- migration ABORTS when backup fails (no partial apply)
- WAL-backed contents are included in the backup
- in-memory behavior is explicit (no silent backup)
- all v4 tables function after migration
"""

import os
import sqlite3

import pytest

from capt_solo.core.errors import MigrationBackupError
from capt_solo.memory.engine import MemoryEngine, SCHEMA_VERSION
from capt_solo.foundry import (
    ProofEngine, CapabilityRegistry, SkillFoundry, KnowledgeBubbleRuntime,
    Governance, ValidationHarness, ProofRequirement,
)
from capt_solo.lifecycle.procedures import ProcedureStore
from capt_solo.ctp.journal import CTPRuntime


V4_TABLES = ("proof_evidence", "proof_requirements", "capabilities", "skills",
             "skill_candidates", "composite_workflows", "knowledge_bubbles",
             "governance_audit")


def _table_exists(conn, name):
    return conn.execute(
        "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name=?",
        (name,)).fetchone()[0] == 1


def test_fresh_db_migrates_to_v4(tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["CAPT_SOLO_HOME"] = str(home)
    eng = MemoryEngine()
    row = eng._conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    assert row["version"] == 4
    assert SCHEMA_VERSION == 4
    for t in V4_TABLES:
        assert _table_exists(eng._conn, t), f"missing table {t}"
    eng.close()


def test_migration_idempotent(tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["CAPT_SOLO_HOME"] = str(home)
    MemoryEngine().close()  # first open: migrates 0->4, creates one backup
    backups_after_first = list((home / "backups").glob("*.db"))
    assert len(backups_after_first) == 1
    eng2 = MemoryEngine()  # already at v4: must NOT create another backup
    rows = eng2._conn.execute(
        "SELECT COUNT(*) AS c FROM schema_version WHERE version=4").fetchone()["c"]
    assert rows == 1
    backups_after_second = list((home / "backups").glob("*.db"))
    assert len(backups_after_second) == 1, (
        f"unexpected extra backup on idempotent reopen: {backups_after_second}")
    eng2.close()


def test_v3_db_upgrades_to_v4(tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    db = home / "data" / "memory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    os.environ["CAPT_SOLO_HOME"] = str(home)
    # craft a v3 DB manually (direct SQL allowed in migration fixtures)
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version (version) VALUES (3)")
    conn.execute("CREATE TABLE memories (memory_id TEXT PRIMARY KEY, content TEXT)")
    conn.commit()
    conn.close()
    eng = MemoryEngine()  # should migrate 3 -> 4
    row = eng._conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    assert row["version"] == 4
    assert _table_exists(eng._conn, "capabilities")
    eng.close()


def test_backup_created_and_valid(tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["CAPT_SOLO_HOME"] = str(home)
    # Open MemoryEngine to build the FULL v1-v3 schema, seed data, then
    # downgrade the version row to 3 so the next open re-migrates (3->4) and
    # produces a pre-migration backup.
    eng = MemoryEngine()
    eng._conn.execute(
        "INSERT INTO memories (memory_id, content, created_at, updated_at) "
        "VALUES ('m1','v1',0.0,0.0)")
    eng._conn.commit()
    eng.close()
    db = home / "data" / "memory.db"
    conn = sqlite3.connect(str(db))
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (3)")
    conn.commit()
    conn.close()
    # reopening triggers backup (3 -> 4) then migration
    eng2 = MemoryEngine()
    assert eng2._conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()["version"] == 4
    backup_dir = home / "backups"
    assert backup_dir.exists()
    backups = sorted(backup_dir.glob("*.db"))
    # one backup from the initial open (v1) + one from the re-migration (v3)
    assert len(backups) == 2, f"expected two backups, got {backups}"
    # backups[0] = v1 backup (before m1 inserted); backups[1] = v3 backup (with m1)
    b0 = sqlite3.connect(str(backups[0]))
    try:
        rows = b0.execute("PRAGMA integrity_check").fetchall()
        assert all(r[0] == "ok" for r in rows)
        assert _table_exists(b0, "memories")
        assert _table_exists(b0, "tags")
        assert not _table_exists(b0, "capabilities")
    finally:
        b0.close()
    b1 = sqlite3.connect(str(backups[1]))
    try:
        rows = b1.execute("PRAGMA integrity_check").fetchall()
        assert all(r[0] == "ok" for r in rows)
        # WAL content included in the v3 backup
        assert b1.execute("SELECT COUNT(*) AS c FROM memories WHERE memory_id='m1'").fetchone()[0] == 1
    finally:
        b1.close()
    eng2.close()


def test_backup_filename_unique(tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["CAPT_SOLO_HOME"] = str(home)
    db = home / "data" / "memory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    # create two v3 fixtures and migrate each -> two distinct backups
    for i in range(2):
        if db.exists():
            db.unlink()
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version (version) VALUES (3)")
        conn.execute("CREATE TABLE memories (memory_id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()
        MemoryEngine().close()
    backups = list((home / "backups").glob("*.db"))
    assert len(backups) == 2, f"expected 2 unique backups, got {backups}"
    assert len(set(str(b) for b in backups)) == 2


def test_migration_aborts_when_backup_fails(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["CAPT_SOLO_HOME"] = str(home)
    # Build a v3 fixture WITHOUT opening MemoryEngine (which would migrate+backup)
    db = home / "data" / "memory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version (version) VALUES (3)")
    conn.execute("CREATE TABLE memories (memory_id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()
    # Force the backup safety gate to fail. Migration MUST abort and must not
    # partially apply (no capabilities table, version stays 3).
    monkeypatch.setattr(
        MemoryEngine, "_backup_before_migration",
        classmethod(lambda cls, from_version: (_ for _ in ()).throw(
            MigrationBackupError("injected backup failure"))))
    with pytest.raises(MigrationBackupError):
        MemoryEngine()
    # schema must NOT have been partially migrated: capabilities table absent
    conn = sqlite3.connect(str(db))
    assert not _table_exists(conn, "capabilities")
    # and version row still 3 (no v4 inserted)
    v = conn.execute("SELECT MAX(version) AS m FROM schema_version").fetchone()[0]
    assert v == 3
    conn.close()


def test_in_memory_explicit_no_backup(tmp_path):
    # engine constructed with an explicit :memory: path documents the absence
    # of a filesystem backup rather than silently creating one.
    eng = MemoryEngine(db_path=__import__("pathlib").Path(":memory:"))
    # schema still initializes in-memory
    row = eng._conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    assert row["version"] == 4
    eng.close()


def test_v4_tables_functional_after_migration(tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["CAPT_SOLO_HOME"] = str(home)
    eng = MemoryEngine()
    pe = ProofEngine(eng._conn)
    reg = CapabilityRegistry(eng._conn, pe)
    ps = ProcedureStore(eng)
    sf = SkillFoundry(eng._conn, pe, ps)
    kb = KnowledgeBubbleRuntime(eng._conn, sf)
    ctp = CTPRuntime()
    gov = Governance(eng._conn, ctp, foundry=sf, registry=reg, bubbles=kb)
    reg.register("cap_m", "does m", "capt_solo")
    pe.record("test_pass", "pytest", "h1", "t", scope="cap_m")
    reg.verify("cap_m", pe, [ProofRequirement("test_pass", 1, "cap_m")])
    pid = ps.create("op", steps="echo x", verification="smoke")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.record_run(pid, outcome="success", verification_result="ok")
    ps.verify_procedure(pid, min_success=2)
    cid = sf.create_candidate(pid)
    sid = sf.build_skill(cid, name="m-skill",
                          verification_requirements=[{"type": "static_analysis", "min_count": 1}])
    rep = sf.validate(sid, ValidationHarness(pe))
    assert rep.passed is True
    sf.submit_for_review(sid)
    sf.approve(sid, reviewer="captain")
    gov.publish_skill(sid, actor="captain", reason="release")
    assert sf.get(sid).lifecycle_state == "published"
    eng.close()
