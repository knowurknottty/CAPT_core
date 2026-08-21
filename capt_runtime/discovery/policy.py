"""Discovery policy: escalation ladder, three-guess rule, classification (v0.7).

Policy is code-level, not prompt guidance. The central invariant:

    After three failed direct guesses, the governor MUST stop guessing and
    switch mechanisms to enumeration. The fourth operation is NEVER another
    direct guess.

This module is pure & deterministic so it is exhaustively testable. It owns no
authority; it only decides which bounded observation to try next.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .models import (
    AMBIGUOUS,
    COMPILED_ARTIFACT_ONLY,
    CONTAINER_METADATA_PRESENT,
    EXHAUSTED,
    NOT_APPLICABLE,
    NOT_FOUND,
    PERMISSION_DENIED,
    POSSIBLE_REPOSITORY,
    REJECTED,
    SOURCE_NOT_PROVEN,
    SOURCE_PRESENT,
    UNAVAILABLE,
    UNKNOWN,
)

# Canonical escalation ladder (from MODULE_WISHLIST, treated as default).
ESCALATION_LADDER: Tuple[str, ...] = (
    "KNOWN_PATH",
    "FILESYSTEM_ENUMERATION",
    "CONTAINER_METADATA",
    "BIND_MOUNTS_AND_VOLUMES",
    "IMAGE_LAYERS",
    "HOST_CHECKOUT",
    "REGISTRY_OR_REPOSITORY_LOOKUP",
    "OWNER_CLARIFICATION",
    "STOP",
)

# Strategies considered "direct guesses" (subject to the three-guess rule).
_GUESS_STRATEGIES = {"KNOWN_PATH", "HOST_CHECKOUT", "REGISTRY_OR_REPOSITORY_LOOKUP"}

# Result vocabulary a strategy may return when not supported.
BOUNDED_RESULT_VOCAB = {
    UNAVAILABLE, NOT_APPLICABLE, PERMISSION_DENIED, NOT_FOUND, AMBIGUOUS, EXHAUSTED,
}


def is_guess(strategy: str) -> bool:
    return strategy in _GUESS_STRATEGIES


def is_terminal(vocab: str) -> bool:
    """Terminal result vocab that ends discovery with a definitive classification."""
    return vocab in (SOURCE_PRESENT, NOT_FOUND, EXHAUSTED, PERMISSION_DENIED)


# ---- source classification (conservative, evidence-based) ------------------

_SOURCE_MARKERS = (
    "pyproject.toml", "setup.py", "setup.cfg", "package.json", "go.mod",
    "Cargo.toml", "pom.xml", "build.gradle", "CMakeLists.txt", "Makefile",
    "requirements.txt", "AGENTS.md", "README.md", ".git",
)
_SOURCE_EXT = (".py", ".go", ".rs", ".js", ".ts", ".c", ".h", ".java",
               ".rb", ".php", ".sh", ".md", ".toml", ".yaml", ".yml", ".json")
_BUNDLE_EXT = (".whl", ".tar.gz", ".tgz", ".zip", ".egg", ".so", ".dylib")
_BUNDLE_DIRS = {"dist", "build", "target", "node_modules", ".next", "__pycache__"}


class ClassificationPolicy:
    """Deterministic source/bundle/repo classification.

    Heuristics stay conservative: "package.json present" yields POSSIBLE_REPOSITORY /
    SOURCE_PRESENT only with corroborating source markers, never a strong
    "definitely the target repo" without more evidence.
    """

    def is_source_file(self, filename: str) -> bool:
        if filename in _SOURCE_MARKERS:
            return True
        return filename.endswith(_SOURCE_EXT)

    def is_bundle_file(self, filename: str) -> bool:
        return filename.endswith(_BUNDLE_EXT)

    def is_bundle_dir(self, dirname: str) -> bool:
        return dirname in _BUNDLE_DIRS

    def classify_tree(self, *, n_source_files: int, n_bundle_artifacts: int,
                      has_git: bool, has_project_marker: bool,
                      has_only_bundle: bool) -> str:
        """Classify a scanned tree conservatively."""
        if n_source_files > 0:
            if has_git or has_project_marker:
                return SOURCE_PRESENT
            return POSSIBLE_REPOSITORY   # source files but no strong repo evidence
        if has_only_bundle or n_bundle_artifacts > 0:
            # bundle alone is compiled_artifact_only; source not proven
            return COMPILED_ARTIFACT_ONLY
        if has_git:
            return POSSIBLE_REPOSITORY
        return UNKNOWN


DEFAULT_POLICY = ClassificationPolicy()
