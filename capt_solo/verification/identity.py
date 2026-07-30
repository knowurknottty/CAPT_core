"""Verified State Identity (VSI) — what was verified, exactly.

A VSI captures the identity of the state under verification so that a prior
verification result can be reused when the state is unchanged. It is deliberately
cheap to compute: git metadata + scoped file hashes + environment fingerprints.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .scope import VerificationScope, SCOPE_PATH_GLOBS


def _git(repo: str, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", repo, *args], capture_output=True, text=True, timeout=20)
        return out.stdout.strip()
    except Exception:
        return ""


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _hash_file(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return None


def _project_id(repo: str) -> str:
    pyproject = os.path.join(repo, "pyproject.toml")
    if os.path.exists(pyproject):
        txt = open(pyproject).read()
        for line in txt.splitlines():
            if line.strip().startswith("name"):
                # name = "capt-solo"
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.path.basename(os.path.abspath(repo))


def _scoped_files(repo: str, scope: VerificationScope) -> List[str]:
    """Return absolute paths of files relevant to a scope (tracked + untracked).

    Untracked files are included because they can still ship in a build or
    affect runtime (e.g. an untracked module under a packaged path). Excluding
    them from the identity would let prior verification be reused for a tree
    whose effective content differs — a release-evidence spoofing risk.
    """
    globs = SCOPE_PATH_GLOBS.get(scope, [])
    if scope == VerificationScope.FULL:
        # Tracked files plus untracked, non-ignored files. `git ls-files
        # --others --exclude-standard` surfaces untracked content that a build
        # could pick up; .gitignored artifacts (e.g. .capt_verify/, venvs) are
        # still excluded by --exclude-standard.
        tracked = _git(repo, "ls-files").splitlines()
        untracked = _git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
        files = [os.path.join(repo, f) for f in tracked + untracked if f]
    else:
        files = []
        for root, _dirs, fs in os.walk(repo):
            if ".git" in root.split(os.sep):
                continue
            for f in fs:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, repo)
                if any(_match_glob(rel, g) for g in globs):
                    files.append(full)
    return sorted(files)


def _match_glob(rel: str, glob: str) -> bool:
    import fnmatch
    return fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(rel, glob.lstrip("./"))


def _scope_file_hashes(repo: str, scope: VerificationScope) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for path in _scoped_files(repo, scope):
        h = _hash_file(path)
        if h is not None:
            out[os.path.relpath(path, repo)] = h
    return out


def _dependency_state(repo: str) -> str:
    parts = []
    for name in ("requirements.txt", "poetry.lock", "Pipfile.lock", "pyproject.toml"):
        p = os.path.join(repo, name)
        h = _hash_file(p)
        if h:
            parts.append(f"{name}:{h}")
    return _hash_text("|".join(parts))


def _runtime_identity() -> str:
    return f"py{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _operating_environment() -> str:
    import platform
    return f"{platform.system().lower()}-{platform.release()}"


@dataclass
class VerifiedStateIdentity:
    """Exact identity of the verified state.

    Two VSIs are equivalent iff every field except `timestamp` matches.
    """
    repository: str
    project_id: str
    active_branch: str
    head_commit: str
    working_tree_status: str          # git status --porcelain
    scope_file_hashes: Dict[str, str]  # path -> hash, for the verification scope
    dependency_state: str
    runtime_identity: str
    operating_environment: str
    verification_command: str
    verification_scope: str
    timestamp: str = ""

    def identity_tuple(self):
        # NOTE: working_tree_status (git porcelain) is intentionally excluded from
        # equivalence. It includes untracked artifacts (e.g. .capt_verify/, temp
        # files) that are not part of the verified state. Equivalence is driven by
        # scoped file hashes + HEAD + dependency + environment + command + scope.
        return (
            self.repository, self.project_id, self.active_branch, self.head_commit,
            tuple(sorted(self.scope_file_hashes.items())),
            self.dependency_state, self.runtime_identity, self.operating_environment,
            self.verification_command, self.verification_scope,
        )


class VsiDiffReason:
    HEAD_CHANGED = "head_changed"
    DEPENDENCY_CHANGED = "dependency_changed"
    ENVIRONMENT_CHANGED = "environment_changed"
    COMMAND_CHANGED = "command_changed"
    SCOPE_EXPANDED = "scope_expanded"
    WORKING_TREE_CHANGED = "working_tree_changed"
    ARTIFACT_CHANGED = "artifact_changed"
    REQUESTED_BY_USER = "requested_by_user"


def build_vsi(repo: str, scope: VerificationScope, command: str,
              environment: Optional[str] = None) -> VerifiedStateIdentity:
    """Build a VSI for the given repo + scope + command."""
    from datetime import datetime, timezone
    repo = os.path.abspath(repo)
    return VerifiedStateIdentity(
        repository=repo,
        project_id=_project_id(repo),
        active_branch=_git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "unknown",
        head_commit=_git(repo, "rev-parse", "HEAD") or "unknown",
        working_tree_status=_git(repo, "status", "--porcelain"),
        scope_file_hashes=_scope_file_hashes(repo, scope),
        dependency_state=_dependency_state(repo),
        runtime_identity=_runtime_identity(),
        operating_environment=environment or _operating_environment(),
        verification_command=command,
        verification_scope=scope.value,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def vsi_equivalent(a: VerifiedStateIdentity, b: VerifiedStateIdentity) -> bool:
    return a.identity_tuple() == b.identity_tuple()


def diff_vsi(old: VerifiedStateIdentity, new: VerifiedStateIdentity) -> List[Dict[str, str]]:
    """Return the exact reasons `new` is not equivalent to `old`."""
    reasons: List[Dict[str, str]] = []
    if old.head_commit != new.head_commit:
        reasons.append({"reason": VsiDiffReason.HEAD_CHANGED,
                        "detail": f"{old.head_commit[:8]} -> {new.head_commit[:8]}"})
    if old.dependency_state != new.dependency_state:
        reasons.append({"reason": VsiDiffReason.DEPENDENCY_CHANGED, "detail": "lockfile/pyproject hash changed"})
    if (old.runtime_identity != new.runtime_identity or
            old.operating_environment != new.operating_environment):
        reasons.append({"reason": VsiDiffReason.ENVIRONMENT_CHANGED,
                        "detail": f"{old.runtime_identity}/{old.operating_environment} -> "
                                  f"{new.runtime_identity}/{new.operating_environment}"})
    if old.verification_command != new.verification_command:
        reasons.append({"reason": VsiDiffReason.COMMAND_CHANGED,
                        "detail": f"{old.verification_command} -> {new.verification_command}"})
    if old.verification_scope != new.verification_scope:
        # treat as expanded if new is broader (FULL vs specific)
        broader = (new.verification_scope == VerificationScope.FULL.value and
                   old.verification_scope != VerificationScope.FULL.value)
        reasons.append({"reason": VsiDiffReason.SCOPE_EXPANDED if broader else VsiDiffReason.COMMAND_CHANGED,
                        "detail": f"{old.verification_scope} -> {new.verification_scope}"})
    if old.scope_file_hashes != new.scope_file_hashes:
        changed = {
            p for p in set(new.scope_file_hashes) | set(old.scope_file_hashes)
            if new.scope_file_hashes.get(p) != old.scope_file_hashes.get(p)
        }
        reasons.append({"reason": VsiDiffReason.WORKING_TREE_CHANGED,
                        "detail": f"{len(changed)} scoped file(s) changed"})
    return reasons
