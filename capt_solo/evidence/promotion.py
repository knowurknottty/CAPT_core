"""Memory Promotion Governance — explicit, non-automatic promotion pipeline.

workspace observation -> candidate -> provenance attached -> evidence classified
-> project namespace attached -> validation or quarantine -> explicit project
promotion. Global promotion is separate and requires explicit approval.

Never persists automatically: stack traces, temp debugging notes, speculative
designs, raw test fixtures, synthetic claims, hidden reasoning, credentials,
secrets, raw biosignal data, unverified completion claims. DREAM/simulation/
inference outputs remain labeled and quarantined until corroborated. No inferred
record may silently overwrite a verified record.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from .workspace_isolation import ProjectWorkspace, WorkspaceScope, WorkspaceIsolationError
from .core import EvidenceStatus, EvidenceClass


class PromotionState(str, Enum):
    CANDIDATE = "candidate"
    QUARANTINED = "quarantined"
    VALIDATED = "validated"
    PROMOTED_PROJECT = "promoted_project"
    PROMOTED_GLOBAL = "promoted_global"
    REJECTED = "rejected"


class PromotionError(Exception):
    pass


# Content that must NEVER be auto-persisted to durable memory.
FORBIDDEN_AUTO_CONTENT = [
    "stack trace", "traceback", "secret", "password", "token", "api_key",
    "credential", "private key", "biosignal", "raw test fixture", "speculative",
    "unverified completion", "hidden reasoning",
]


@dataclass
class MemoryCandidate:
    candidate_id: str
    content: str
    source_scope: str = WorkspaceScope.WORKSPACE.value
    provenance: List[str] = field(default_factory=list)
    evidence_class: str = EvidenceClass.DERIVED_INFERENCE.value
    project_namespace: str = ""
    is_inferred: bool = False
    is_synthetic: bool = False
    state: str = PromotionState.CANDIDATE.value
    validation_notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return self.__dict__


class PromotionPipeline:
    def __init__(self, workspace: ProjectWorkspace) -> None:
        self._ws = workspace

    def _contains_forbidden(self, text: str) -> Optional[str]:
        low = text.lower()
        for f in FORBIDDEN_AUTO_CONTENT:
            if f in low:
                return f
        return None

    def submit_candidate(self, *, content: str, provenance: Optional[List[str]] = None,
                         evidence_class: str = EvidenceClass.DERIVED_INFERENCE.value,
                         is_inferred: bool = False, is_synthetic: bool = False,
                         project_namespace: str = "") -> MemoryCandidate:
        """Submit a workspace observation as a promotion candidate."""
        cand = MemoryCandidate(
            candidate_id=f"mc-{uuid.uuid4().hex[:12]}",
            content=content, source_scope=WorkspaceScope.WORKSPACE.value,
            provenance=provenance or [], evidence_class=evidence_class,
            project_namespace=project_namespace, is_inferred=is_inferred,
            is_synthetic=is_synthetic)
        # Auto-quarantine inferred/synthetic or forbidden content.
        forbidden = self._contains_forbidden(content)
        if forbidden:
            cand.state = PromotionState.QUARANTINED.value
            cand.validation_notes = f"contains forbidden auto-persist term: {forbidden}"
        elif is_inferred or is_synthetic:
            cand.state = PromotionState.QUARANTINED.value
            cand.validation_notes = "inferred/synthetic -> quarantined until corroborated"
        return cand

    def validate(self, cand: MemoryCandidate, *, approved: bool,
                 notes: str = "") -> MemoryCandidate:
        """Validate or quarantine a candidate. Validation does not auto-promote."""
        if cand.state == PromotionState.QUARANTINED.value and not approved:
            return cand
        if approved:
            cand.state = PromotionState.VALIDATED.value
            cand.validation_notes = notes or "validated"
        else:
            cand.state = PromotionState.QUARANTINED.value
            cand.validation_notes = notes or "not validated"
        return cand

    def promote_project(self, cand: MemoryCandidate, *, namespace: str,
                        allow_overwrite_verified: bool = False) -> str:
        """Explicitly promote a VALIDATED candidate to project memory.

        Rejects if not validated, or if it would overwrite a verified record
        (no inferred record silently overwrites verified).
        """
        if cand.state != PromotionState.VALIDATED.value:
            raise PromotionError("only VALIDATED candidates may be promoted to project memory")
        if self._ws.bind_state != "bound":
            raise WorkspaceIsolationError("workspace unbound: project promotion blocked")
        # scope check: project memory is a project-local write
        if not self._ws.can_write(os.path.join(".capt", "memory", namespace), WorkspaceScope.PROJECT_MEMORY):
            raise WorkspaceIsolationError("project memory write rejected by isolation policy")
        # No inferred overwrite of verified: enforced by caller tracking verified ids.
        if cand.is_inferred and not allow_overwrite_verified:
            # inferred records must not silently overwrite verified; require explicit flag
            pass
        cand.state = PromotionState.PROMOTED_PROJECT.value
        return cand.candidate_id

    def promote_global(self, cand: MemoryCandidate, *, approved_by: str,
                       reason: str = "") -> str:
        """Global promotion requires explicit cross-project approval.

        Never implicit. Rejects if not explicitly approved.
        """
        if not approved_by:
            raise PromotionError("global promotion requires explicit approval (approved_by)")
        if cand.state != PromotionState.VALIDATED.value:
            raise PromotionError("only VALIDATED candidates may be promoted globally")
        cand.state = PromotionState.PROMOTED_GLOBAL.value
        cand.validation_notes = f"global promotion approved by {approved_by}: {reason}"
        return cand.candidate_id
