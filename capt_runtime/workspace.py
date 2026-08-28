"""Canonical target-workspace resolution for governed filesystem operations.

A persistent CAPT runtime must never use its own process cwd as an implicit
repository target. Callers supply a workspace explicitly; the runtime
canonicalizes and validates that exact resource before authority is granted.
"""
from __future__ import annotations

from pathlib import Path


class TargetWorkspaceError(ValueError):
    """Raised when a governed filesystem operation lacks a valid target root."""


def resolve_target_root(raw: str | Path | None) -> str:
    """Return the canonical absolute directory for an explicit target root.

    No cwd fallback is permitted. Symlinks are resolved before governance so
    approval, capability scope, worktree creation, and driver execution bind
    to one stable resource identity.
    """
    if raw is None or not str(raw).strip():
        raise TargetWorkspaceError("TARGET_WORKSPACE_REQUIRED")
    candidate = Path(str(raw)).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise TargetWorkspaceError("TARGET_WORKSPACE_NOT_FOUND") from exc
    if not resolved.is_dir():
        raise TargetWorkspaceError("TARGET_WORKSPACE_NOT_DIRECTORY")
    return str(resolved)
