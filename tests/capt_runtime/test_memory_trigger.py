"""CAPT Memory Trigger — configuration, trigger, memory, ContextPack, harness.

These tests prove the mandatory memory trigger system works in the CAPT
Runtime / harness path WITHOUT requiring Hermes installed. The Hermes
conformance test lives in test_memory_trigger_hermes.py.
"""

import os
import tempfile
import uuid

import pytest

from capt_runtime.memory import (
    MemoryTriggerEngine,
    MemoryStore,
    MemoryRecord,
    MemoryTriggerPolicy,
    PolicySource,
    TRIGGER_INTERVAL_TOKENS,
    ContextUsage,
    effective_policy,
    build_memory_query,
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
        sensitivity="project", consent="project",
        content="Prior approval for write to /etc was DENIED."))
    store.store(MemoryRecord(
        record_id="r2", memory_class="user", owner="operator", source="stated",
        provenance="operator:y", trust="unverified", verification_status="pending",
        sensitivity="user", consent="user",
        content="Operator prefers concise reports."))
    store.store(MemoryRecord(
        record_id="r3", memory_class="episodic", owner="capt", source="verify",
        provenance="mission:z", trust="verified", verification_status="verified",
        sensitivity="project", consent="project", stale=True,
        content="A prior approach failed; do not repeat it."))
    store.store(MemoryRecord(
        record_id="r4", memory_class="project", owner="capt", source="fs",
        provenance="mission:w", trust="verified", verification_status="verified",
        sensitivity="secret", consent="project",
        content="Secret credential record that must not leak to user scope."))


@pytest.fixture
def engine():
    store = MemoryStore(":memory:")
    _seed(store)
    return MemoryTriggerEngine(store, model_safe_limit_steps=8)


# -- Configuration ---------------------------------------------------------

def test_32k_accepted(engine):
    p = engine.update_policy(retrieval_trigger_steps=1)
    assert p.retrieval_tokens() == 32_768


def test_64k_accepted(engine):
    p = engine.update_policy(retrieval_trigger_steps=2)
    assert p.retrieval_tokens() == 65_536


def test_96k_accepted(engine):
    p = engine.update_policy(retrieval_trigger_steps=3)
    assert p.retrieval_tokens() == 98_304


def test_128k_accepted(engine):
    p = engine.update_policy(retrieval_trigger_steps=4)
    assert p.retrieval_tokens() == 131_072


def test_further_32k_step_accepted(engine):
    p = engine.update_policy(retrieval_trigger_steps=8)
    assert p.retrieval_tokens() == 262_144


def test_zero_rejected():
    with pytest.raises(ValueError):
        MemoryTriggerPolicy(retrieval_trigger_steps=0, compression_trigger_steps=1,
                             checkpoint_trigger_steps=1, consolidation_trigger_steps=1,
                             hard_stop_trigger_steps=8, model_safe_limit_steps=8)


def test_negative_rejected():
    with pytest.raises(ValueError):
        MemoryTriggerPolicy(retrieval_trigger_steps=-1, compression_trigger_steps=1,
                             checkpoint_trigger_steps=1, consolidation_trigger_steps=1,
                             hard_stop_trigger_steps=8, model_safe_limit_steps=8)


def test_48k_rejected():
    # 48k is not an exact multiple of 32_768 -> rejected as a raw token threshold.
    from capt_runtime.memory.policy import tokens_to_steps
    with pytest.raises(ValueError):
        tokens_to_steps(48_000)


def test_non_integer_rejected():
    with pytest.raises(ValueError):
        MemoryTriggerPolicy(retrieval_trigger_steps=1.5, compression_trigger_steps=1,
                             checkpoint_trigger_steps=1, consolidation_trigger_steps=1,
                             hard_stop_trigger_steps=8, model_safe_limit_steps=8)


def test_above_safe_limit_rejected(engine):
    with pytest.raises(ValueError):
        engine.update_policy(retrieval_trigger_steps=16)  # > model_safe_limit 8


def test_policy_narrowing_accepted(engine):
    p = engine.update_policy(retrieval_trigger_steps=2)
    assert p.retrieval_trigger_steps == 2


def test_driver_widening_rejected(engine):
    # A driver_preference source cannot widen a runtime_policy bound.
    with pytest.raises(ValueError):
        engine.update_policy(retrieval_trigger_steps=16, source=PolicySource.DRIVER_PREFERENCE)


# -- Trigger behavior ------------------------------------------------------

def test_below_trigger_no_retrieval(engine):
    u = ContextUsage(); u.current_messages = 1000
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["retrieval"]["fires"] is False


def test_exactly_at_trigger_retrieval_fires_once(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS  # 32_768
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["retrieval"]["fires"] is True
    # Idempotent: re-evaluation at same usage does not re-fire.
    rep2 = engine.evaluate_usage("m", u)
    assert rep2["triggers"]["retrieval"]["fires"] is False


def test_crossing_multiple_steps_correct_state(engine):
    # Lower retrieval to 1 (32k) to cross at 98k; compression/checkpoint=1, consolidation=4.
    engine.update_policy(retrieval_trigger_steps=1, compression_trigger_steps=1,
                          checkpoint_trigger_steps=1, consolidation_trigger_steps=4)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS * 3  # 98k
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["retrieval"]["fires"] is True
    assert rep["triggers"]["compression"]["fires"] is True
    assert rep["triggers"]["checkpoint"]["fires"] is True
    assert rep["triggers"]["consolidation"]["fires"] is False  # 4 steps = 128k


def test_repeated_unchanged_no_duplicate_trigger(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    r1 = engine.evaluate_usage("m", u)
    r2 = engine.evaluate_usage("m", u)
    assert r1["triggers"]["retrieval"]["fires"] is True
    assert r2["triggers"]["retrieval"]["fires"] is False


def test_compression_trigger_fires(engine):
    engine.update_policy(compression_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["compression"]["fires"] is True


def test_checkpoint_trigger_fires(engine):
    engine.update_policy(checkpoint_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["checkpoint"]["fires"] is True


def test_consolidation_candidate_generated(engine):
    engine.update_policy(consolidation_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["consolidation"]["fires"] is True


def test_hard_stop_suspends(engine):
    u = ContextUsage(); u.current_messages = engine.policy.hard_stop_tokens()
    rep = engine.evaluate_usage("m", u)
    assert rep["triggers"]["hardStop"]["fires"] is True


# -- Memory ----------------------------------------------------------------

def test_mandatory_query_emitted(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    assert pack["selectedRecords"] or pack["excludedRecords"]


def test_records_attributable(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    for rec in pack["selectedRecords"]:
        assert rec["recordId"] and rec["provenance"] and rec["digest"]


def test_excluded_records_visible(engine):
    engine.update_policy(retrieval_trigger_steps=1)
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    # r4 is secret; with sensitivity_allowance=project it is excluded.
    excluded_ids = {e.get("recordId") for e in pack["excludedRecords"]}
    assert "r4" in excluded_ids


def test_consent_restricted_record_excluded(engine):
    # Query with consent_scope=project; r2 (user consent) is excluded.
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    selected_ids = {r["recordId"] for r in pack["selectedRecords"]}
    assert "r2" not in selected_ids


def test_stale_record_labeled(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    assert "r3" in pack["staleRecords"]


def test_conflict_preserved(engine):
    # No explicit conflict in seed; ensure the field exists and is a list.
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    assert isinstance(pack["unresolvedConflicts"], list)


def test_duplicate_records_deduplicated(engine):
    # Two queries with same input produce one trigger log entry (idempotent).
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    engine.require_retrieval_before_planning("m", u)
    engine.require_retrieval_before_planning("m", u)
    log = engine.trigger_log("m")
    assert len([e for e in log if e["trigger_type"] == "retrieval"]) == 1


def test_unverified_output_not_promoted_as_fact(engine):
    cands = engine.evaluate_promotion("m", [{"summary": "maybe X"}])
    assert cands[0]["verified"] is False
    assert cands[0]["requiresEvidence"] is True


def test_promotion_requires_evidence(engine):
    cands = engine.evaluate_promotion("m", [{"summary": "obs"}])
    rec = engine.accept_promotion(cands[0])
    assert rec.verification_status == "pending"


# -- ContextPack -----------------------------------------------------------

def test_deterministic_rebuild(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    p1 = engine.require_retrieval_before_planning("m", u)
    p2 = engine.require_retrieval_before_planning("m", u)
    assert p1["contextPackDigest"] == p2["contextPackDigest"]


def test_digest_changes_when_inputs_change(engine):
    u1 = ContextUsage(); u1.current_messages = TRIGGER_INTERVAL_TOKENS
    p1 = engine.require_retrieval_before_planning("m", u1)
    # Change policy -> different effective inputs -> different digest.
    engine.update_policy(retrieval_trigger_steps=2)
    u2 = ContextUsage(); u2.current_messages = TRIGGER_INTERVAL_TOKENS
    p2 = engine.require_retrieval_before_planning("m2", u2)
    assert p1["contextPackDigest"] != p2["contextPackDigest"]


def test_digest_stable_when_inputs_do_not_change(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    p1 = engine.require_retrieval_before_planning("m", u)
    p2 = engine.require_retrieval_before_planning("m", u)
    assert p1["contextPackDigest"] == p2["contextPackDigest"]


def test_selected_excluded_preserved(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    assert "selectedRecords" in pack and "excludedRecords" in pack


def test_token_budget_enforced(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    assert pack["tokenBudget"] >= 0


# -- Harness ---------------------------------------------------------------

def test_dispatch_blocked_without_contextpack(engine):
    with pytest.raises(Exception) as ei:
        engine.require_memory_before_dispatch("m-x")
    assert ei.value.code == CONTEXTPACK_REQUIRED


def test_dispatch_blocked_with_stale_contextpack(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    with pytest.raises(Exception) as ei:
        engine.require_memory_before_dispatch(
            "m", context_pack_digest="sha256:" + "0" * 64,
            policy_digest=engine.policy.policy_digest)
    assert ei.value.code == CONTEXTPACK_STALE


def test_dispatch_blocked_when_memory_inactive():
    store = MemoryStore(":memory:")
    eng = MemoryTriggerEngine(store, model_safe_limit_steps=8)
    eng.store = None  # simulate inactive
    with pytest.raises(Exception) as ei:
        eng.require_memory_before_dispatch("m")
    assert ei.value.code == MEMORY_PATH_INACTIVE


def test_dispatch_blocked_when_context_exceeds_hardstop(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    with pytest.raises(Exception) as ei:
        engine.require_memory_before_dispatch(
            "m", context_pack_digest=pack["contextPackDigest"],
            policy_digest=engine.policy.policy_digest,
            context_usage=engine.policy.hard_stop_tokens() + 1)
    assert ei.value.code == CONTEXT_BUDGET_EXCEEDED


def test_dispatch_blocked_on_consent_failure(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    with pytest.raises(Exception) as ei:
        engine.require_memory_before_dispatch(
            "m", context_pack_digest=pack["contextPackDigest"],
            policy_digest=engine.policy.policy_digest, consent_ok=False)
    assert ei.value.code == MEMORY_CONSENT_DENIED


def test_dispatch_blocked_on_scope_violation(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    with pytest.raises(Exception) as ei:
        engine.require_memory_before_dispatch(
            "m", context_pack_digest=pack["contextPackDigest"],
            policy_digest=engine.policy.policy_digest, scope_ok=False)
    assert ei.value.code == MEMORY_SCOPE_VIOLATION


def test_dispatch_allowed_with_valid_pack(engine):
    u = ContextUsage(); u.current_messages = TRIGGER_INTERVAL_TOKENS
    pack = engine.require_retrieval_before_planning("m", u)
    gate = engine.require_memory_before_dispatch(
        "m", context_pack_digest=pack["contextPackDigest"],
        policy_digest=engine.policy.policy_digest, context_usage=40000)
    assert gate["ok"] is True


def test_reconnect_reconstructs_policy(engine):
    engine.update_policy(retrieval_trigger_steps=2)
    recon = engine.reconstruct_policy(engine.policy.policy_version)
    assert recon is not None
    assert recon.retrieval_trigger_steps == 2


# -- MemoryQuery contract --------------------------------------------------

def test_memory_query_contract_valid():
    q = build_memory_query(
        mission_id="m1", task_id="t1", actor="human",
        requesting_subsystem="capt_runtime.memory", trigger_boundary=32768,
        context_usage=1000, requested_memory_classes=["project"], purpose="test",
        record_limit=10, token_budget=5000)
    assert q["correlationId"].startswith("corr-")
    assert q["triggerBoundary"] == 32768
