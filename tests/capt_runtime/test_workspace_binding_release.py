from __future__ import annotations

from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.model_authority import canonical_execution_target_root
from desktop.operator_control import OperatorControlStore


def _defaults(target: str = "") -> dict[str, str]:
    return {
        "provider": "ollama",
        "model": "qwen3.5-defiant-fable:latest",
        "targetRoot": target,
        "promptIntelligence": "AUTO",
    }


def test_operator_control_allows_no_target_selected(tmp_path: Path):
    store = OperatorControlStore(tmp_path / "operator-control.json", _defaults())
    snap = store.snapshot()
    assert snap["targetRoot"] == ""
    assert "CAPT_core" not in snap["targetRoot"]


def test_canonical_execution_target_rejects_missing_nonexistent_and_file(tmp_path: Path):
    with pytest.raises(AuthorityViolation, match="MODEL_TARGET_ROOT_MISSING"):
        canonical_execution_target_root("")
    with pytest.raises(AuthorityViolation, match="MODEL_TARGET_ROOT_NOT_FOUND"):
        canonical_execution_target_root(str(tmp_path / "missing"))
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(AuthorityViolation, match="MODEL_TARGET_ROOT_NOT_DIRECTORY"):
        canonical_execution_target_root(str(f))


def test_canonical_execution_target_resolves_symlink_to_real_directory(tmp_path: Path):
    real = tmp_path / "external-repo"
    real.mkdir()
    link = tmp_path / "repo-link"
    link.symlink_to(real, target_is_directory=True)
    assert canonical_execution_target_root(str(link)) == str(real.resolve())


def test_operator_control_accepts_explicit_external_repo_and_canonicalizes(tmp_path: Path):
    initial = tmp_path / "initial"
    external = tmp_path / "external"
    initial.mkdir()
    external.mkdir()
    store = OperatorControlStore(
        tmp_path / "operator-control.json", _defaults(str(initial))
    )
    snap = store.set_configuration(
        expected_revision=0, target_root=str(external / ".")
    )
    assert snap["targetRoot"] == str(external.resolve())


def test_operator_control_rejects_nonexistent_target_when_selected(tmp_path: Path):
    store = OperatorControlStore(tmp_path / "operator-control.json", _defaults())
    with pytest.raises(ValueError, match="TARGET_ROOT_NOT_DIRECTORY"):
        store.set_configuration(
            expected_revision=0, target_root=str(tmp_path / "missing")
        )
