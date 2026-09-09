import json
import stat

import pytest

from desktop.operator_control import OperatorControlStale, OperatorControlStore


def _defaults(tmp_path):
    return {
        "provider": "ollama",
        "model": "qwen3.5-defiant-fable:latest",
        "targetRoot": str(tmp_path),
        "promptIntelligence": "AUTO",
    }


def _store(tmp_path):
    return OperatorControlStore(tmp_path / "operator-control.json", _defaults(tmp_path))


def test_operator_control_persists_0600_and_recovers_after_restart(tmp_path):
    store = _store(tmp_path)
    snap = store.set_configuration(
        expected_revision=0, prompt_intelligence="OFF"
    )
    path = tmp_path / "operator-control.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["revision"] == 1
    recovered = _store(tmp_path).snapshot()
    assert recovered == snap
    assert recovered["promptIntelligence"] == "OFF"

def test_operator_control_rejects_stale_writer_without_mutation(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    store = _store(tmp_path)
    winning = store.set_configuration(
        expected_revision=0, target_root=str(child)
    )
    with pytest.raises(OperatorControlStale) as exc:
        store.set_configuration(expected_revision=0, provider="openrouter")
    assert exc.value.current_snapshot == winning
    assert store.snapshot() == winning


def test_prechat_configuration_survives_new_chat(tmp_path):
    child = tmp_path / "child"
    child.mkdir()
    store = _store(tmp_path)
    configured = store.set_configuration(
        expected_revision=0,
        target_root=str(child),
        prompt_intelligence="OFF",
    )
    chat = store.new_chat(expected_revision=configured["revision"])
    assert chat["activeSessionId"].startswith("opchat-")
    assert chat["targetRoot"] == str(child)
    assert chat["promptIntelligence"] == "OFF"
    session = chat["sessions"][chat["activeSessionId"]]
    assert session["configurationDigest"] == chat["configurationDigest"]

def test_configuration_digest_changes_only_with_effective_configuration(tmp_path):
    store = _store(tmp_path)
    first = store.snapshot()
    second = store.set_configuration(
        expected_revision=first["revision"], prompt_intelligence="OFF"
    )
    assert second["configurationRevision"] == first["configurationRevision"] + 1
    assert second["configurationDigest"] != first["configurationDigest"]


def test_invalid_target_root_is_rejected_before_persistence(tmp_path):
    store = _store(tmp_path)
    before = store.snapshot()
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="TARGET_ROOT"):
        store.set_configuration(
            expected_revision=before["revision"], target_root=str(missing)
        )
    assert store.snapshot() == before
