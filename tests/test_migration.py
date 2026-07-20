"""Tests for v0.1 -> v0.2 migration using a real v1 fixture DB."""

import json
import sqlite3
from pathlib import Path

import pytest

from capt_solo.core.config import reset_paths_for_test
from capt_solo.memory.engine import MemoryEngine, SCHEMA_VERSION


@pytest.fixture
def v1_db(tmp_path) -> Path:
    """Create a real v1-only database (no CSG tables) and return its path."""
    db = tmp_path / "v1.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO schema_version (version) VALUES (1);
        CREATE TABLE memories (
            memory_id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            namespace TEXT NOT NULL DEFAULT 'default',
            provenance TEXT NOT NULL DEFAULT 'unknown',
            confidence REAL NOT NULL DEFAULT 1.0,
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE tags (
            memory_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            PRIMARY KEY (memory_id, tag)
        );
        INSERT INTO memories
          (memory_id, content, namespace, provenance, confidence, metadata, created_at, updated_at)
          VALUES ('old1', 'legacy memory', 'ns', 'user', 1.0, '{}', 1.0, 2.0);
        """
    )
    conn.commit()
    conn.close()
    return db


def test_v1_to_v2_migration_creates_tables(v1_db):
    eng = MemoryEngine(v1_db)
    try:
        # schema_version should now include 2
        versions = [r["version"] for r in eng._conn.execute(
            "SELECT version FROM schema_version").fetchall()]
        assert 2 in versions
        # CSG tables exist
        tables = [r[0] for r in eng._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for t in ("memory_nodes", "memory_edges", "memory_aliases",
                   "memory_conflicts", "context_builds", "context_build_items"):
            assert t in tables
        # legacy memory preserved + node seeded
        assert eng.get("old1") is not None
        node = eng._conn.execute(
            "SELECT * FROM memory_nodes WHERE memory_id='old1'").fetchone()
        assert node is not None
    finally:
        eng.close()


def test_v1_to_v2_migration_idempotent(v1_db):
    # opening twice must not error and must remain at version 2
    for _ in range(2):
        eng = MemoryEngine(v1_db)
        versions = [r["version"] for r in eng._conn.execute(
            "SELECT version FROM schema_version").fetchall()]
        assert versions.count(2) == 1
        eng.close()


def test_v1_to_v2_export_import_roundtrip(v1_db, tmp_path):
    eng = MemoryEngine(v1_db)
    try:
        eng.store("new memory after migration", namespace="ns2", tags=["t"])
        exp = eng.export_json(tmp_path / "exp.json")
        assert exp.exists()
        data = json.loads(exp.read_text())
        assert data["version"] == SCHEMA_VERSION
        # import into fresh v2 db
        fresh = MemoryEngine(tmp_path / "fresh.db")
        try:
            n = fresh.import_json(exp, merge=True)
            assert n >= 2  # old1 + new
            # graph data preserved
            assert fresh._conn.execute(
                "SELECT COUNT(*) AS c FROM memory_nodes").fetchone()["c"] >= 2
        finally:
            fresh.close()
    finally:
        eng.close()


def test_migration_backup_before_not_required_but_safe(v1_db, tmp_path):
    """Engine opens v1 and migrates; a backup copy can be made post-migration."""
    eng = MemoryEngine(v1_db)
    try:
        bk = eng.backup(tmp_path / "post_mig.db")
        assert bk.exists()
        # backup is itself a valid migrated db
        eng2 = MemoryEngine(bk)
        try:
            assert eng2.integrity_check()
        finally:
            eng2.close()
    finally:
        eng.close()
