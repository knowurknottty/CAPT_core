"""CAPT-UPG-021 sparse symbol-index tests."""

from pathlib import Path

from capt_runtime.discovery.symbol_index import (
    build_symbol_index,
    select_symbols,
    sparse_selection_metrics,
)


def _candidate(path: Path, cid: str, accepted: bool = True):
    return {
        "candidate_id": cid,
        "path": str(path),
        "resolved_path": str(path.resolve()),
        "kind": "file",
        "accepted": accepted,
    }


def test_index_consumes_only_admitted_files_and_reports_unsupported(tmp_path):
    py_file = tmp_path / "service.py"
    py_file.write_text(
        "class RuntimeService:\n"
        "    def revoke(self):\n"
        "        return True\n\n"
        "def helper():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    js_file = tmp_path / "ui.js"
    js_file.write_text("function render() { return true; }\n", encoding="utf-8")
    rejected = tmp_path / "hidden.py"
    rejected.write_text("def secret():\n    pass\n", encoding="utf-8")

    discovery = {
        "root": str(tmp_path),
        "classification": "source_present",
        "candidates": [
            _candidate(py_file, "py"),
            _candidate(js_file, "js"),
            _candidate(rejected, "rejected", accepted=False),
        ],
    }
    index = build_symbol_index(discovery)
    qualnames = {symbol["qualname"] for symbol in index["symbols"]}

    assert "RuntimeService" in qualnames
    assert "RuntimeService.revoke" in qualnames
    assert "helper" in qualnames
    assert "secret" not in qualnames
    assert index["coverage"]["admittedFileCandidates"] == 2
    assert index["coverage"]["indexedFiles"] == 1
    assert index["coverage"]["unsupportedFiles"] == 1
    assert index["authority"] == "derived_read_only"


def test_selector_exposes_selected_and_omitted_symbols_with_metrics(tmp_path):
    source = tmp_path / "runtime.py"
    source.write_text(
        "def authorize_mutation():\n"
        "    \"\"\"authorize a governed mutation\"\"\"\n"
        "    return True\n\n"
        "def render_widget():\n"
        "    return 'ui'\n\n"
        "def unrelated_math():\n"
        "    return 2 + 2\n",
        encoding="utf-8",
    )
    index = build_symbol_index({
        "root": str(tmp_path),
        "classification": "source_present",
        "candidates": [_candidate(source, "runtime")],
    })
    selection = select_symbols(index, ["authorize", "mutation"])
    selected_names = [item["name"] for item in selection["selected"]]
    assert selected_names == ["authorize_mutation"]
    assert selection["omittedCount"] == 2
    assert selection["sufficiencyClaim"] is False

    relevant = [selection["selected"][0]["symbolId"]]
    metrics = sparse_selection_metrics(index, selection, relevant)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["byteReductionRatio"] > 0.0
    assert metrics["contextSufficiencyProven"] is False


def test_parse_failure_is_visible_not_silently_covered(tmp_path):
    broken = tmp_path / "broken.py"
    broken.write_text("def nope(:\n    pass\n", encoding="utf-8")
    index = build_symbol_index({
        "root": str(tmp_path),
        "classification": "source_present",
        "candidates": [_candidate(broken, "broken")],
    })
    assert index["coverage"]["indexedFiles"] == 0
    assert index["coverage"]["parseOrReadFailures"] == 1
    assert index["failures"][0]["reason"] == "parse_failed"
