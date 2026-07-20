"""Tests for v0.2 CSG graph, AntiToken, context builder, pipeline, engine v0.2."""

import pytest

from capt_solo.core.errors import MemoryError_
from capt_solo.khsb.bus import KHSB
from capt_solo.memory.antitoken import estimate_reduction, extract, render, validate
from capt_solo.memory.csg import CSG, DEFAULT_WEIGHTS
from capt_solo.memory.context import build_context
from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.pipeline import MemoryPipeline


@pytest.fixture
def eng(isolated_home):
    e = MemoryEngine()
    yield e
    e.close()


@pytest.fixture
def bus():
    b = KHSB()
    yield b
    b.reset()


# ----- CSG -----
def test_csg_add_edge_valid(eng):
    csg = CSG(eng._conn)
    eid = csg.add_edge("a", "b", "supports")
    assert eid
    assert len(csg.get_neighbors("a")) == 1


def test_csg_add_edge_invalid_type(eng):
    csg = CSG(eng._conn)
    with pytest.raises(MemoryError_):
        csg.add_edge("a", "b", "not_a_type")


def test_csg_remove_edge(eng):
    csg = CSG(eng._conn)
    eid = csg.add_edge("a", "b", "supports")
    assert csg.remove_edge(eid) is True
    assert csg.get_neighbors("a") == []


def test_csg_find_path(eng):
    csg = CSG(eng._conn)
    csg.add_edge("a", "b", "supports")
    csg.add_edge("b", "c", "supports")
    path = csg.find_path("a", "c")
    assert path == ["a", "b", "c"]


def test_csg_find_path_none(eng):
    csg = CSG(eng._conn)
    assert csg.find_path("a", "z") is None


def test_csg_detect_conflicts(eng):
    csg = CSG(eng._conn)
    csg.add_edge("a", "b", "contradicts")
    cf = csg.detect_conflicts("a")
    assert len(cf) == 1
    assert cf[0]["with"] == "b"


def test_csg_set_weights(eng):
    csg = CSG(eng._conn)
    csg.set_weights({"recency": 0.1})
    assert csg.get_weights()["recency"] == 0.1
    # unknown key ignored
    csg.set_weights({"nonexistent": 5.0})
    assert "nonexistent" not in csg.get_weights()


def test_csg_select_context_deterministic(eng):
    csg = CSG(eng._conn)
    candidates = [
        {"memory_id": "m1", "content": "alpha beta", "namespace": "ns",
         "tags": ["t"], "confidence": 1.0, "provenance": "user", "updated_at": 1e18,
         "status": "active"},
        {"memory_id": "m2", "content": "gamma", "namespace": "other",
         "tags": [], "confidence": 0.5, "provenance": "unknown", "updated_at": 1.0,
         "status": "active"},
    ]
    sel1, exp1 = csg.select_context(candidates, query="alpha", namespace="ns", max_items=10)
    sel2, exp2 = csg.select_context(candidates, query="alpha", namespace="ns", max_items=10)
    assert [s["memory_id"] for s in sel1] == [s["memory_id"] for s in sel2]
    assert sel1[0]["memory_id"] == "m1"  # namespace + lexical match wins


def test_csg_select_explanation(eng):
    csg = CSG(eng._conn)
    exp = [{"memory_id": "m1", "decision": "selected", "score": 0.5,
            "signals": {}, "reason": "x"}]
    out = csg.explain_selection(exp)
    assert "m1" in out


def test_csg_superseded_penalty(eng):
    csg = CSG(eng._conn)
    candidates = [
        {"memory_id": "m1", "content": "x", "namespace": "ns", "tags": [],
         "confidence": 1.0, "provenance": "user", "updated_at": 1e18, "status": "superseded"},
    ]
    sel, exp = csg.select_context(candidates, include_superseded=False)
    assert sel == []  # penalized below zero, excluded


# ----- AntiToken -----
def test_antitoken_extract_preserves_negation():
    mem = {"memory_id": "m1", "content": "We must NOT use Docker. It breaks portability.",
           "namespace": "ns", "tags": [], "provenance": "user", "confidence": 1.0,
           "metadata": {"kind": "constraint"}, "status": "active"}
    pkt = extract(mem)
    assert pkt.negation is True
    ok, warns = validate(pkt, mem)
    assert ok, warns


def test_antitoken_extract_preserves_numeric_and_version():
    mem = {"memory_id": "m1", "content": "Use version 2.3.1 with threshold 0.85 for v0.1.",
           "namespace": "ns", "tags": [], "provenance": "user", "confidence": 1.0,
           "metadata": {}, "status": "active"}
    pkt = extract(mem)
    ok, warns = validate(pkt, mem)
    assert ok, warns


def test_antitoken_fidelity_fallback_on_truncation():
    # craft a source where key numeric is only in later sentence; ensure validate
    # flags if dropped. We simulate by checking validate catches missing token.
    mem = {"memory_id": "m1", "content": "Decision made. The value 42 is critical.",
           "namespace": "ns", "tags": [], "provenance": "user", "confidence": 1.0,
           "metadata": {}, "status": "active"}
    pkt = extract(mem)
    # assertion is first sentence only; '42' is in second sentence -> not preserved
    ok, warns = validate(pkt, mem)
    assert not ok
    assert any("numeric" in w for w in warns)


def test_antitoken_render_text_and_json():
    mem = {"memory_id": "m1", "content": "Use SQLite. It is portable.",
           "namespace": "ns", "tags": [], "provenance": "user", "confidence": 1.0,
           "metadata": {"kind": "decision"}, "status": "active"}
    pkt = extract(mem)
    assert "SQLite" in render(pkt, "text")
    assert "SQLite" in render(pkt, "json")
    assert "ANTITOKEN" in render(pkt, "model_neutral")


def test_antitoken_estimate_reduction():
    mem = {"memory_id": "m1", "content": "x" * 400, "namespace": "ns", "tags": [],
           "provenance": "user", "confidence": 1.0, "metadata": {}, "status": "active"}
    pkt = extract(mem)
    est = estimate_reduction(mem["content"], pkt)
    assert est["reduction_ratio"] > 0
    assert "tokenizer" in est["token_estimate_note"]


# ----- pipeline -----
def test_pipeline_ingest_basic(eng, bus):
    pipe = MemoryPipeline(eng, bus)
    r = pipe.ingest("Store this fact.", namespace="ns", kind="fact", provenance="user")
    assert r.ok, r.rejections
    assert r.value["memory"]["memory_id"]


def test_pipeline_rejects_empty(eng, bus):
    pipe = MemoryPipeline(eng, bus)
    r = pipe.ingest("   ")
    assert not r.ok


def test_pipeline_rejects_secret(eng, bus):
    pipe = MemoryPipeline(eng, bus)
    r = pipe.ingest("password=" + ("x" * 12))
    assert not r.ok
    assert any("password" in x.lower() for x in r.rejections)


def test_pipeline_rejects_exact_duplicate(eng, bus):
    pipe = MemoryPipeline(eng, bus)
    pipe.ingest("identical content here", namespace="ns")
    r2 = pipe.ingest("identical content here", namespace="ns")
    assert not r2.ok
    assert any("duplicate" in x.lower() for x in r2.rejections)


def test_pipeline_detects_conflict(eng, bus):
    pipe = MemoryPipeline(eng, bus)
    pipe.ingest("SQLite is correct.", namespace="ns", kind="decision")
    r = pipe.ingest("SQLite is NOT correct.", namespace="ns", kind="decision")
    assert r.ok
    assert len(r.value["conflicts"]) > 0


def test_pipeline_trust_transition(eng, bus):
    pipe = MemoryPipeline(eng, bus)
    r = pipe.ingest("Hypothesis: X will work.", namespace="ns", kind="hypothesis")
    mid = r.value["memory"]["memory_id"]
    tr = pipe.transition_trust(mid, "observed_fact")
    assert tr.ok
    assert eng.get(mid).metadata["trust_state"] == "observed_fact"


def test_pipeline_trust_transition_invalid(eng, bus):
    pipe = MemoryPipeline(eng, bus)
    r = pipe.ingest("Fact.", namespace="ns", kind="fact")
    mid = r.value["memory"]["memory_id"]
    tr = pipe.transition_trust(mid, "verified_result")  # user_fact->verified allowed actually
    # user_fact -> verified_result IS allowed; use a disallowed one
    tr2 = pipe.transition_trust(mid, "inference")  # user_fact -> inference not allowed
    assert not tr2.ok


def test_pipeline_emits_khsb_events(eng, bus):
    received = []
    bus.subscribe("memory.ingest.completed", lambda m: received.append(m.payload))
    pipe = MemoryPipeline(eng, bus)
    pipe.ingest("event test", namespace="ns")
    assert any("memory_id" in p for p in received)


# ----- engine v0.2 APIs -----
def test_engine_find_duplicates(eng):
    eng.store("dup content", namespace="ns")
    matches = eng.find_duplicates("dup content", namespace="ns")
    assert any(m["kind"] == "exact" for m in matches)


def test_engine_add_relation_and_neighbors(eng):
    a = eng.store("a").memory_id
    b = eng.store("b").memory_id
    eid = eng.add_relation(a, b, "supports")
    assert eid
    assert len(eng.get_neighbors(a)) == 1


def test_engine_record_resolve_conflict(eng):
    a = eng.store("a").memory_id
    b = eng.store("b").memory_id
    cid = eng.record_conflict(a, b, reason="test")
    assert eng.detect_conflicts(a)
    assert eng.resolve_conflict(cid) is True
    assert not eng.detect_conflicts(a)


def test_engine_mark_superseded(eng):
    a = eng.store("old").memory_id
    b = eng.store("new").memory_id
    assert eng.mark_superseded(a, by=b)
    assert eng.get(a).metadata["status"] == "superseded"


def test_engine_merge(eng):
    a = eng.store("source").memory_id
    b = eng.store("target").memory_id
    assert eng.merge(a, b)
    assert eng.get(a).metadata["status"] == "superseded"
    assert eng.resolve_alias(a) == b


def test_engine_find_path(eng):
    a = eng.store("a").memory_id
    b = eng.store("b").memory_id
    c = eng.store("c").memory_id
    eng.add_relation(a, b, "supports")
    eng.add_relation(b, c, "supports")
    assert eng.find_path(a, c) == [a, b, c]


# ----- context builder -----
def test_build_context_basic(eng):
    eng.store("Use SQLite for storage. It is portable.", namespace="proj",
              tags=["db"], metadata={"kind": "decision"})
    eng.store("Unrelated astronomy fact.", namespace="proj")
    res = build_context(eng, query="storage database", namespace="proj", max_items=5)
    assert len(res.items) >= 1
    assert res.trace_id
    assert "ANTITOKEN" in res.rendered


def test_build_context_budget_enforcement(eng):
    for i in range(5):
        eng.store(f"memory number {i} " + "word " * 50, namespace="proj")
    res = build_context(eng, query="memory", namespace="proj",
                        max_items=5, char_budget=200)
    total = sum(len(i.antitoken.assertion) for i in res.items if i.antitoken)
    assert total <= 200 or len(res.exclusions) > 0


def test_build_context_explains_all_selected(eng):
    eng.store("Use SQLite. Portable.", namespace="proj", metadata={"kind": "decision"})
    res = build_context(eng, query="sqlite", namespace="proj", max_items=3)
    # every selected item has a reason
    assert all(i.reason for i in res.items)
