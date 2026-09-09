"""Normalized operator authority for governed model/tool execution.

The macOS surface expresses intent only. This module is the deterministic
runtime boundary that canonicalizes that intent before HumanApproval exists.
The normalized mapping is safe to digest/freeze and is revalidated again at
execution preparation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .errors import AuthorityViolation
from .provider_endpoint import endpoint_class

_SCHEMA_VERSION = "1.0.0"
_ALLOWED_FIELDS = frozenset({
    "filesystemScope",
    "filesystemRoot",
    "fileMutationAllowed",
    "shellAccessAllowed",
    "providerNetworkPolicy",
})
_REQUIRED_FIELDS = _ALLOWED_FIELDS
_SCOPE_VALUES = frozenset({"project", "custom", "full"})
_NETWORK_VALUES = frozenset({"local_only", "remote_allowed"})


def _directory(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityViolation(f"{label}_MISSING")
    try:
        path = Path(value).expanduser().resolve(strict=False)
    except (RuntimeError, OSError) as exc:
        raise AuthorityViolation(f"{label}_UNAVAILABLE") from exc
    if path.exists() and not path.is_dir():
        raise AuthorityViolation(f"{label}_NOT_DIRECTORY")
    return path


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise AuthorityViolation(f"AUTHORITY_FLAG_MUST_BE_BOOLEAN:{name}")
    return value


def normalize_model_authority(
    raw: Mapping[str, Any] | None,
    *,
    target_root: str,
) -> dict[str, Any]:
    """Return the exact bounded authority profile eligible for approval.

    Missing profile means the backwards-compatible safest posture: project-only
    filesystem read/search and local provider endpoints only. An explicit
    profile must be complete; silent partial-profile defaults could otherwise
    turn a serialization bug into accidental authority.
    """
    target = _directory(target_root, label="MODEL_TARGET_ROOT")
    if raw is None:
        values: dict[str, Any] = {
            "filesystemScope": "project",
            "filesystemRoot": str(target),
            "fileMutationAllowed": False,
            "shellAccessAllowed": False,
            "providerNetworkPolicy": "local_only",
        }
    else:
        if not isinstance(raw, Mapping):
            raise AuthorityViolation("AUTHORITY_PROFILE_MALFORMED")
        unknown = set(raw).difference(_ALLOWED_FIELDS)
        if unknown:
            raise AuthorityViolation(
                "AUTHORITY_PROFILE_UNKNOWN_FIELDS:" + ",".join(sorted(map(str, unknown)))
            )
        missing = _REQUIRED_FIELDS.difference(raw)
        if missing:
            raise AuthorityViolation(
                "AUTHORITY_PROFILE_MISSING_FIELDS:" + ",".join(sorted(missing))
            )
        values = dict(raw)

    scope = values["filesystemScope"]
    if scope not in _SCOPE_VALUES:
        raise AuthorityViolation("AUTHORITY_FILESYSTEM_SCOPE_INVALID")
    requested_root = _directory(values["filesystemRoot"], label="AUTHORITY_FILESYSTEM_ROOT")
    if scope == "project":
        if requested_root != target:
            raise AuthorityViolation("PROJECT_SCOPE_ROOT_MISMATCH")
        filesystem_root = target
    elif scope == "full":
        if requested_root != Path("/").resolve():
            raise AuthorityViolation("FULL_SCOPE_ROOT_MUST_BE_SLASH")
        filesystem_root = Path("/").resolve()
    else:
        filesystem_root = requested_root

    mutation = _bool(values["fileMutationAllowed"], "fileMutationAllowed")
    shell = _bool(values["shellAccessAllowed"], "shellAccessAllowed")
    network = values["providerNetworkPolicy"]
    if network not in _NETWORK_VALUES:
        raise AuthorityViolation("AUTHORITY_PROVIDER_NETWORK_POLICY_INVALID")

    operations = ["file.read", "file.search"]
    if mutation:
        operations.extend(["file.write", "file.patch"])
    if shell:
        operations.append("terminal.exec")
    risk = (
        "consequential"
        if mutation or shell or network == "remote_allowed" or scope == "full"
        else "low"
    )
    return {
        "schemaVersion": _SCHEMA_VERSION,
        "filesystemScope": scope,
        "filesystemRoot": str(filesystem_root),
        "fileMutationAllowed": mutation,
        "shellAccessAllowed": shell,
        "providerNetworkPolicy": network,
        "toolOperations": operations,
        "riskClassification": risk,
    }


def assert_provider_network_allowed(profile: Mapping[str, Any], base_url: str) -> None:
    """Fail before HTTP dispatch when approval permits local endpoints only."""
    policy = profile.get("providerNetworkPolicy")
    if policy not in _NETWORK_VALUES:
        raise AuthorityViolation("AUTHORITY_PROVIDER_NETWORK_POLICY_INVALID")
    if policy == "local_only" and endpoint_class(base_url) != "local":
        raise AuthorityViolation("REMOTE_PROVIDER_NETWORK_NOT_AUTHORIZED")


def revalidate_normalized_model_authority(
    profile: Mapping[str, Any], *, target_root: str
) -> dict[str, Any]:
    """Re-derive a frozen approval profile and reject any widened/drifted field."""
    if not isinstance(profile, Mapping):
        raise AuthorityViolation("AUTHORITY_PROFILE_MALFORMED")
    required_normalized = {
        "schemaVersion", "filesystemScope", "filesystemRoot",
        "fileMutationAllowed", "shellAccessAllowed", "providerNetworkPolicy",
        "toolOperations", "riskClassification",
    }
    if set(profile) != required_normalized:
        raise AuthorityViolation("AUTHORITY_PROFILE_NORMALIZED_FIELDS_INVALID")
    if profile.get("schemaVersion") != _SCHEMA_VERSION:
        raise AuthorityViolation("AUTHORITY_PROFILE_SCHEMA_INVALID")
    base = {key: profile[key] for key in _ALLOWED_FIELDS}
    normalized = normalize_model_authority(base, target_root=target_root)
    candidate = dict(profile)
    operations = candidate.get("toolOperations")
    if isinstance(operations, tuple):
        candidate["toolOperations"] = list(operations)
    if candidate != normalized:
        raise AuthorityViolation("AUTHORITY_PROFILE_NORMALIZED_MISMATCH")
    return normalized
