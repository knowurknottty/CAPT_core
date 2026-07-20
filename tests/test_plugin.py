"""Tests for the Hermes plugin public tool surface."""

import pytest

from capt_solo.plugin import CaptSoloPlugin, TOOLS, get_plugin, tool_names


@pytest.fixture
def plugin():
    return get_plugin()


def test_tool_names_stable():
    expected = {
        "capt_store_memory", "capt_search_memory", "capt_get_memory",
        "capt_begin_transaction", "capt_commit_transaction",
        "capt_abort_transaction", "capt_send_message", "capt_health",
        "capt_export_project", "capt_import_project",
        # v0.2 context-intelligence tools
        "capt_build_context", "capt_explain_context",
        "capt_add_memory_relation", "capt_detect_memory_conflicts",
        "capt_review_memory_conflicts", "capt_compress_memory",
        "capt_memory_pipeline_status",
        # v0.3 adaptive lifecycle / session / procedure / prospective / feedback tools
        "capt_session_begin", "capt_session_checkpoint", "capt_session_resume",
        "capt_session_status", "capt_session_consolidate", "capt_session_close",
        "capt_promote_memory", "capt_archive_memory", "capt_pin_memory",
        "capt_explain_memory_lifecycle", "capt_create_procedure", "capt_get_procedure",
        "capt_record_procedure_run", "capt_find_procedures", "capt_add_prospective_memory",
        "capt_list_pending_intents", "capt_resolve_intent",
        "capt_record_retrieval_feedback", "capt_get_restart_context",
    }
    assert expected.issubset(set(tool_names()))
    assert len(TOOLS) == 47


def test_capt_store_memory(plugin):
    res = plugin.capt_store_memory("hello", namespace="p", tags=["t"])
    assert res["ok"] is True
    assert res["memory"]["content"] == "hello"


def test_capt_search_memory(plugin):
    plugin.capt_store_memory("findme keyword", namespace="p")
    res = plugin.capt_search_memory("keyword")
    assert res["ok"] is True
    assert len(res["results"]) >= 1


def test_capt_get_memory(plugin):
    stored = plugin.capt_store_memory("getme")
    mid = stored["memory"]["memory_id"]
    res = plugin.capt_get_memory(mid)
    assert res["ok"] is True
    assert res["memory"]["content"] == "getme"


def test_capt_get_memory_missing(plugin):
    res = plugin.capt_get_memory("missing")
    assert res["ok"] is False
    assert res["error"] == "not_found"


def test_capt_begin_commit(plugin):
    b = plugin.capt_begin_transaction(correlation_id="c", idempotency_key="k")
    assert b["ok"] is True
    c = plugin.capt_commit_transaction(b["tx_id"])
    assert c["ok"] is True
    assert c["receipt"]["status"] == "committed"


def test_capt_abort(plugin):
    b = plugin.capt_begin_transaction()
    a = plugin.capt_abort_transaction(b["tx_id"])
    assert a["ok"] is True
    assert a["receipt"]["status"] == "aborted"


def test_capt_send_message(plugin):
    res = plugin.capt_send_message("topic", {"x": 1}, correlation_id="c")
    assert res["ok"] is True
    assert res["message_id"]


def test_capt_health(plugin):
    res = plugin.capt_health()
    assert res["status"] in ("ok", "degraded")
    assert "memory_integrity" in res


def test_capt_export_project(plugin, tmp_path):
    plugin.capt_store_memory("exportable")
    res = plugin.capt_export_project(str(tmp_path / "exp.json"))
    assert res["ok"] is True
    from pathlib import Path
    assert Path(res["path"]).exists()


def test_capt_import_project_missing_file(plugin):
    res = plugin.capt_import_project("/nonexistent/file.json")
    assert res["ok"] is False
    assert "error" in res


def test_capt_import_project(plugin, tmp_path):
    plugin.capt_store_memory("toexport")
    exp = plugin.capt_export_project(str(tmp_path / "exp.json"))
    res = plugin.capt_import_project(exp["path"], merge=True)
    assert res["ok"] is True
    assert res["imported"] >= 1


def test_capt_commit_unknown_tx(plugin):
    res = plugin.capt_commit_transaction("nope")
    assert res["ok"] is False
    assert "error" in res


def test_capt_abort_unknown_tx(plugin):
    res = plugin.capt_abort_transaction("nope")
    assert res["ok"] is False
    assert "error" in res
