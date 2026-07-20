"""CAPT Solo v0.3 — Retrieval Feedback + Bounded Adaptation tests.

Covers: feedback recording, bounded weight updates, reset, no trust mutation,
no truth mutation, no cross-project contamination.
"""

import pytest

from capt_solo.lifecycle.feedback import RetrievalFeedback, FEEDBACK_KINDS, ADAPTATION_KEYS
from capt_solo.memory.engine import MemoryEngine
from capt_solo.lifecycle.lifecycle import LifecycleEngine


@pytest.fixture
def fb(mem_engine):
    return RetrievalFeedback(mem_engine)


def test_feedback_kinds_valid():
    for k in ["useful", "irrelevant", "outdated", "contradictory",
              "misleading", "incomplete", "too_verbose", "too_compressed"]:
        assert k in FEEDBACK_KINDS


def test_record_feedback(fb):
    fid = fb.record("useful", memory_id="m1", namespace="proj", query="q")
    assert fid
    rows = fb._eng._conn.execute(
        "SELECT * FROM retrieval_feedback WHERE feedback_id=?", (fid,)).fetchone()
    assert rows["feedback_kind"] == "useful"
    assert rows["memory_id"] == "m1"


def test_bounded_weight_update(fb):
    for _ in range(3):
        fb.record("useful", namespace="proj", memory_id="m1")
    state = fb.get_adaptation_state("proj")
    # preferred_recency or preferred_kind should shift but stay bounded
    for k, v in state["adaptation"].items():
        assert -1.0 <= v <= 1.0


def test_adaptation_reset(fb):
    fb.record("useful", namespace="proj")
    fb.reset_adaptation("proj")
    state = fb.get_adaptation_state("proj")
    assert all(v == 0.0 for v in state["adaptation"].values())


def test_feedback_does_not_mutate_trust(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = mem_engine.store("x", lifecycle_state="candidate",
                         metadata={"trust_state": "inferred_fact"})
    fb = RetrievalFeedback(mem_engine)
    fb.record("useful", memory_id=m.memory_id, namespace="proj")
    # trust unchanged
    assert mem_engine.get(m.memory_id).metadata["trust_state"] == "inferred_fact"
    # lifecycle unchanged
    assert mem_engine.get(m.memory_id).lifecycle_state == "candidate"


def test_feedback_does_not_promote_or_delete(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = mem_engine.store("x", lifecycle_state="candidate")
    fb = RetrievalFeedback(mem_engine)
    fb.record("useful", memory_id=m.memory_id, namespace="proj")
    # still candidate, not durable, not deleted
    assert mem_engine.get(m.memory_id).lifecycle_state == "candidate"


def test_no_cross_project_contamination(fb):
    fb.record("useful", namespace="projA", memory_id="m1")
    fb.record("irrelevant", namespace="projB", memory_id="m2")
    stateA = fb.get_adaptation_state("projA")
    stateB = fb.get_adaptation_state("projB")
    # adaptations differ by project; projA biased useful, projB biased irrelevant
    assert stateA["adaptation"] != stateB["adaptation"]


def test_explain_weight_change(fb):
    fb.record("useful", namespace="proj", memory_id="m1")
    expl = fb.explain_weight_change("useful", "proj")
    assert "would_change" in expl
    assert "bounded" in expl
    assert expl["feedback_kind"] == "useful"


def test_adaptation_keys_complete():
    for k in ADAPTATION_KEYS:
        assert k in {
            "preferred_memory_kind", "preferred_recency_balance",
            "preferred_verbosity", "preferred_procedural_detail",
            "preferred_conflict_visibility", "preferred_context_density",
        }
