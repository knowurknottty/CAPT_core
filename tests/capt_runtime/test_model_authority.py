from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.model_authority import (
    assert_provider_network_allowed,
    normalize_model_authority,
)


def test_default_authority_is_project_scoped_read_search_local_only(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    profile = normalize_model_authority(None, target_root=str(repo))

    assert profile == {
        "schemaVersion": "1.0.0",
        "filesystemScope": "project",
        "filesystemRoot": str(repo.resolve()),
        "fileMutationAllowed": False,
        "shellAccessAllowed": False,
        "providerNetworkPolicy": "local_only",
        "toolOperations": ["file.read", "file.search"],
        "riskClassification": "low",
    }


def test_consequential_authority_derives_exact_tool_operations(tmp_path: Path):
    repo = tmp_path / "repo"; repo.mkdir()
    workspace = tmp_path / "workspace"; workspace.mkdir()
    profile = normalize_model_authority(
        {
            "filesystemScope": "custom",
            "filesystemRoot": str(workspace),
            "fileMutationAllowed": True,
            "shellAccessAllowed": True,
            "providerNetworkPolicy": "remote_allowed",
        },
        target_root=str(repo),
    )
    assert profile["filesystemRoot"] == str(workspace.resolve())
    assert profile["toolOperations"] == [
        "file.read", "file.search", "file.write", "file.patch", "terminal.exec"
    ]
    assert profile["riskClassification"] == "consequential"


def test_project_scope_cannot_widen_root_away_from_target(tmp_path: Path):
    repo = tmp_path / "repo"; repo.mkdir()
    other = tmp_path / "other"; other.mkdir()
    with pytest.raises(AuthorityViolation, match="PROJECT_SCOPE_ROOT_MISMATCH"):
        normalize_model_authority(
            {
                "filesystemScope": "project",
                "filesystemRoot": str(other),
                "fileMutationAllowed": False,
                "shellAccessAllowed": False,
                "providerNetworkPolicy": "local_only",
            },
            target_root=str(repo),
        )


def test_full_scope_requires_exact_filesystem_root(tmp_path: Path):
    repo = tmp_path / "repo"; repo.mkdir()
    with pytest.raises(AuthorityViolation, match="FULL_SCOPE_ROOT_MUST_BE_SLASH"):
        normalize_model_authority(
            {
                "filesystemScope": "full",
                "filesystemRoot": str(repo),
                "fileMutationAllowed": False,
                "shellAccessAllowed": False,
                "providerNetworkPolicy": "local_only",
            },
            target_root=str(repo),
        )


def test_authority_profile_rejects_unknown_fields_and_non_boolean_flags(tmp_path: Path):
    repo = tmp_path / "repo"; repo.mkdir()
    with pytest.raises(AuthorityViolation, match="AUTHORITY_PROFILE_UNKNOWN_FIELDS"):
        normalize_model_authority(
            {
                "filesystemScope": "project", "filesystemRoot": str(repo),
                "fileMutationAllowed": False, "shellAccessAllowed": False,
                "providerNetworkPolicy": "local_only", "magicBypass": True,
            },
            target_root=str(repo),
        )
    with pytest.raises(AuthorityViolation, match="AUTHORITY_FLAG_MUST_BE_BOOLEAN"):
        normalize_model_authority(
            {
                "filesystemScope": "project", "filesystemRoot": str(repo),
                "fileMutationAllowed": "yes", "shellAccessAllowed": False,
                "providerNetworkPolicy": "local_only",
            },
            target_root=str(repo),
        )


def test_local_only_provider_policy_fails_before_cloud_dispatch():
    profile = {
        "providerNetworkPolicy": "local_only",
    }
    assert_provider_network_allowed(profile, "http://127.0.0.1:11434/v1")
    assert_provider_network_allowed(profile, "http://localhost:8080/v1")
    with pytest.raises(AuthorityViolation, match="REMOTE_PROVIDER_NETWORK_NOT_AUTHORIZED"):
        assert_provider_network_allowed(profile, "https://openrouter.ai/api/v1")


def test_revalidation_rejects_post_approval_tool_widening(tmp_path: Path):
    from capt_runtime.model_authority import revalidate_normalized_model_authority

    repo = tmp_path / "repo"; repo.mkdir()
    normalized = normalize_model_authority(None, target_root=str(repo))
    tampered = dict(normalized)
    tampered["toolOperations"] = normalized["toolOperations"] + ["terminal.exec"]
    with pytest.raises(AuthorityViolation, match="AUTHORITY_PROFILE_NORMALIZED_MISMATCH"):
        revalidate_normalized_model_authority(tampered, target_root=str(repo))


def test_revalidation_accepts_exact_frozen_authority(tmp_path: Path):
    from capt_runtime.model_authority import revalidate_normalized_model_authority

    repo = tmp_path / "repo"; repo.mkdir()
    normalized = normalize_model_authority(
        {
            "filesystemScope": "project",
            "filesystemRoot": str(repo),
            "fileMutationAllowed": True,
            "shellAccessAllowed": False,
            "providerNetworkPolicy": "local_only",
        },
        target_root=str(repo),
    )
    assert revalidate_normalized_model_authority(
        normalized, target_root=str(repo)
    ) == normalized


def test_revalidation_accepts_immutable_prepared_execution_representation(tmp_path: Path):
    from capt_runtime.model_authority import revalidate_normalized_model_authority
    from capt_runtime.prepared_execution import freeze

    repo = tmp_path / "repo-frozen"; repo.mkdir()
    normalized = normalize_model_authority(None, target_root=str(repo))
    frozen = freeze(normalized)
    assert revalidate_normalized_model_authority(
        frozen, target_root=str(repo)
    ) == normalized
