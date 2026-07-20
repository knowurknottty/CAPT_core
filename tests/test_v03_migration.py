"""CAPT Solo v0.3 — Migration tests (v0.1->v0.3, v0.2->v0.3, repeat, backup)."""

import json
import sqlite3
from pathlib import Path

import pytest

from capt_solo.core.config import reset_paths_for_test
from capt_solo.memory.engine import MemoryEngine, SCHEMA_VERSION


@pytest.fixture
def v1_db(tmp_path) -> Path:
    db = tmp_path / "v1.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO schema_version (version) VALUES (1);
        CREATE TABLE memories (
            memory_id TEXT PRIMARY KEY, content TEXT NOT NULL,
            namespace TEXT NOT NULL DEFAULT 'default',
            provenance TEXT NOT NULL DEFAULT 'unknown',
            confidence REAL NOT NULL DEFAULT 1.0,
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE tags (memory_id TEXT NOT NULL, tag TEXT NOT NULL,
            PRIMARY KEY (memory_id, tag));
        INSERT INTO memories
          (memory_id, content, namespace, provenance, confidence, metadata, created_at, updated_at)
          VALUES ('old1', 'legacy memory', 'ns', 'user', 1.0, '{}', 1.0, 2.0);
        """
    )
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def v2_db(tmp_path) -> Path:
    """A v2 database (has CSG tables but not v0.3 tables)."""
    db = tmp_path / "v2.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO schema_version (version) VALUES (2);
        CREATE TABLE memories (
            memory_id TEXT PRIMARY KEY, content TEXT NOT NULL,
            namespace TEXT NOT NULL DEFAULT 'default',
            provenance TEXT NOT NULL DEFAULT 'unknown',
            confidence REAL NOT NULL DEFAULT 1.0,
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL, updated_at REAL NOT NULL,
            tier TEXT NOT NULL DEFAULT 'durable',
            lifecycle_state TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE tags (memory_id TEXT NOT NULL, tag TEXT NOT NULL,
            PRIMARY KEY (memory_id, tag));
        CREATE TABLE memory_nodes (
            node_id TEXT PRIMARY KEY, memory_id TEXT, node_type TEXT,
            label TEXT, weight REAL, created_at REAL);
        CREATE TABLE memory_edges (
            edge_id TEXT PRIMARY KEY, source TEXT, target TEXT,
            edge_type TEXT, weight REAL, confidence REAL,
            provenance TEXT, created_at REAL, ctp_tx_id TEXT);
        CREATE TABLE memory_aliases (
            alias TEXT PRIMARY KEY, canonical TEXT, created_at REAL);
        CREATE TABLE memory_conflicts (
            conflict_id TEXT PRIMARY KEY, memory_a TEXT, memory_b TEXT,
            reason TEXT, resolved INTEGER DEFAULT 0, created_at REAL,
            ctp_tx_id TEXT);
        CREATE TABLE context_builds (
            build_id TEXT PRIMARY KEY, namespace TEXT, query TEXT,
            budget INTEGER, created_at REAL);
        CREATE TABLE context_build_items (
            build_id TEXT, memory_id TEXT, score REAL, rank INTEGER,
            explanation TEXT);
        INSERT INTO memories
          (memory_id, content, namespace, provenance, confidence, metadata, created_at, updated_at, tier, lifecycle_state)
          VALUES ('m2', 'v2 memory', 'ns', 'user', 1.0, '{}', 1.0, 2.0, 'durable', 'active');
        """
    )
    conn.commit()
    conn.close()
    return db


def _v3_tables():
    return (
        "memory_lifecycle_transitions", "memory_retention_policies",
        "sessions", "session_checkpoints", "session_events",
        "session_consolidations", "procedures", "procedure_versions",
        "procedure_runs", "prospective_memories", "retrieval_feedback",
        "retrieval_adaptation", "semantic_index_metadata",
    )


def test_v1_to_v3_migration_creates_all_tables(v1_db):
    eng = MemoryEngine(v1_db)
    try:
        versions = [r["version"] for r in eng._conn.execute(
            "SELECT version FROM schema_version").fetchall()]
        assert 3 in versions
        tables = {r[0] for r in eng._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for t in _v3_tables():
            assert t in tables
        # legacy memory preserved
        assert eng.get("old1") is not None
        # tier/lifecycle defaulted
        assert eng.get("old1").tier == "durable"
        assert eng.get("old1").lifecycle_state == "active"
    finally:
        eng.close()


def test_v2_to_v3_migration(v2_db):
    eng = MemoryEngine(v2_db)
    try:
        versions = [r["version"] for r in eng._conn.execute(
            "SELECT version FROM schema_version").fetchall()]
        assert 3 in versions
        tables = {r[0] for r in eng._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for t in _v3_tables():
            assert t in tables
        assert eng.get("m2") is not None
    finally:
        eng.close()


def test_repeat_migration_idempotent(v1_db):
    for _ in range(3):
        eng = MemoryEngine(v1_db)
        versions = [r["version"] for r in eng._conn.execute(
            "SELECT version FROM schema_version").fetchall()]
        assert versions.count(3) == 1
        eng.close()


def test_migration_backup_created(v1_db, tmp_path):
    eng = MemoryEngine(v1_db)
    try:
        bk = eng.backup(tmp_path / "post_v3.db")
        assert bk.exists()
        eng2 = MemoryEngine(bk)
        try:
            assert eng2.integrity_check()
        finally:
            eng2.close()
    finally:
        eng.close()


def test_v3_export_import_roundtrip(v2_db, tmp_path):
    eng = MemoryEngine(v2_db)
    try:
        # add v0.3 data
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
        mgr.promote_with_ctp("m2", "durable", actor="user",
                             evidence=["user_approval"])
        sid = mgr.session_begin_with_ctp("proj")["session_id"]
        mgr.sessions.checkpoint(sid, progress="p", next_action="n")
        exp = eng.export_json(tmp_path / "exp.json")
        data = json.loads(exp.read_text())
        assert data["version"] == SCHEMA_VERSION
        # import into fresh db
        fresh = MemoryEngine(tmp_path / "fresh.db")
        try:
            n = fresh.import_json(exp, merge=True)
            assert n >= 1
            # v0.3 tables present in fresh
            tables = {r[0] for r in fresh._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            for t in _v3_tables():
                assert t in tables
            # session checkpoint preserved
            assert fresh._conn.execute(
                "SELECT COUNT(*) AS c FROM session_checkpoints").fetchone()["c"] >= 1
        finally:
            fresh.close()
    finally:
        eng.close()
