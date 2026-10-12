"""Tests for scripts/upg_queue.py (upgrade-campaign work queue)."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "upg_queue.py"
BACKLOG = ROOT / "docs" / "upgrade-campaign" / "capt_upg_025_backlog.json"

_spec = importlib.util.spec_from_file_location("upg_queue", SCRIPT)
assert _spec and _spec.loader
uq = importlib.util.module_from_spec(_spec)
sys.modules["upg_queue"] = uq
_spec.loader.exec_module(uq)


def _item(iid: str, *, deps: list[str] | None = None, files: list[str] | None = None,
          status: str = "open", tier: str = "P1") -> dict[str, Any]:
    return {
        "id": iid, "title": iid, "tier": tier, "kind": "upgrade", "provenance": "P",
        "summary": "s", "files": files or [], "creates": [], "depends_on": deps or [],
        "risk": "low", "needs_adr": False, "owner_role": "implementer",
        "acceptance": ["a"], "verification": ["v"], "status": status,
    }


def _write(tmp_path: Path, items: list[dict[str, Any]]) -> Path:
    path = tmp_path / "backlog.json"
    path.write_text(json.dumps({"items": items}), encoding="utf-8")
    return path


def test_shipped_backlog_is_valid() -> None:
    data = uq.load(BACKLOG)
    assert uq.validate(data, ROOT) == []


def test_shipped_backlog_initial_ready_set_is_p0_first() -> None:
    rows = uq.ready(uq.load(BACKLOG))
    assert rows, "a fresh campaign must have ready work"
    assert rows[0]["tier"] == "P0"
    ready_ids = {r["id"] for r in rows}
    assert "CAPT-UPG-041" not in ready_ids  # depends on the ADR (040)


def test_cycle_is_detected(tmp_path: Path) -> None:
    data = {"items": [_item("CAPT-UPG-900", deps=["CAPT-UPG-901"]),
                      _item("CAPT-UPG-901", deps=["CAPT-UPG-900"])]}
    problems = uq.validate(data, tmp_path)
    assert any("cycle" in p for p in problems)


def test_unknown_dependency_and_missing_path(tmp_path: Path) -> None:
    data = {"items": [_item("CAPT-UPG-900", deps=["CAPT-UPG-999"], files=["nope.py"])]}
    problems = uq.validate(data, tmp_path)
    assert any("unknown dependency" in p for p in problems)
    assert any("does not exist" in p for p in problems)


def test_ready_respects_dependencies_and_file_conflicts(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("")
    (tmp_path / "pkg").mkdir()
    items = [
        _item("CAPT-UPG-900", files=["a.py"], status="claimed"),
        _item("CAPT-UPG-901", files=["a.py"]),
        _item("CAPT-UPG-902", deps=["CAPT-UPG-900"]),
        _item("CAPT-UPG-903", files=["pkg"], tier="P0"),
    ]
    items[0]["claimedBy"] = "vesper"
    rows = uq.ready({"items": items})
    ids = [r["id"] for r in rows]
    assert "CAPT-UPG-902" not in ids
    assert ids[0] == "CAPT-UPG-903"
    conflicted = next(r for r in rows if r["id"] == "CAPT-UPG-901")
    assert conflicted["conflictsWith"] == ["CAPT-UPG-900"]


def test_claim_refuses_overlap_and_unmet_deps(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("")
    data = {"items": [_item("CAPT-UPG-900", files=["a.py"]), _item("CAPT-UPG-901", files=["a.py"]),
                      _item("CAPT-UPG-902", deps=["CAPT-UPG-900"])]}
    uq.transition(data, "CAPT-UPG-900", "claimed", agent="vesper")
    with pytest.raises(uq.QueueError, match="overlaps"):
        uq.transition(data, "CAPT-UPG-901", "claimed", agent="axiom")
    with pytest.raises(uq.QueueError, match="unmet"):
        uq.transition(data, "CAPT-UPG-902", "claimed", agent="axiom")


def test_full_lifecycle_and_separation_of_duties() -> None:
    data = {"items": [_item("CAPT-UPG-900")]}
    uq.transition(data, "CAPT-UPG-900", "claimed", agent="vesper")
    uq.transition(data, "CAPT-UPG-900", "red", agent="vesper", note="failing test committed")
    with pytest.raises(uq.QueueError, match="requires --evidence"):
        uq.transition(data, "CAPT-UPG-900", "green", agent="vesper")
    uq.transition(data, "CAPT-UPG-900", "green", agent="vesper", evidence="pytest log sha256:ab")
    with pytest.raises(uq.QueueError, match="only the claimant"):
        uq.transition(data, "CAPT-UPG-900", "in_review", agent="axiom", evidence="pr")
    uq.transition(data, "CAPT-UPG-900", "in_review", agent="vesper", evidence="PR #1")
    with pytest.raises(uq.QueueError, match="separation of duties"):
        uq.transition(data, "CAPT-UPG-900", "merged", agent="vesper", evidence="sha")
    item = uq.transition(data, "CAPT-UPG-900", "merged", agent="kirk", evidence="merge sha 1234")
    assert item["status"] == "merged"
    assert [h["to"] for h in item["history"]] == ["claimed", "red", "green", "in_review", "merged"]
    with pytest.raises(uq.QueueError, match="illegal"):
        uq.transition(data, "CAPT-UPG-900", "open", agent="kirk")


def test_expect_status_rejects_stale_view() -> None:
    data = {"items": [_item("CAPT-UPG-900")]}
    with pytest.raises(uq.QueueError, match="stale"):
        uq.transition(data, "CAPT-UPG-900", "deferred", agent="kirk", expect="claimed")


def test_concurrent_cli_claims_only_one_wins(tmp_path: Path) -> None:
    path = _write(tmp_path, [_item("CAPT-UPG-900")])
    procs = [
        subprocess.Popen(
            [sys.executable, "-I", str(SCRIPT), "--backlog", str(path), "--repo-root", str(tmp_path),
             "claim", "CAPT-UPG-900", "--agent", f"agent-{n}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for n in range(6)
    ]
    codes = [p.wait(timeout=30) for p in procs]
    assert sorted(codes) == [0, 1, 1, 1, 1, 1]
    final = json.loads(path.read_text(encoding="utf-8"))["items"][0]
    assert final["status"] == "claimed" and len(final["history"]) == 1


def test_cli_refuses_to_mutate_invalid_backlog(tmp_path: Path) -> None:
    bad = _item("CAPT-UPG-900", files=["missing.py"])
    path = _write(tmp_path, [bad])
    before = path.read_text(encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--backlog", str(path), "--repo-root", str(tmp_path),
         "claim", "CAPT-UPG-900", "--agent", "vesper"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 1 and "invalid" in result.stderr
    assert path.read_text(encoding="utf-8") == before


def test_shipped_backlog_untouched_by_tests() -> None:
    data = uq.load(BACKLOG)
    snapshot = copy.deepcopy(data)
    uq.ready(data)
    assert data == snapshot
    assert all(i["status"] == "open" for i in data["items"])
