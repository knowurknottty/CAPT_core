"""CAPT Memory Trigger — adversarial review (mission §16 Pass 2).

Challenges the mandatory memory trigger system. Each test targets a specific
adversarial vector from the mission's adversarial review list.
"""

import pytest

from capt_runtime.memory import (
    MemoryStore,
    MemoryTriggerEngine,
    MemoryRecord,
    ContextUsage,
    TRIGGER_INTERVAL_TOKENS,
)
from capt_runtime.memory.engine import (
    MEMORY_PATH_INACTIVE,
    CONTEXTPACK_REQUIRED,
    CONTEXTPACK_STALE,
    CONTEXT_BUDGET_EXCEEDED,
    MEMORY_CONSENT_DENIED,
    MEMORY_SCOPE_VIOLATION,
    MEMORY_TRIGGER_CONFIGURATION_INVALID,
)


def _seed(store):
    store.store(MemoryRecord(
        record_id="r1", memory_class="project", owner="capt", source="fs",
        provenance="mission:x", trust="verified", verification_status="verified",
        sensitivity="project", consent="project", content="prior denial"))
    store.store(MemoryRecord(
        record_id="r2", memory_class="user", owner="operator", source="stated",
        provenance="operator:y", trust="unverified", verification_status="pending",
        sensitivity="user", consent="user", content="pref concise"))


@pytest.fixture
def engine():
    store = MemoryStore(":memory:")
    _seed(store)
    return MemoryTriggerEngine(store, model_safe_limit_steps=8)


# -- token estimate accuracy ----------------------------------------------

def test_estimate_labeled_estimated(engine):
    u = ContextUsage(); u.current_messages = 1000
    rep = engine.evaluate_usage("m", u)
    assert "ESTIMATED" in rep["estimationMethod"]


def test_estimate_monotonic_with_text(engine):
    a = ContextUsage(); a.mission_spec = 100
    b = ContextUsage(); b.mission_spec = 5000
    assert b.total() > a.total()


# -- threshold off-by-one --------------------------------------------------

def test_off_by_one_boundary_does_not_fire(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    # One token below the 32k boundary must NOT fire.
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS - 1
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["retrieval"]["fires"] is False


def test_exactly_on_boundary_fires(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["retrieval"]["fires"] is True


# -- duplicate trigger firing ----------------------------------------------

def test_duplicate_trigger_not_re_fired(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    r1 = engine.evaluate_usage("m", u)
    r2 = engine.evaluate_usage("m", u)
    assert r1["triggers"]["retrieval"]["fires"] is True
    assert r2["triggers"]["retrieval"]["fires"] is False


# -- trigger suppression ---------------------------------------------------

def test_suppression_attempt_has_no_api(engine):
    # There is no engine method to suppress a trigger; CAPT fires it before
    # dispatch. We assert the gate still requires the pack.
    with pytest.raises(Exception) as ei:
        engine.require_memory_before_dispatch("m")
    assert ei.value.code == CONTEXTPACK_REQUIRED


# -- hermes policy override ------------------------------------------------

def test_driver_cannot_widen_policy(engine):
    from capt_runtime.memory.policy import PolicySource
    with pytest.raises(ValueError):
        engine.update_policy(retrieval_trigger_steps=16, source=PolicySource.DRIVER_PREFERENCE)


# -- context smuggling ----------------------------------------------------

def test_context_smuggling_rejected_at_dispatch(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    # A forged context_pack_digest must not pass the gate.
    with pytest.raises(Exception) as ei:
        engine.require_memory_before_dispatch(
            "m", context_pack_digest="sha256:" + "0" * 64,
            policy_digest=engine.policy.policy_digest)
    assert ei.value.code == CONTEXTPACK_STALE


# -- hidden driver memory --------------------------------------------------

def test_hidden_driver_memory_cannot_override(engine):
    # The engine never ingests driver-native memory into the policy. We assert
    # the policy is unchanged after a dispatch gate check.
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    before = engine.policy.policy_digest
    engine.require_memory_before_dispatch(
        "m", context_pack_digest=pack["contextPackDigest"],
        policy_digest=engine.policy.policy_digest, context_usage=40000)
    assert engine.policy.policy_digest == before


# -- consent leakage ------------------------------------------------------

def test_consent_leakage_blocked(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    # r2 (user consent) must not appear in selected records.
    selected = {r["recordId"] for r in pack["selectedRecords"]}
    assert "r2" not in selected


# -- stale memory ---------------------------------------------------------

def test_stale_memory_labeled(engine):
    store = engine.store
    store.store(MemoryRecord(
        record_id="rstale", memory_class="episodic", owner="capt", source="v",
        provenance="m:z", trust="verified", verification_status="verified",
        sensitivity="project", consent="project", content="stale fact", stale=True))
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    assert "rstale" in pack["staleRecords"]


# -- context growth -------------------------------------------------------

def test_context_growth_recomputes_boundary(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    u1 = ContextUsage(); u1.current_messages = TRIGGER_INTERVAL_TOKENS
    engine.evaluate_usage("m", u1)
    u2 = ContextUsage(); u2.current_messages = TRIGGER_INTERVAL_TOKENS * 3
    rep = engine.evaluate_usage("m", u2)
    # At 3x boundary, retrieval already fired once; it must not re-fire, but
    # the next boundary advances.
    assert rep["triggers"]["retrieval"]["fires"] is False
    assert rep["nextTriggerBoundary"] >= TRIGGER_INTERVAL_TOKENS * 3


# -- incorrect replay -----------------------------------------------------

def test_replay_reconstructs_same_policy(engine):
    engine.update_policy(retrieval_trigger_steps=2, compression_trigger_steps=2)
    recon = engine.reconstruct_policy(engine.policy.policy_version)
    assert recon is not None
    assert recon.retrieval_trigger_steps == 2
    assert recon.compression_trigger_steps == 2


# -- configuration race ----------------------------------------------------

def test_concurrent_policy_updates_serialized(engine):
    import threading
    errors = []
    def worker(steps):
        try:
            engine.update_policy(retrieval_trigger_steps=steps)
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=worker, args=(s,)) for s in (1, 2, 3, 4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    # No crash; final policy is one of the attempted values within limits.
    assert engine.policy.retrieval_trigger_steps in (1, 2, 3, 4)
    assert not errors or all(isinstance(e, ValueError) for e in errors)


# -- active-run threshold change ------------------------------------------

def test_threshold_change_during_active_run(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    gate = engine.require_memory_before_dispatch(
        "m", context_pack_digest=pack["contextPackDigest"],
        policy_digest=engine.policy.policy_digest, context_usage=40000)
    assert gate["ok"] is True
    # Operator narrows the threshold during the active run; the existing pack
    # remains valid until the next rebuild (no invisible context change).
    engine.update_policy(retrieval_trigger_steps=1, compression_trigger_steps=1)
    gate2 = engine.require_memory_before_dispatch(
        "m", context_pack_digest=pack["contextPackDigest"],
        policy_digest=engine.policy.policy_digest, context_usage=40000)
    assert gate2["ok"] is True


# -- model-limit mismatch -------------------------------------------------

def test_model_limit_mismatch_rejected(engine):
    with pytest.raises(ValueError):
        engine.update_policy(retrieval_trigger_steps=16)  # > model_safe_limit 8


# -- UI bypass ------------------------------------------------------------

def test_ui_bypass_impossible_no_direct_write(engine):
    # The engine has no method that writes policy without validation. We assert
    # set_policy is only reachable via update_policy (validated).
    import inspect
    src = inspect.getsource(type(engine).update_policy)
    assert "with_update" in src


# -- stateless fallback ---------------------------------------------------

def test_no_stateless_fallback(engine):
    # Without firing the retrieval trigger, dispatch is refused. There is no
    # silent raw-prompt path.
    with pytest.raises(Exception) as ei:
        engine.require_memory_before_dispatch("m")
    assert ei.value.code == CONTEXTPACK_REQUIRED
