"""Verification scopes and path→scope mapping for targeted verification."""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Set


class VerificationScope(str, Enum):
    FULL = "full"
    SUITE = "suite"
    ENGINE_MATH = "engine_math"
    ENGINE_PHYSICS = "engine_physics"
    ENGINE_INVENTION = "engine_invention"
    MEMORY = "memory"
    BOUNDARY = "boundary"
    DOCS = "docs"
    REGISTRY = "registry"
    WORKSPACE = "workspace"


# Path globs (relative to repo root) that belong to each scope.
SCOPE_PATH_GLOBS: Dict[VerificationScope, List[str]] = {
    VerificationScope.ENGINE_MATH: [
        "capt_solo/engines/mathematics.py", "tests/test_mathematics.py",
    ],
    VerificationScope.ENGINE_PHYSICS: [
        "capt_solo/engines/physics.py", "tests/test_physics.py",
    ],
    VerificationScope.ENGINE_INVENTION: [
        "capt_solo/engines/invention.py", "tests/test_invention.py",
    ],
    VerificationScope.MEMORY: [
        "capt_solo/memory/*.py", "capt_solo/learning/dream.py",
        "tests/test_memory_types.py",
    ],
    VerificationScope.BOUNDARY: [
        "capt_solo/pulse.py", "pyproject.toml", "tests/test_release_boundary.py",
        "dist/*.whl",
    ],
    VerificationScope.DOCS: [
        "docs/**/*.md", "*.md", "README.md", "CONTRIBUTING.md", "CHANGELOG.md",
    ],
    VerificationScope.REGISTRY: [
        "architecture/**/*", "architecture/registry.yaml",
    ],
    VerificationScope.WORKSPACE: [
        "capt_solo/workspace.py", "capt_cli.py", "capt_solo/workspace/**/*.py",
    ],
}


def _match(rel: str, glob: str) -> bool:
    import fnmatch
    g = glob.lstrip("./")
    if fnmatch.fnmatch(rel, g):
        return True
    # support ** by simple prefix match on directory segments
    if "**" in g:
        prefix = g.split("**")[0].rstrip("/")
        return rel.startswith(prefix) or ("/" + prefix + "/") in ("/" + rel)
    return False


def map_paths_to_scopes(paths: Iterable[str]) -> Set[VerificationScope]:
    """Map changed file paths (repo-relative) to the scopes they affect."""
    rels = [p if not os.path.isabs(p) else p for p in paths]
    scopes: Set[VerificationScope] = set()
    for rel in rels:
        rel = rel.replace("\\", "/")
        matched = False
        for scope, globs in SCOPE_PATH_GLOBS.items():
            if any(_match(rel, g) for g in globs):
                scopes.add(scope)
                matched = True
        if not matched:
            # unknown path: assume it could affect everything
            scopes.add(VerificationScope.FULL)
    return scopes


def select_scope_for_changes(changed_paths: Iterable[str]) -> VerificationScope:
    """Pick the narrowest scope to verify given changed paths.

    If multiple specific scopes are affected, return SUITE (run the test suite
    but not necessarily the entire repo). If FULL is implicated, return FULL.
    """
    scopes = map_paths_to_scopes(changed_paths)
    if not scopes:
        return VerificationScope.DOCS
    if VerificationScope.FULL in scopes:
        return VerificationScope.FULL
    if len(scopes) == 1:
        return next(iter(scopes))
    return VerificationScope.SUITE


@dataclass
class ScopeCommand:
    scope: VerificationScope
    pytest_args: List[str]


# How to run verification for each scope (pytest target).
SCOPE_COMMANDS: Dict[VerificationScope, List[str]] = {
    VerificationScope.FULL: ["-q"],
    VerificationScope.SUITE: ["-q"],
    VerificationScope.ENGINE_MATH: ["tests/test_mathematics.py", "-q"],
    VerificationScope.ENGINE_PHYSICS: ["tests/test_physics.py", "-q"],
    VerificationScope.ENGINE_INVENTION: ["tests/test_invention.py", "-q"],
    VerificationScope.MEMORY: ["tests/test_memory_types.py", "-q"],
    VerificationScope.BOUNDARY: ["tests/test_release_boundary.py", "-q"],
    VerificationScope.DOCS: [],   # documentation-only: no test run required
    VerificationScope.REGISTRY: ["architecture/validate_registry.py"],
    VerificationScope.WORKSPACE: ["tests/test_workspace.py", "-q"],
}


def command_for_scope(scope: VerificationScope) -> str:
    args = SCOPE_COMMANDS.get(scope, ["-q"])
    if not args:
        return "no-op (documentation-only)"
    return "python3 -m pytest " + " ".join(args)
