"""Project Workspace Isolation — bounded project boundary (.capt/).

Enforces distinct scopes: workspace / project_memory / global_memory.
Prevents contamination of global CAPT/bioCAPT state and implicit writes outside
the project root. Rejects path traversal, symlink escape, and implicit global
persistence.

In an unbound workspace (no PROJECT_CONTEXT.json), inspection may continue but
project/global persistence must not occur.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class WorkspaceScope(str, Enum):
    WORKSPACE = "workspace"
    PROJECT_MEMORY = "project_memory"
    GLOBAL_MEMORY = "global_memory"


class BindState(str, Enum):
    BOUND = "bound"
    UNBOUND = "unbound"


@dataclass
class ProjectContext:
    schema_version: str = "1.0"
    project_id: str = ""
    repository: str = ""
    canonical_root: str = ""
    branch_policy: str = "integration/full-public-architecture"
    allowed_write_roots: List[str] = field(default_factory=list)
    forbidden_write_roots: List[str] = field(default_factory=list)
    evidence_root: str = ".capt/evidence"
    scratch_root: str = ".capt/scratch"
    quarantine_root: str = ".capt/quarantine"
    project_memory_namespace: str = ""
    memory_promotion_policy: str = "explicit"
    external_mutation_policy: str = "deny"
    raw: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: Dict) -> "ProjectContext":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class WorkspaceIsolationError(Exception):
    """Raised on forbidden write, traversal, or scope violation."""


class ProjectWorkspace:
    def __init__(self, root: str) -> None:
        self._root = os.path.abspath(root)
        self._context_path = os.path.join(self._root, ".capt", "PROJECT_CONTEXT.json")
        self._context: Optional[ProjectContext] = None
        self._bind_state = BindState.UNBOUND
        if os.path.exists(self._context_path):
            try:
                with open(self._context_path) as f:
                    self._context = ProjectContext.from_dict(json.load(f))
                self._bind_state = BindState.BOUND
            except Exception:
                self._context = None
                self._bind_state = BindState.UNBOUND

    @property
    def bind_state(self) -> str:
        return self._bind_state.value

    @property
    def context(self) -> Optional[ProjectContext]:
        return self._context

    def is_bound(self) -> bool:
        return self._bind_state == BindState.BOUND

    # ---- path safety ----
    def _safe_path(self, path: str) -> str:
        """Resolve and ensure the path stays within the project root.

        Rejects path traversal and symlink escape. Returns the canonical path.
        """
        if path.startswith("/") or ".." in path.split("/") or "\\" in path:
            # absolute or traversal attempt
            if not os.path.isabs(path):
                # relative with '..' -> reject
                if ".." in path.replace("\\", "/").split("/"):
                    raise WorkspaceIsolationError(f"path traversal rejected: {path}")
        resolved = os.path.realpath(os.path.join(self._root, path))
        root_real = os.path.realpath(self._root)
        if resolved != root_real and not resolved.startswith(root_real + os.sep):
            raise WorkspaceIsolationError(f"escape outside project root rejected: {path}")
        return resolved

    def can_write(self, path: str, scope: WorkspaceScope) -> bool:
        """Whether a write to `path` under `scope` is permitted."""
        if self._bind_state == BindState.UNBOUND:
            # unbound: no project/global persistence; workspace writes also blocked
            # outside the visible project unless explicitly allowed.
            return False
        if scope == WorkspaceScope.GLOBAL_MEMORY:
            # global memory requires explicit approval; never implicit
            return False
        try:
            self._safe_path(path)
        except WorkspaceIsolationError:
            return False
        # forbidden roots
        for fr in (self._context.forbidden_write_roots if self._context else []):
            try:
                if self._safe_path(path).startswith(self._safe_path(fr)):
                    return False
            except WorkspaceIsolationError:
                return False
        return True

    def require_scope(self, scope: WorkspaceScope, path: Optional[str] = None) -> str:
        """Validate and return a safe path for the requested scope, or raise."""
        if scope == WorkspaceScope.GLOBAL_MEMORY:
            raise WorkspaceIsolationError(
                "global memory write rejected: requires explicit cross-project approval")
        if self._bind_state == BindState.UNBOUND:
            raise WorkspaceIsolationError(
                "workspace unbound: project/global persistence must not occur")
        if path is None:
            if scope == WorkspaceScope.WORKSPACE:
                path = os.path.join(".capt", "scratch")
            else:
                path = os.path.join(".capt", "evidence")
        return self._safe_path(path)

    def bind(self, context: ProjectContext) -> None:
        """Create .capt/PROJECT_CONTEXT.json (explicit binding)."""
        ctx = context
        ctx.canonical_root = self._root
        ctx.repository = ctx.repository or os.path.basename(self._root)
        ctx.project_memory_namespace = ctx.project_memory_namespace or ctx.project_id
        os.makedirs(os.path.join(self._root, ".capt"), exist_ok=True)
        with open(self._context_path, "w") as f:
            json.dump(ctx.to_dict(), f, indent=2)
        self._context = ctx
        self._bind_state = BindState.BOUND

    def declare_unbound(self) -> None:
        self._bind_state = BindState.UNBOUND
        self._context = None
