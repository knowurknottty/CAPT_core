"""Self-Modification Governance — governed agent changes to skills/policies.

Any agent modification to system skills, operating procedures, prompts, policies,
verification rules, memory rules, or agent defaults is a governed code change.

Lifecycle: PROPOSED -> QUARANTINED -> APPROVED -> APPLIED -> VERIFIED -> REJECTED
-> ROLLED_BACK.

Rules (from mission):
1. Do not silently mutate operating policy.
2. Preserve an inspectable diff.
3. Record why the change was made.
4. Verify new rule does not contradict higher-priority governance.
5. Avoid recursive self-modification loops.
6. Limit self-modifications per mission.
7. Require explicit approval for high-impact/global policy changes.
8. Permit low-risk project-local procedure improvements only when policy allows.
9. Provide a rollback mechanism.
10. Never interpret successful self-editing as proof of improved behavior.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class SelfModState(str, Enum):
    PROPOSED = "proposed"
    QUARANTINED = "quarantined"
    APPROVED = "approved"
    APPLIED = "applied"
    VERIFIED = "verified"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class SelfModError(Exception):
    pass


# Maximum self-modifications per mission (anti-loop guard, rule 6).
MAX_SELF_MODS_PER_MISSION = 10


@dataclass
class SelfModificationRecord:
    record_id: str
    proposed_change: str
    rationale: str
    triggering_evidence: str
    original_behavior: str
    expected_improvement: str
    risk_analysis: str
    affected_scope: str            # project_local | global_policy | skill | prompt
    diff: str
    tests_or_validation: str
    rollback_path: str
    approval_requirement: str      # none | project_local | global_approval
    status: str = SelfModState.PROPOSED.value
    prior_content_hash: Optional[str] = None
    applied_content_hash: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return self.__dict__


class SelfModificationGovernor:
    def __init__(self, mission_id: str = "default", max_mods: int = MAX_SELF_MODS_PER_MISSION) -> None:
        self._mission_id = mission_id
        self._records: List[SelfModificationRecord] = []
        self._max_mods = max_mods
        self._applied_count = 0

    def propose(self, *, proposed_change: str, rationale: str, triggering_evidence: str,
                original_behavior: str, expected_improvement: str, risk_analysis: str,
                affected_scope: str, diff: str, tests_or_validation: str,
                rollback_path: str, approval_requirement: str = "project_local",
                prior_content: Optional[str] = None) -> SelfModificationRecord:
        # Deduplicate identical proposals (anti-loop, rule 5/6).
        for r in self._records:
            if (r.proposed_change == proposed_change and r.diff == diff
                    and r.affected_scope == affected_scope and r.status in (
                        SelfModState.PROPOSED.value, SelfModState.QUARANTINED.value,
                        SelfModState.APPROVED.value, SelfModState.APPLIED.value)):
                return r  # return existing; do not create duplicate
        # Limit count (anti-loop rule 6).
        if len([r for r in self._records]) >= self._max_mods:
            raise SelfModError(f"self-modification limit ({self._max_mods}) reached for mission")
        rec = SelfModificationRecord(
            record_id=f"sm-{uuid.uuid4().hex[:12]}",
            proposed_change=proposed_change, rationale=rationale,
            triggering_evidence=triggering_evidence, original_behavior=original_behavior,
            expected_improvement=expected_improvement, risk_analysis=risk_analysis,
            affected_scope=affected_scope, diff=diff,
            tests_or_validation=tests_or_validation, rollback_path=rollback_path,
            approval_requirement=approval_requirement,
            prior_content_hash=(hashlib.sha256(prior_content.encode()).hexdigest()[:16]
                                if prior_content else None))
        # Low-risk project-local go to APPROVED if policy allows; global requires quarantine.
        if affected_scope == "global_policy" or approval_requirement == "global_approval":
            rec.status = SelfModState.QUARANTINED.value
        else:
            rec.status = SelfModState.PROPOSED.value
        self._records.append(rec)
        return rec

    def approve(self, record_id: str, *, approved_by: str = "user") -> SelfModificationRecord:
        rec = self._find(record_id)
        if rec.status in (SelfModState.REJECTED.value, SelfModState.ROLLED_BACK.value):
            raise SelfModError("cannot approve a rejected/rolled-back record")
        if rec.affected_scope == "global_policy" or rec.approval_requirement == "global_approval":
            if approved_by in (None, "", "self"):
                raise SelfModError("global policy change requires explicit external approval")
        rec.status = SelfModState.APPROVED.value
        return rec

    def apply(self, record_id: str) -> SelfModificationRecord:
        rec = self._find(record_id)
        if rec.status != SelfModState.APPROVED.value:
            raise SelfModError("only APPROVED records may be applied")
        # Inspectable diff must be present (rule 2).
        if not rec.diff.strip():
            raise SelfModError("no inspectable diff; refusing to apply")
        rec.status = SelfModState.APPLIED.value
        self._applied_count += 1
        return rec

    def verify(self, record_id: str, *, verified: bool, notes: str = "") -> SelfModificationRecord:
        rec = self._find(record_id)
        if rec.status != SelfModState.APPLIED.value:
            raise SelfModError("only APPLIED records may be verified")
        rec.status = SelfModState.VERIFIED.value if verified else SelfModState.QUARANTINED.value
        if not verified:
            rec.risk_analysis += f"; verification failed: {notes}"
        return rec

    def reject(self, record_id: str, *, reason: str = "") -> SelfModificationRecord:
        rec = self._find(record_id)
        rec.status = SelfModState.REJECTED.value
        rec.risk_analysis += f"; rejected: {reason}"
        return rec

    def rollback(self, record_id: str) -> SelfModificationRecord:
        rec = self._find(record_id)
        if not rec.rollback_path:
            raise SelfModError("no rollback path recorded")
        rec.status = SelfModState.ROLLED_BACK.value
        return rec

    def _find(self, record_id: str) -> SelfModificationRecord:
        for r in self._records:
            if r.record_id == record_id:
                return r
        raise SelfModError(f"record not found: {record_id}")

    def records(self) -> List[SelfModificationRecord]:
        return list(self._records)

    def dedupe_count(self) -> int:
        return len(self._records)
