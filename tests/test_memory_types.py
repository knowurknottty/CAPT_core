"""Tests for memory convergence (M5): explicit memory-type taxonomy,
non-destructive revision, provenance chains, quarantine of malformed data,
and DREAM boundary (inferred output never overwrites canonical memory).
"""
import pytest

from capt_solo.memory.types import (
    MemoryType, MemoryRecord, validate_memory_record, memory_type_from_string,
    QuarantineReason,
)
from capt_solo.memory.engram import EngramStore, ConsolidationState, MemoryError_
from capt_solo.learning.dream import DreamConsolidator


def test_memory_type_taxonomy_explicit():
    # All required distinctions exist as distinct enum members.
    required = {
        "event", "observation", "episode", "interpretation", "inference",
        "belief", "identity_narrative", "autobiographical", "semantic",
        "revision", "correction", "supersession", "provenance", "replay",
    }
    present = {m.value for m in MemoryType}
    assert required <= present, f"missing memory types: {required - present}"


def test_memory_type_from_string():
    assert memory_type_from_string("semantic") == MemoryType.SEMANTIC
    with pytest.raises(ValueError):
        memory_type_from_string("not_a_type")


def test_non_destructive_revision():
    rec = MemoryRecord(record_id="r1", memory_type=MemoryType.OBSERVATION,
                        content="original fact")
    h0 = rec.content_hash()
    rev = rec.apply_revision(new_content="corrected fact", kind="correction")
    # canonical content unchanged by apply_revision (non-destructive)
    assert rec.content == "original fact"
    assert rec.content_hash() == h0
    assert rev.prior_content_hash == h0
    assert rev.kind == "correction"
    assert len(rec.revisions) == 1
    assert rec.is_correction is True


def test_provenance_chain_required_for_inferred():
    rec = MemoryRecord(record_id="r2", memory_type=MemoryType.INFERENCE,
                        content="inferred x", is_inferred=True)
    # no provenance_chain -> quarantined
    validate_memory_record(rec)
    assert rec.quarantined is True
    assert rec.quarantine_reason == QuarantineReason.MISSING_PROVENANCE.value
    # with provenance -> not quarantined
    rec2 = MemoryRecord(record_id="r3", memory_type=MemoryType.INFERENCE,
                         content="inferred y", is_inferred=True,
                         provenance_chain=["src:ep1"])
    validate_memory_record(rec2)
    assert rec2.quarantined is False


def test_quarantine_empty_content():
    rec = MemoryRecord(record_id="r4", memory_type=MemoryType.EVENT, content="")
    validate_memory_record(rec)
    assert rec.quarantined is True
    assert rec.quarantine_reason == QuarantineReason.EMPTY_CONTENT.value


def test_quarantine_uncertainty_bounds():
    rec = MemoryRecord(record_id="r5", memory_type=MemoryType.BELIEF,
                        content="x", uncertainty=1.5)
    validate_memory_record(rec)
    assert rec.quarantined is True
    assert rec.quarantine_reason == QuarantineReason.UNCERTAIN_WITHOUT_BOUNDS.value


def test_engram_memory_type_and_provenance():
    store = EngramStore(db_path=":memory:")
    e = store.store_trace(content="observed temperature 20C",
                          memory_type="observation",
                          provenance_chain=["sensor:thermometer-1"])
    assert e.memory_type == "observation"
    assert e.provenance_chain == ["sensor:thermometer-1"]
    got = store.get_engram(e.engram_id)
    assert got.memory_type == "observation"
    assert got.provenance_chain == ["sensor:thermometer-1"]


def test_engram_invalid_memory_type_rejected():
    store = EngramStore(db_path=":memory:")
    with pytest.raises(MemoryError_):
        store.store_trace(content="x", memory_type="bogus_type")


def test_engram_non_destructive_revise():
    store = EngramStore(db_path=":memory:")
    e = store.store_trace(content="initial claim")
    e2 = store.revise_engram(e.engram_id, new_content="revised claim",
                             kind="correction", note="fixed typo")
    # revision history preserved
    assert len(e2.revisions) == 1
    assert e2.revisions[0]["kind"] == "correction"
    assert e2.revisions[0]["prior_content_hash"]  # prior hash recorded
    # content updated but recoverable via revisions
    assert e2.content == "revised claim"


def test_dream_proposes_inferred_not_overwriting():
    store = EngramStore(db_path=":memory:")
    e = store.store_trace(content="raw observation",
                          source_evidence=["ev-1"])
    e = store.consolidate(e.engram_id)
    dc = DreamConsolidator(engram_store=store)
    proposed = dc.propose_knowledge_record(e)
    # Proposed record is explicitly labeled inferred and carries provenance.
    assert proposed.is_inferred is True
    assert proposed.memory_type == MemoryType.INFERENCE
    assert "engram:" + e.engram_id in proposed.provenance_chain
    # The canonical engram content is NOT mutated by proposing.
    assert store.get_engram(e.engram_id).content == "raw observation"
