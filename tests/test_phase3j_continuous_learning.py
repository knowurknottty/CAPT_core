"""Phase 3J — Continuous Learning foundation tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from capt_solo.knowledge.evidence import EvidenceStore, VerificationStatus
from capt_solo.knowledge.knowledge import KnowledgeStore, KnowledgeStatus
from capt_solo.learning.continuous import (
    ContinuousLearner, FeedbackKind,
)


@pytest.fixture
def learner():
    with tempfile.TemporaryDirectory() as d:
        ev = EvidenceStore(db_path=Path(d) / "ev.db")
        ks = KnowledgeStore(db_path=Path(d) / "kb.db", evidence_store=ev)
        cl = ContinuousLearner(knowledge_store=ks, evidence_store=ev)
        yield cl, ks, ev
        ks._eng.close()


def test_j_feedback_adjusts_confidence(learner):
    cl, ks, _ = learner
    item = ks.add_knowledge(statement="x", evidence_refs=[], confidence=0.5)
    ev = cl.ingest_feedback(knowledge_id=item.knowledge_id,
                            feedback=FeedbackKind.CORRECT.value)
    assert ev.delta_confidence > 0
    assert ks.get_knowledge(item.knowledge_id).confidence > 0.5


def test_j_incorrect_lowers_confidence(learner):
    cl, ks, _ = learner
    item = ks.add_knowledge(statement="x", evidence_refs=[], confidence=0.8)
    cl.ingest_feedback(knowledge_id=item.knowledge_id,
                       feedback=FeedbackKind.INCORRECT.value)
    assert ks.get_knowledge(item.knowledge_id).confidence < 0.8


def test_j_contradiction_downgrades_verified(learner):
    cl, ks, ev = learner
    e = ev.add_evidence(claim="x", source_refs=["s"],
                        status=VerificationStatus.CORROBORATED.value)
    item = ks.add_knowledge(statement="x", evidence_refs=[e.evidence_id],
                            confidence=0.9)
    ks.promote_status(item.knowledge_id, KnowledgeStatus.VERIFIED.value)
    assert ks.get_knowledge(item.knowledge_id).status == KnowledgeStatus.VERIFIED.value
    cl.ingest_feedback(knowledge_id=item.knowledge_id,
                       feedback=FeedbackKind.CONTRADICTION.value)
    assert ks.get_knowledge(item.knowledge_id).status == KnowledgeStatus.CONTRADICTED.value


def test_j_confidence_bounded(learner):
    cl, ks, _ = learner
    item = ks.add_knowledge(statement="x", evidence_refs=[], confidence=0.95)
    # many correct feedbacks must not exceed 1.0
    for _ in range(10):
        cl.ingest_feedback(knowledge_id=item.knowledge_id,
                           feedback=FeedbackKind.CORRECT.value)
    assert ks.get_knowledge(item.knowledge_id).confidence <= 1.0


def test_j_learning_log_and_drift(learner):
    cl, ks, _ = learner
    item = ks.add_knowledge(statement="x", evidence_refs=[], confidence=0.5)
    cl.ingest_feedback(knowledge_id=item.knowledge_id,
                       feedback=FeedbackKind.CONTRADICTION.value)
    log = cl.learning_log(knowledge_id=item.knowledge_id)
    assert len(log) == 1
    drift = cl.detect_drift(item.knowledge_id)
    assert len(drift) == 1


def test_j_run_cycle_runs_dream(learner):
    cl, ks, ev = learner
    e = ev.add_evidence(claim="stable", source_refs=["ci"],
                        status=VerificationStatus.CORROBORATED.value)
    from capt_solo.memory.engram import EngramStore, ConsolidationState
    en = EngramStore(engine=ks._eng)
    en.store_trace(content="stable", source_evidence=[e.evidence_id])
    report = cl.run_cycle()
    assert report["dream_processed"] >= 1
    assert report["learning_events"] >= 0
