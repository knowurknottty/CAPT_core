"""Verification records, status values, evidence, and policy."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class VerificationStatus(str, Enum):
    STATE_UNCHANGED = "state_unchanged"              # VSI equivalent; nothing to do
    VERIFICATION_CURRENT = "verification_current"    # prior result reused, valid
    VERIFICATION_REQUIRED = "verification_required"  # VSI changed; must run
    VERIFICATION_PARTIAL = "verification_partial"    # some scopes ran, others current
    VERIFICATION_SUPERSEDED = "verification_superseded"  # old record replaced
    VERIFICATION_INVALIDATED = "verification_invalidated"  # prior result no longer valid


@dataclass
class VerificationEvidence:
    """Pointer to where evidence lives (file path, command output, hashes)."""
    location: str
    summary: str = ""
    passed: Optional[int] = None
    failed: Optional[int] = None
    command: str = ""
    artifact: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location, "summary": self.summary,
            "passed": self.passed, "failed": self.failed,
            "command": self.command, "artifact": self.artifact,
        }


@dataclass
class VerificationRecord:
    """A stored verification outcome tied to a VSI."""
    record_id: str
    vsi: Any                       # VerifiedStateIdentity (serialized)
    status: str
    evidence: VerificationEvidence
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    invalidated_by: Optional[str] = None   # record_id that superseded this

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "vsi": self.vsi if isinstance(self.vsi, dict) else _vsi_to_dict(self.vsi),
            "status": self.status,
            "evidence": self.evidence.to_dict(),
            "confidence": self.confidence,
            "created_at": self.created_at,
            "invalidated_by": self.invalidated_by,
        }


def _vsi_to_dict(vsi: Any) -> Dict[str, Any]:
    if hasattr(vsi, "to_dict"):
        return vsi.to_dict()
    # VerifiedStateIdentity has no to_dict; build minimal
    return {
        "repository": vsi.repository, "project_id": vsi.project_id,
        "active_branch": vsi.active_branch, "head_commit": vsi.head_commit,
        "working_tree_status": vsi.working_tree_status,
        "scope_file_hashes": vsi.scope_file_hashes,
        "dependency_state": vsi.dependency_state,
        "runtime_identity": vsi.runtime_identity,
        "operating_environment": vsi.operating_environment,
        "verification_command": vsi.verification_command,
        "verification_scope": vsi.verification_scope,
    }


@dataclass
class VerificationPolicy:
    """Controls when verification is required vs reused.

    - reuse_when_equivalent: if True, identical VSI reuses prior evidence.
    - full_on_head_change: HEAD change forces full-suite run.
    - full_on_dependency_change: dependency lock change forces full-suite run.
    - full_on_environment_change: environment change forces full-suite run.
    - doc_only_no_suite: documentation-only changes skip the test suite.
    """
    reuse_when_equivalent: bool = True
    full_on_head_change: bool = True
    full_on_dependency_change: bool = True
    full_on_environment_change: bool = True
    doc_only_no_suite: bool = True

    def decide_scope(self, diff_reasons: List[Dict[str, str]],
                     affected_scopes) -> "VerificationScope":
        from .scope import VerificationScope
        reason_types = {d["reason"] for d in diff_reasons}
        if (self.full_on_head_change and "head_changed" in reason_types) or \
           (self.full_on_dependency_change and "dependency_changed" in reason_types) or \
           (self.full_on_environment_change and "environment_changed" in reason_types):
            return VerificationScope.FULL
        if not affected_scopes:
            return VerificationScope.DOCS
        if len(affected_scopes) == 1:
            return next(iter(affected_scopes))
        return VerificationScope.SUITE
