"""Integration tests for the full v0.2 flow: pipeline -> CSG -> context -> conflict
-> merge -> export/import -> restart recovery. Also targets remaining engine,
context, pipeline, and plugin branches."""

import json

import pytest

from capt_solo.core.config import reset_paths_for_test
from capt_solo.khsb.bus import KHSB
from capt_solo.memory.context import build_context
from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.pipeline import MemoryPipeline
from capt_solo.plugin import CaptSoloPlugin


@pytest.fixture
def plugin(isolated_home):
    return CaptSoloPlugin()


@pytest.fixture
def eng(isolated_home):
    e = MemoryEngine()
    yield e
    e.close()


# ----- engine: merge / alias / supersede / conflict -----
def test_engine_merge_and_alias(eng):
    a = eng.store("source memory").memory_id
    b = eng.store("target memory").memory_id
    assert eng.merge(a, b) is True
    assert eng.get(a).metadata["status"] == "superseded"
    assert eng.resolve_alias(a) == b


def test_engine_merge_missing(eng):
    b = eng.store("target").memory_id
    assert eng.merge("missing", b) is False


def test_engine_mark_superseded_with_by(eng):
    a = eng.store("old").memory_id
    b = eng.store("new").memory_id
    assert eng.mark_superseded(a, by=b)
    assert eng.get(a).metadata["superseded_by"] == b


def test_engine_mark_superseded_missing(eng):
    assert eng.mark_superseded("nope") is False


def test_engine_record_resolve_conflict_full(eng):
    a = eng.store("a").memory_id
    b = eng.store("b").memory_id
    cid = eng.record_conflict(a, b, reason="test conflict")
    assert cid
    assert eng.detect_conflicts(a)
    assert eng.resolve_conflict(cid) is True
    assert not eng.detect_conflicts(a)


def test_engine_list_conflicts_all(eng):
    a = eng.store("a").memory_id
    b = eng.store("b").memory_id
    eng.record_conflict(a, b)
    all_c = eng.list_conflicts(unresolved_only=False)
    assert len(all_c) == 1


def test_engine_add_remove_relation(eng):
    a = eng.store("a").memory_id
    b = eng.store("b").memory_id
    eid = eng.add_relation(a, b, "supports")
    assert eid
    assert len(eng.get_neighbors(a)) == 1
    assert eng.remove_relation(eid) is True
    assert eng.get_neighbors(a) == []


def test_engine_find_path_none(eng):
    a = eng.store("a").memory_id
    b = eng.store("b").memory_id
    eng.add_relation(a, b, "supports")
    assert eng.find_path(a, "zzz") is None


# ----- context builder branches -----
def test_build_context_with_conflicts_and_exclusions(eng):
    a = eng.store("Use SQLite. Portable.", namespace="proj",
                 metadata={"kind": "decision"}).memory_id
    b = eng.store("Do NOT use SQLite.", namespace="proj",
                 metadata={"kind": "decision"}).memory_id
    eng.record_conflict(a, b, reason="db choice")
    res = build_context(eng, query="sqlite", namespace="proj", max_items=5,
                        include_conflicts=True)
    assert len(res.items) >= 1
    assert res.conflicts  # conflict surfaced


def test_build_context_char_budget_excludes(eng):
    for i in range(4):
        eng.store(f"memory item {i} " + "word " * 40, namespace="proj")
    res = build_context(eng, query="memory", namespace="proj",
                        max_items=10, char_budget=100)
    assert res.estimated_compressed_chars <= 100 or len(res.exclusions) > 0


def test_build_context_token_budget(eng):
    for i in range(4):
        eng.store(f"token test {i} " + "data " * 40, namespace="proj")
    res = build_context(eng, query="token", namespace="proj",
                        max_items=10, token_budget=20)
    assert len(res.exclusions) > 0 or res.estimated_compressed_chars // 4 <= 20


def test_build_context_include_superseded(eng):
    a = eng.store("old approach", namespace="proj").memory_id
    b = eng.store("new approach", namespace="proj").memory_id
    eng.mark_superseded(a, by=b)
    res = build_context(eng, query="approach", namespace="proj", max_items=5,
                        include_superseded=True)
    ids = [i.memory_id for i in res.items]
    assert a in ids  # superseded included when opted in


# ----- pipeline: transition + explain -----
def test_pipeline_transition_and_explain(eng):
    bus = KHSB()
    pipe = MemoryPipeline(eng, bus)
    r = pipe.ingest("Hypothesis: caching will help.", namespace="proj",
                    kind="hypothesis")
    mid = r.value["memory"]["memory_id"]
    tr = pipe.transition_trust(mid, "observed_fact")
    assert tr.ok
    assert eng.get(mid).metadata["trust_state"] == "observed_fact"


def test_pipeline_explain_after_build(eng):
    bus = KHSB()
    pipe = MemoryPipeline(eng, bus)
    pipe.ingest("Use SQLite. Portable.", namespace="proj", kind="decision")
    from capt_solo.memory.csg import CSG
    res = build_context(eng, query="sqlite", namespace="proj", max_items=3)
    csg = CSG(eng._conn)
    expl = csg.explain_selection([
        {"memory_id": i.memory_id, "decision": "selected", "score": i.score,
         "signals": {}, "reason": "x"} for i in res.items])
    assert "selected" in expl


# ----- plugin error paths -----
def test_plugin_capt_add_relation_missing_memory(plugin):
    # relation to nonexistent memory auto-creates nodes; edge is created
    res = plugin.capt_add_memory_relation("nope_a", "nope_b", "supports")
    assert res["ok"] is True
    assert res["edge_id"]


def test_plugin_capt_build_context_empty(plugin):
    res = plugin.capt_build_context(query="nothing", namespace="proj")
    assert res["ok"] is True
    assert res["context"]["items"] == []


def test_plugin_capt_explain_empty(plugin):
    res = plugin.capt_explain_context(query="x", namespace="proj")
    assert res["ok"] is True


def test_plugin_capt_detect_conflicts_missing(plugin):
    res = plugin.capt_detect_memory_conflicts("nope")
    assert res["ok"] is True
    assert res["conflicts"] == []


def test_plugin_capt_review_conflicts_empty(plugin):
    res = plugin.capt_review_memory_conflicts()
    assert res["ok"] is True
    assert res["conflicts"] == []


# ----- full restart recovery -----
def test_full_restart_recovery(isolated_home, tmp_path):
    # session 1
    e1 = MemoryEngine()
    pipe = MemoryPipeline(e1, KHSB())
    pipe.ingest("Decision: use SQLite for v0.2 storage.", namespace="proj",
                    kind="decision", provenance="user")
    e1.close()
    # simulate restart: new engine instance, same home
    e2 = MemoryEngine()
    try:
        # data persists; CSG nodes present
        assert e2.list(namespace="proj")
        nodes = e2._conn.execute(
            "SELECT COUNT(*) AS c FROM memory_nodes").fetchone()["c"]
        assert nodes >= 1
        # build context works after restart
        res = build_context(e2, query="storage", namespace="proj", max_items=5)
        assert res.items
    finally:
        e2.close()


# ----- export/import preserves graph -----
def test_export_import_preserves_graph(isolated_home, tmp_path):
    e1 = MemoryEngine()
    pipe = MemoryPipeline(e1, KHSB())
    r1 = pipe.ingest("Use SQLite.", namespace="proj", kind="decision")
    r2 = pipe.ingest("Do NOT use SQLite.", namespace="proj", kind="decision")
    e1.record_conflict(r1.value["memory"]["memory_id"],
                        r2.value["memory"]["memory_id"], reason="db")
    exp = e1.export_json(tmp_path / "g.json")
    e1.close()

    e2 = MemoryEngine(tmp_path / "imported.db")
    try:
        n = e2.import_json(exp, merge=True)
        assert n >= 2
        # conflict preserved
        assert e2.list_conflicts(unresolved_only=True)
        # nodes seeded
        assert e2._conn.execute(
            "SELECT COUNT(*) AS c FROM memory_nodes").fetchone()["c"] >= 2
    finally:
        e2.close()
