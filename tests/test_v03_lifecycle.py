"""CAPT Solo v0.3 — Adaptive Memory Lifecycle tests.

Covers: tiers, lifecycle states, valid/invalid transitions, transition
audit history, promotion evidence (no promotion by repetition alone),
pin protection, archive/restore, decay ranking effects, no silent deletion,
retention policies.
"""

import pytest

from capt_solo.core.errors import MemoryError_
from capt_solo.lifecycle.lifecycle import (
    LifecycleEngine, LifecycleState, MemoryTier, RetentionClass,
    VALID_TRANSITIONS, PROMOTION_EVIDENCE,
)
from capt_solo.memory.engine import MemoryEngine


def _store(eng, tier="durable", state="active", **kw):
    return eng.store("fact content", tier=tier, lifecycle_state=state, **kw)


# --- tiers & states -------------------------------------------------------

def test_tiers_and_states_enums():
    assert MemoryTier.DURABLE.value == "durable"
    assert LifecycleState.PINNED.value == "pinned"
    assert "working" in {t.value for t in MemoryTier}
    assert "rejected" in {s.value for s in LifecycleState}


def test_store_accepts_tier_and_state(mem_engine):
    m = _store(mem_engine, tier="session", state="transient")
    assert m.tier == "session"
    assert m.lifecycle_state == "transient"


def test_default_tier_and_state(mem_engine):
    m = mem_engine.store("x")
    assert m.tier == "durable"  # default
    assert m.lifecycle_state == "active"  # default


# --- transitions ----------------------------------------------------------

def test_valid_transition_records_history(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="candidate")
    tid = lc.transition(m.memory_id, "active", reason="review", actor="user")
    assert isinstance(tid, str) and tid
    assert mem_engine.get(m.memory_id).lifecycle_state == "active"
    hist = lc.transition_history(m.memory_id)
    assert len(hist) == 1
    assert hist[0]["previous_state"] == "candidate"
    assert hist[0]["new_state"] == "active"
    assert hist[0]["actor"] == "user"
    assert hist[0]["reason"] == "review"
    assert "config_snapshot" in hist[0]


def test_invalid_transition_fails(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="active")
    with pytest.raises(MemoryError_):
        lc.transition(m.memory_id, "pinned")  # active -> pinned not allowed
    # state unchanged
    assert mem_engine.get(m.memory_id).lifecycle_state == "active"


def test_transition_missing_memory(mem_engine):
    lc = LifecycleEngine(mem_engine)
    with pytest.raises(MemoryError_):
        lc.transition("nope", "active")


def test_transition_does_not_change_trust(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="candidate", metadata={"trust_state": "inferred_fact"})
    lc.transition(m.memory_id, "active")
    meta = mem_engine.get(m.memory_id).metadata
    assert meta.get("trust_state") == "inferred_fact"


# --- promotion ------------------------------------------------------------

def test_evaluate_promotion_explains_missing_evidence(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="candidate")
    ev = lc.evaluate_promotion(m.memory_id)
    assert ev.current_state == "candidate"
    assert "durable" in ev.eligible_transitions
    assert ev.missing_evidence  # no evidence recorded yet
    # candidate -> durable does NOT require explicit user approval (only pinned does)
    assert ev.user_approval_required is False


def test_promote_requires_evidence(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="candidate")
    with pytest.raises(MemoryError_):
        lc.promote(m.memory_id, "durable", actor="user")  # no evidence


def test_promote_by_repetition_alone_rejected(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="candidate")
    with pytest.raises(MemoryError_):
        lc.promote(m.memory_id, "durable", actor="user",
                   evidence=["repetition_only"])


def test_promote_with_valid_evidence(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="candidate")
    tid = lc.promote(m.memory_id, "durable", actor="user",
                     evidence=["user_approval", "verified_test_result"])
    assert mem_engine.get(m.memory_id).lifecycle_state == "durable"
    meta = mem_engine.get(m.memory_id).metadata
    assert "user_approval" in meta["promotion_evidence"]


def test_promote_to_pinned_requires_user(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="durable")
    with pytest.raises(MemoryError_):
        lc.promote(m.memory_id, "pinned", actor="system",
                   evidence=["user_approval"])
    # user actor allowed
    tid = lc.promote(m.memory_id, "pinned", actor="user",
                     evidence=["user_approval"])
    assert mem_engine.get(m.memory_id).lifecycle_state == "pinned"


def test_reject_candidate(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="candidate")
    lc.reject_candidate(m.memory_id, reason="low value")
    assert mem_engine.get(m.memory_id).lifecycle_state == "rejected"


def test_pin_requires_user_actor(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="durable")
    with pytest.raises(MemoryError_):
        lc.pin(m.memory_id, actor="system")
    lc.pin(m.memory_id, actor="user")
    assert mem_engine.get(m.memory_id).lifecycle_state == "pinned"


# --- archive / restore / decay -------------------------------------------

def test_archive_and_restore(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="active")
    lc.archive(m.memory_id, reason="stale")
    assert mem_engine.get(m.memory_id).lifecycle_state == "archived"
    lc.restore(m.memory_id, reason="needed")
    assert mem_engine.get(m.memory_id).lifecycle_state == "active"


def test_restore_only_from_archived_or_expired(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="active")
    with pytest.raises(MemoryError_):
        lc.restore(m.memory_id)


def test_decay_affects_ranking_not_data(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="active")
    # simulate age by setting updated_at far in past
    mem_engine._conn.execute(
        "UPDATE memories SET updated_at=? WHERE memory_id=?",
        (mem_engine.get(m.memory_id).updated_at - 400 * 86400, m.memory_id))
    mem_engine._conn.commit()
    assessment = lc.evaluate_decay(m.memory_id)
    assert assessment["decay_score"] > 0.0
    assert assessment["protected"] is False
    applied = lc.apply_decay(m.memory_id)
    assert applied["applied"] is True
    # canonical data intact
    assert mem_engine.get(m.memory_id).content == "fact content"
    assert mem_engine.get(m.memory_id).lifecycle_state == "active"


def test_pinned_is_protected_from_decay(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="durable")
    lc.pin(m.memory_id, actor="user")
    assessment = lc.evaluate_decay(m.memory_id)
    assert assessment["protected"] is True
    applied = lc.apply_decay(m.memory_id)
    assert applied["applied"] is False


def test_no_silent_deletion(mem_engine):
    lc = LifecycleEngine(mem_engine)
    m = _store(mem_engine, state="active")
    lc.expire(m.memory_id, reason="test")
    # still retrievable; state changed, row present
    assert mem_engine.get(m.memory_id) is not None
    assert mem_engine.get(m.memory_id).lifecycle_state == "expired"


# --- retention policies ---------------------------------------------------

def test_retention_policy_set_get(mem_engine):
    lc = LifecycleEngine(mem_engine)
    lc.set_retention_policy("proj", RetentionClass.LONG_TERM.value, decay_rate=0.1)
    pol = lc.get_retention_policy("proj")
    assert pol["retention_class"] == "long_term"
    assert pol["decay_rate"] == 0.1


def test_retention_policy_bad_class(mem_engine):
    lc = LifecycleEngine(mem_engine)
    with pytest.raises(MemoryError_):
        lc.set_retention_policy("proj", "bogus")
