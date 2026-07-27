"""Phase 3I — HMC / ENGRAM / DREAM canonicalization tests.

Clean implementations in CAPT_core (external ecosystem source NOT copied;
licensing gate [L] avoided).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from capt_solo.memory.hmc import HolographicMemoryCompressor, HolographicVector
from capt_solo.memory.engram import (
    ConsolidationState, EngramStore,
)
from capt_solo.knowledge.evidence import EvidenceStore, VerificationStatus
from capt_solo.learning.dream import DreamConsolidator


# ---------------- HMC ----------------
def test_i_hmc_deterministic():
    c = HolographicMemoryCompressor(dim=64)
    v1 = c.compress("the build passed all tests")
    v2 = c.compress("the build passed all tests")
    assert v1.components == v2.components
    assert v1.source_hash == v2.source_hash


def test_i_hmc_similarity():
    c = HolographicMemoryCompressor(dim=64)
    a = c.compress("user fixed the broken build")
    b = c.compress("user fixed the broken build quickly")
    d = c.compress("completely unrelated content about weather")
    assert a.similarity(b) > a.similarity(d)


def test_i_hmc_nearest():
    c = HolographicMemoryCompressor(dim=64)
    cands = ["fix the build", "write documentation", "deploy to staging"]
    best, sim = c.nearest("repair the build pipeline", cands)
    assert best == "fix the build"
    assert sim > 0.0


# ---------------- ENGRAM ----------------
@pytest.fixture
def engram():
    with tempfile.TemporaryDirectory() as d:
        e = EngramStore(db_path=Path(d) / "eng.db")
        yield e
        e._eng.close()


def test_i_engram_store_and_consolidate(engram):
    e = engram.store_trace(content="observed: tests green",
                           source_evidence=["ev-1"])
    assert e.state == ConsolidationState.RAW.value
    engram.consolidate(e.engram_id)
    got = engram.get_engram(e.engram_id)
    assert got.state == ConsolidationState.CONSOLIDATED.value
    assert got.consolidated_at is not None


def test_i_engram_list_by_state(engram):
    engram.store_trace(content="a")
    b = engram.store_trace(content="b")
    engram.consolidate(b.engram_id)
    consolidated = engram.list_engrams(state=ConsolidationState.CONSOLIDATED.value)
    assert len(consolidated) == 1


# ---------------- DREAM ----------------
def test_i_dream_consolidation_as_learning():
    with tempfile.TemporaryDirectory() as d:
        ev = EvidenceStore(db_path=Path(d) / "ev.db")
        en = EngramStore(db_path=Path(d) / "en.db")
        # corroborating evidence
        e = ev.add_evidence(claim="tests green", source_refs=["ci"],
                            status=VerificationStatus.CORROBORATED.value)
        en.store_trace(content="system stable", source_evidence=[e.evidence_id])
        dc = DreamConsolidator(engram_store=en, evidence_store=ev)
        sess = dc.run()
        assert sess.processed == 1
        assert sess.consolidated == 1
        assert sess.knowledge_created == 1


def test_i_dream_withholds_without_evidence():
    with tempfile.TemporaryDirectory() as d:
        ev = EvidenceStore(db_path=Path(d) / "ev.db")
        en = EngramStore(db_path=Path(d) / "en.db")
        en.store_trace(content="uncorroborated claim")
        dc = DreamConsolidator(engram_store=en, evidence_store=ev)
        sess = dc.run()
        assert sess.processed == 1
        assert sess.knowledge_created == 0
        assert any("withheld" in n for n in sess.notes)
