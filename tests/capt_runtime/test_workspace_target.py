from pathlib import Path

import pytest

from capt_runtime.workspace import TargetWorkspaceError, resolve_target_root


def test_external_workspace_is_preserved_and_canonicalized(tmp_path: Path) -> None:
    repo = tmp_path / "flock-sucker"
    repo.mkdir()
    assert resolve_target_root(str(repo)) == str(repo.resolve())


def test_symlink_workspace_resolves_to_same_authority_resource(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    link = tmp_path / "alias"
    link.symlink_to(repo, target_is_directory=True)
    assert resolve_target_root(str(link)) == str(repo.resolve())


@pytest.mark.parametrize("raw,code", [
    (None, "TARGET_WORKSPACE_REQUIRED"),
    ("", "TARGET_WORKSPACE_REQUIRED"),
])
def test_missing_workspace_fails_closed(raw, code) -> None:
    with pytest.raises(TargetWorkspaceError, match=code):
        resolve_target_root(raw)


def test_nonexistent_workspace_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(TargetWorkspaceError, match="TARGET_WORKSPACE_NOT_FOUND"):
        resolve_target_root(tmp_path / "missing")


def test_file_is_not_accepted_as_workspace(tmp_path: Path) -> None:
    file = tmp_path / "not-a-workspace"
    file.write_text("x")
    with pytest.raises(TargetWorkspaceError, match="TARGET_WORKSPACE_NOT_DIRECTORY"):
        resolve_target_root(file)
