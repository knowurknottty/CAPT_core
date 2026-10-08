from pathlib import Path

import pytest

from capt_runtime.workaround_inventory import category, inspect_script, inventory


def test_important_workaround_routes():
    assert category("run-compact-council.py") == "council_launch"
    assert category("generate_mission_triage_20261008.py") == "mission_triage"
    assert category("live_pi_probe.py") == "provider_health"
    assert category("capt-hardening-r2-failover.py") == "runtime_recovery"
    assert category("inversion-commander-scaffold.py") == "other"


def test_inventory_never_executes_inspected_files(tmp_path):
    marker = tmp_path / "SHOULD_NOT_EXIST"
    script = tmp_path / "bot_ui_patch.py"
    script.write_text("from pathlib import Path\nPath(%r).write_text('side effect')\n" % str(marker))
    rows = inventory([tmp_path])
    assert rows["recordCount"] == 1
    assert rows["scripts"][0]["category"] == "desktop_acceptance"
    assert rows["scripts"][0]["hasTopLevelStatements"]
    assert not marker.exists()


def test_symlinks_skipped_and_overlap_deduplicated(tmp_path):
    child = tmp_path / "probe.py"
    child.write_text("x=1\n")
    link = tmp_path / "alias.py"
    link.symlink_to(child)
    report = inventory([tmp_path, tmp_path])
    assert report["recordCount"] == 1
    assert report["scripts"][0]["path"] == str(child)
    assert report["notProofOfMissingFeatures"]


def test_no_execution_even_for_invalid_source(tmp_path):
    bad = tmp_path / "needs_fix.py"
    bad.write_text("def func(:\n")
    result = inspect_script(bad)
    assert result["parseStatus"] == "invalid"
    assert result["errorType"] == "SyntaxError"


def test_invalid_scope_fails_closed(tmp_path):
    (tmp_path / "a.py").write_text("pass\n")
    with pytest.raises(ValueError, match="max_files"):
        inventory([tmp_path], max_files=0)
    (tmp_path / "b.py").write_text("pass\\n")
    with pytest.raises(ValueError, match="exceeds max_files"):
        inventory([tmp_path], max_files=1)
