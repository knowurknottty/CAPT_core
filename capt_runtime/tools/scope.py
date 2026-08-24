"""Canonical filesystem scope enforcement for governed local tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from capt_runtime.errors import AuthorityViolation

PathLike = Union[str, os.PathLike[str]]


def _contained(root: Path, target: Path) -> bool:
    try:
        return os.path.commonpath((str(root), str(target))) == str(root)
    except ValueError:
        return False


def _canonical_root(root: PathLike) -> Path:
    try:
        canonical = Path(root).expanduser().resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as exc:
        raise AuthorityViolation(f"filesystem scope root is unavailable: {root}") from exc
    if not canonical.is_dir():
        raise AuthorityViolation(f"filesystem scope root is not a directory: {canonical}")
    return canonical


def require_scoped_path(
    root: PathLike,
    target: PathLike,
    *,
    for_write: bool = False,
) -> Path:
    """Return a canonical in-scope path or fail before filesystem/process effect."""
    canonical_root = _canonical_root(root)
    candidate = Path(target).expanduser()
    if not candidate.is_absolute():
        candidate = canonical_root / candidate

    if for_write:
        # Replacing a symlink is ambiguous at the authority boundary. The file
        # adapter uses atomic replacement, so require an ordinary target name.
        if candidate.is_symlink():
            raise AuthorityViolation(f"write target may not be a symlink: {candidate}")
        try:
            parent = candidate.parent.resolve(strict=True)
        except (FileNotFoundError, RuntimeError) as exc:
            raise AuthorityViolation(
                f"write target parent is unavailable: {candidate.parent}"
            ) from exc
        if not _contained(canonical_root, parent):
            raise AuthorityViolation(
                f"write target escapes filesystem scope: {candidate} not under {canonical_root}"
            )
        resolved = parent / candidate.name
        if candidate.exists():
            try:
                existing = candidate.resolve(strict=True)
            except RuntimeError as exc:
                raise AuthorityViolation(f"write target cannot be resolved: {candidate}") from exc
            if not _contained(canonical_root, existing):
                raise AuthorityViolation(
                    f"write target escapes filesystem scope: {candidate} -> {existing}"
                )
            resolved = existing
        return resolved

    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as exc:
        raise AuthorityViolation(f"path is unavailable inside filesystem scope: {candidate}") from exc
    if not _contained(canonical_root, resolved):
        raise AuthorityViolation(
            f"path escapes filesystem scope: {candidate} -> {resolved}; root={canonical_root}"
        )
    return resolved
