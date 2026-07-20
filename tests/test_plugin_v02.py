"""Tests for v0.2 plugin tools (capt_build_context, capt_compress_memory, etc.)."""

import pytest

from capt_solo.plugin import CaptSoloPlugin, tool_names


@pytest.fixture
def plugin(isolated_home):
    return CaptSoloPlugin()


def test_capt_build_context(plugin):
    plugin.capt_store_memory("Use SQLite for storage. Portable.", namespace="proj",
                           tags=["db"], metadata={"kind": "decision"})
    res = plugin.capt_build_context(query="storage", namespace="proj", max_items=5)
    assert res["ok"] is True
    assert "items" in res["context"]
    assert res["context"]["trace_id"]


def test_capt_explain_context(plugin):
    plugin.capt_store_memory("Use SQLite. Portable.", namespace="proj",
                           metadata={"kind": "decision"})
    res = plugin.capt_explain_context(query="sqlite", namespace="proj")
    assert res["ok"] is True
    assert "explanation" in res


def test_capt_add_memory_relation(plugin):
    a = plugin.capt_store_memory("a")["memory"]["memory_id"]
    b = plugin.capt_store_memory("b")["memory"]["memory_id"]
    res = plugin.capt_add_memory_relation(a, b, "supports")
    assert res["ok"] is True
    assert res["edge_id"]


def test_capt_add_memory_relation_bad_type(plugin):
    a = plugin.capt_store_memory("a")["memory"]["memory_id"]
    b = plugin.capt_store_memory("b")["memory"]["memory_id"]
    res = plugin.capt_add_memory_relation(a, b, "not_a_type")
    assert res["ok"] is False


def test_capt_detect_memory_conflicts(plugin):
    a = plugin.capt_store_memory("SQLite is right.")["memory"]["memory_id"]
    plugin.capt_add_memory_relation(a, a, "contradicts")  # self-edge for test
    res = plugin.capt_detect_memory_conflicts(a)
    assert res["ok"] is True


def test_capt_review_memory_conflicts(plugin):
    res = plugin.capt_review_memory_conflicts()
    assert res["ok"] is True
    assert "conflicts" in res


def test_capt_compress_memory(plugin):
    mid = plugin.capt_store_memory(
        "Decision: use SQLite. It is portable and offline.",
        metadata={"kind": "decision"})["memory"]["memory_id"]
    res = plugin.capt_compress_memory(mid, format="text")
    assert res["ok"] is True
    assert "rendered" in res
    assert "packet" in res


def test_capt_compress_memory_missing(plugin):
    res = plugin.capt_compress_memory("nope")
    assert res["ok"] is False
    assert res["error"] == "not_found"


def test_capt_memory_pipeline_status(plugin):
    plugin.capt_store_memory("x", namespace="proj")
    res = plugin.capt_memory_pipeline_status()
    assert res["ok"] is True
    assert "graph_nodes" in res
    assert "csg_weights" in res


def test_tool_names_include_v02():
    names = tool_names()
    for t in ("capt_build_context", "capt_explain_context",
              "capt_add_memory_relation", "capt_detect_memory_conflicts",
              "capt_review_memory_conflicts", "capt_compress_memory",
              "capt_memory_pipeline_status"):
        assert t in names
