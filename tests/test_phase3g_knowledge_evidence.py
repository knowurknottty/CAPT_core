"""Phase 3G — Knowledge / Evidence / Trust / Proof / Governance convergence tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from capt_solo.knowledge.evidence import EvidenceStore, VerificationStatus
from capt_solo.knowledge.knowledge import KnowledgeStore, KnowledgeStatus


@pytest.fixture
def stores():
    with tempfile.TemporaryDirectory() as d:
        ev = EvidenceStore(db_path=Path(d) / "ev.db")
        ks = KnowledgeStore(db_path=Path(d) / "kb.db", evidence_store=ev)
        yield ev, ks
        ks._eng.close()


def test_g_evidence_add_and_status(stores):
    ev, _ = stores
    rec = ev.add_evidence(claim="build passes", source_refs=["src-1"],
                          provenance="ci", confidence=0.9)
    assert rec.evidence_id
    assert rec.status == VerificationStatus.UNVERIFIED.value
    ev.set_status(rec.evidence_id, VerificationStatus.CORROBORATED.value)
    got = ev.get_evidence(rec.evidence_id)
    assert got.status == VerificationStatus.CORROBORATED.value


def test_g_evidence_contradiction(stores):
    ev, _ = stores
    a = ev.add_evidence(claim="x is true", source_refs=["s1"])
    b = ev.add_evidence(claim="x is false", source_refs=["s2"])
    ev.mark_contradiction(a.evidence_id, b.evidence_id)
    ga = ev.get_evidence(a.evidence_id)
    gb = ev.get_evidence(b.evidence_id)
    assert b.evidence_id in ga.contradicts
    assert a.evidence_id in gb.contradicts


def test_g_knowledge_requires_evidence_to_verify(stores):
    ev, ks = stores
    item = ks.add_knowledge(statement="system is stable", evidence_refs=[])
    # cannot verify without corroborating evidence
    with pytest.raises(Exception):
        ks.promote_status(item.knowledge_id, KnowledgeStatus.VERIFIED.value)
    # add corroborating evidence, link, then verify
    e = ev.add_evidence(claim="system stable", source_refs=["ci"],
                        status=VerificationStatus.CORROBORATED.value)
    ks.link_evidence(item.knowledge_id, e.evidence_id)
    ks.promote_status(item.knowledge_id, KnowledgeStatus.VERIFIED.value)
    got = ks.get_knowledge(item.knowledge_id)
    assert got.status == KnowledgeStatus.VERIFIED.value


def test_g_knowledge_status_progression(stores):
    ev, ks = stores
    item = ks.add_knowledge(statement="hyp", evidence_refs=[],
                            status=KnowledgeStatus.HYPOTHESIS.value)
    ks.promote_status(item.knowledge_id, KnowledgeStatus.SUPPORTED.value)
    assert ks.get_knowledge(item.knowledge_id).status == KnowledgeStatus.SUPPORTED.value


def test_g_evidence_ontology_bridge(stores):
    ev, _ = stores
    rec = ev.add_evidence(claim="c", source_refs=["s"], provenance="test")
    term = ev.to_ontology(rec.evidence_id)
    assert term is not None
    assert term.kind == "evidence_record"
    assert term.payload["claim"] == "c"


def test_g_list_filters(stores):
    ev, ks = stores
    ev.add_evidence(claim="a", source_refs=["s"], status=VerificationStatus.VERIFIED.value)
    ev.add_evidence(claim="b", source_refs=["s"], status=VerificationStatus.UNVERIFIED.value)
    verified = ev.list_evidence(status=VerificationStatus.VERIFIED.value)
    assert len(verified) == 1
    assert verified[0].claim == "a"


def test_g_export_import_roundtrip(stores):
    ev, ks = stores
    item = ks.add_knowledge(statement="persist me", evidence_refs=["e1"],
                            confidence=0.7)
    kid = item.knowledge_id
    path = Path(tempfile.mkdtemp()) / "kb.json"
    ks._eng.export_json(path)
    with tempfile.TemporaryDirectory() as d:
        ks2 = KnowledgeStore(db_path=Path(d) / "kb2.db")
        ks2._eng.import_json(path)
        got = ks2.get_knowledge(kid)
        assert got is not None
        assert got.statement == "persist me"
        assert got.confidence == 0.7
        ks2._eng.close()
