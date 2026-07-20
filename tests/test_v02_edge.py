"""Supplementary tests targeting edge branches for v0.2 coverage."""

import pytest

from capt_solo.core.errors import MemoryError_
from capt_solo.khsb.bus import KHSB
from capt_solo.memory.antitoken import extract, render, validate
from capt_solo.memory.csg import CSG
from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.pipeline import MemoryPipeline
from capt_solo.memory.trust import apply_transition, can_transition, trust_from_kind
from capt_solo.memory.models import MemoryKind, TrustState


@pytest.fixture
def eng(isolated_home):
    e = MemoryEngine()
    yield e
    e.close()


# ----- antitoken edge branches -----
def test_antitoken_security_and_destructive_flags():
    mem = {"memory_id": "m", "content": "DELETE the key file. SECRET leaked.",
           "namespace": "ns", "tags": [], "provenance": "user",
           "confidence": 1.0, "metadata": {"kind": "failure"}, "status": "active"}
    pkt = extract(mem)
    assert pkt.security_warning is True
    assert pkt.destructive_warning is True
    ok, warns = validate(pkt, mem)
    assert ok, warns


def test_antitoken_uncertainty_flag():
    mem = {"memory_id": "m", "content": "Maybe the version 2.3 is unstable, approximately.",
           "namespace": "ns", "tags": [], "provenance": "user",
           "confidence": 0.4, "metadata": {"kind": "hypothesis"}, "status": "active"}
    pkt = extract(mem)
    assert pkt.uncertainty is True
    ok, warns = validate(pkt, mem)
    assert ok, warns


def test_antitoken_render_json_and_model_neutral():
    mem = {"memory_id": "m", "content": "Use Postgres. It scales.",
           "namespace": "ns", "tags": [], "provenance": "user",
           "confidence": 1.0, "metadata": {"kind": "decision"}, "status": "active"}
    pkt = extract(mem)
    assert '"memory_id"' in render(pkt, "json")
    mn = render(pkt, "model_neutral")
    assert mn.startswith("ANTITOKEN")
    assert "kind=decision" in mn


def test_antitoken_path_preservation():
    mem = {"memory_id": "m", "content": "Config at /etc/app/config.yaml must exist.",
           "namespace": "ns", "tags": [], "provenance": "user",
           "confidence": 1.0, "metadata": {}, "status": "active"}
    pkt = extract(mem)
    ok, warns = validate(pkt, mem)
    assert ok, warns


# ----- csg edge branches -----
def test_csg_find_path_max_depth_exceeded(eng):
    csg = CSG(eng._conn)
    # chain a->b->c->d->e (depth 4) with max_depth=2
    ids = [f"n{i}" for i in range(5)]
    for a, b in zip(ids, ids[1:]):
        csg.add_edge(a, b, "supports")
    assert csg.find_path("n0", "n4", max_depth=2) is None
    assert csg.find_path("n0", "n4", max_depth=6) is not None


def test_csg_explain_selection_empty(eng):
    csg = CSG(eng._conn)
    out = csg.explain_selection([])
    assert isinstance(out, str)


def test_csg_select_context_with_intent_and_tx(eng):
    csg = CSG(eng._conn)
    candidates = [
        {"memory_id": "m1", "content": "deploy the service", "namespace": "ns",
         "tags": ["t"], "confidence": 1.0, "provenance": "user",
         "updated_at": 1e18, "status": "active"},
    ]
    sel, exp = csg.select_context(
        candidates, query="deploy", task_intent="deploy service",
        tx_linkage={"m1": "tx1"})
    assert sel[0]["memory_id"] == "m1"
    assert exp[0]["signals"]["transaction_linkage"] == 1.0


def test_csg_select_context_budget_excludes(eng):
    csg = CSG(eng._conn)
    candidates = [
        {"memory_id": f"m{i}", "content": f"word {i} " * 30, "namespace": "ns",
         "tags": [], "confidence": 1.0, "provenance": "user",
         "updated_at": 1e18, "status": "active"} for i in range(5)
    ]
    sel, exp = csg.select_context(candidates, max_items=2)
    # only 2 selected due to budget
    assert len(sel) == 2


# ----- trust edge branches -----
def test_trust_transition_self_and_rejected():
    assert can_transition(TrustState.REJECTED, TrustState.USER_FACT)
    assert can_transition(TrustState.REJECTED, TrustState.OBSERVED_FACT)
    # superseded -> only rejected allowed
    assert not can_transition(TrustState.SUPERSEDED, TrustState.USER_FACT)
    with pytest.raises(ValueError):
        apply_transition(TrustState.SUPERSEDED, TrustState.USER_FACT)


def test_trust_from_kind_default():
    assert trust_from_kind(MemoryKind.FACT) == TrustState.OBSERVED_FACT
    assert trust_from_kind(MemoryKind.ARTIFACT_REF) == TrustState.TOOL_RESULT


# ----- pipeline rollback on failure -----
def test_pipeline_rollback_on_persistence_error(eng, monkeypatch):
    pipe = MemoryPipeline(eng, KHSB())
    # force the raw store to raise to simulate a failure mid-transaction
    def boom(*a, **k):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(eng, "_store_raw", boom)
    r = pipe.ingest("content that will fail", namespace="ns")
    assert not r.ok
    assert any("persistence failed" in x for x in r.rejections)
    # nothing persisted
    assert eng.list(namespace="ns") == []


def test_pipeline_emit_events_disabled(eng):
    pipe = MemoryPipeline(eng, KHSB(), )
    r = pipe.ingest("no events test", namespace="ns", emit_events=False)
    assert r.ok
