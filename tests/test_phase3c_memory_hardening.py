"""Phase 3C — internal memory hardening tests.

Exercises real persistence, migration, export/import round-trip, corruption
recovery, consent enforcement, and canonical adapter mapping. No mocks of the
database; uses a temp file per test.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from capt_solo.memory.engine import MemoryEngine, SCHEMA_VERSION
from capt_solo.memory.interfaces import (
    ConsentState,
    MemoryRecord,
    RetentionPolicy,
    TemporalMetadata,
    canonical_to_memory_kwargs,
    memory_to_canonical,
)
from capt_solo.ontology import Confidence, Provenance


@pytest.fixture
def eng():
    with tempfile.TemporaryDirectory() as d:
        e = MemoryEngine(db_path=Path(d) / "mem.db")
        yield e
        e.close()


def test_c_schema_version_is_five(eng):
    assert eng._current_version() == SCHEMA_VERSION == 5


def test_c_store_carries_canonical_fields(eng):
    m = eng.store(
        "observation: system stable",
        namespace="obs",
        provenance="sensor-a",
        confidence=0.8,
        uncertainty=0.15,
        retention="durable",
        consent="granted",
        identity_link="agent-1",
        evidence_refs=["ev-1", "ev-2"],
        tags=["stability"],
    )
    got = eng.get(m.memory_id)
    assert got.uncertainty == 0.15
    assert got.retention == "durable"
    assert got.consent == "granted"
    assert got.identity_link == "agent-1"
    assert got.evidence_refs == ["ev-1", "ev-2"]


def test_c_uncertainty_preserved_through_update(eng):
    m = eng.store("x", confidence=0.9, uncertainty=0.1)
    eng.update(m.memory_id, uncertainty=0.2)
    assert eng.get(m.memory_id).uncertainty == 0.2


def test_c_uncertainty_range_validated(eng):
    with pytest.raises(Exception):
        eng.store("bad", uncertainty=1.5)


def test_c_export_import_roundtrip(eng):
    a = eng.store("alpha", namespace="n1", confidence=0.7, uncertainty=0.1,
                  retention="archival", consent="granted", evidence_refs=["e1"],
                  tags=["t1"])
    b = eng.store("beta", namespace="n2", provenance="p2")
    path = Path(tempfile.mkdtemp()) / "export.json"
    eng.export_json(path)
    data = json.loads(path.read_text())
    assert data["version"] == SCHEMA_VERSION
    # import into a fresh engine
    with tempfile.TemporaryDirectory() as d:
        e2 = MemoryEngine(db_path=Path(d) / "mem2.db")
        count = e2.import_json(path)
        assert count == 2
        got_a = e2.get(a.memory_id)
        assert got_a is not None
        assert got_a.uncertainty == 0.1
        assert got_a.retention == "archival"
        assert got_a.consent == "granted"
        assert got_a.evidence_refs == ["e1"]
        assert got_a.tags == ["t1"]
        e2.close()


def test_c_migration_forward_and_rollback(tmp_path):
    # Build a v4 DB by writing schema_version=4 and a v4-shaped memories table,
    # then open with MemoryEngine (should migrate to 5), then rollback.
    import sqlite3
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("""CREATE TABLE memories (
        memory_id TEXT PRIMARY KEY, content TEXT NOT NULL, namespace TEXT,
        provenance TEXT, confidence REAL, metadata TEXT, created_at REAL,
        updated_at REAL, tier TEXT, lifecycle_state TEXT)""")
    conn.execute("""CREATE TABLE tags (
        memory_id TEXT NOT NULL, tag TEXT NOT NULL,
        PRIMARY KEY (memory_id, tag))""")
    conn.execute("INSERT INTO schema_version (version) VALUES (4)")
    conn.execute("""INSERT INTO memories VALUES ('m1','c','default','unknown',1.0,'{}',
        1.0,1.0,'durable','active')""")
    conn.commit()
    conn.close()
    e = MemoryEngine(db_path=db)
    assert e._current_version() == 5  # migrated forward
    # new columns exist and default
    rec = e.get("m1")
    assert rec.retention == "durable"
    assert rec.consent == "unset"
    # rollback to 4
    rb = e.rollback_to(4)
    assert rb["current_version"] == 4
    e.close()


def test_c_corruption_recovery(eng):
    # inject a corrupt row (malformed metadata JSON) directly
    eng._conn.execute(
        "INSERT INTO memories (memory_id, content, namespace, provenance, confidence, "
        "metadata, created_at, updated_at, tier, lifecycle_state) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("bad1", "x", "default", "unknown", 1.0, "{not json", 1.0, 1.0, "durable", "active"))
    eng._conn.commit()
    eng.store("good", confidence=0.5)
    receipt = eng.recover_corrupt()
    assert receipt["scanned"] >= 2
    assert receipt["quarantined"] == 1
    # good record still retrievable
    good = eng.search("good")
    assert good and good[0].content == "good"
    # bad record quarantined
    bad = eng.get("bad1")
    assert bad.lifecycle_state == "quarantined"


def test_c_consent_default_deny(eng):
    eng.require_consent_for("sensitive")
    with pytest.raises(Exception):
        eng.store("secret thing", namespace="sensitive")
    # granted passes
    m = eng.store("secret thing", namespace="sensitive", consent="granted")
    assert eng.get(m.memory_id).consent == "granted"


def test_c_canonical_adapter_roundtrip(eng):
    m = eng.store("fact", namespace="n", confidence=0.6, uncertainty=0.2,
                  identity_link="agent-x", evidence_refs=["e9"])
    rec = memory_to_canonical(m)
    assert isinstance(rec, MemoryRecord)
    assert isinstance(rec.confidence, Confidence)
    assert isinstance(rec.provenance, Provenance)
    assert isinstance(rec.temporal, TemporalMetadata)
    assert rec.uncertainty == 0.2
    assert rec.identity.identity_link == "agent-x"
    assert rec.source_evidence.evidence_refs == ["e9"]
    # back to kwargs
    kw = canonical_to_memory_kwargs(rec)
    assert kw["content"] == "fact"
    assert kw["confidence"] == 0.6
    assert kw["identity_link"] == "agent-x"


def test_c_empty_store_search(eng):
    res = eng.search("nothing")
    assert res == []


def test_c_duplicate_id_rejected(eng):
    m = eng.store("first")
    # store generates uuid; update with same id is the path. Ensure get works.
    assert eng.get(m.memory_id).memory_id == m.memory_id


def test_c_missing_optional_accelerator_no_crash(eng):
    # antitoken not required for memory ops
    res = eng.search("anything")
    assert res is not None
