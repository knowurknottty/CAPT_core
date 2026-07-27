"""Evidence Reuse Decision Engine — deterministic reuse vs re-verification.

Decision flow:
  existing proof -> current state identity (VSI) -> invalidation scan
  -> no invalidator found -> evidence remains current -> reuse without execution

Outputs (ReuseOutcome): REUSE_CURRENT_EVIDENCE, RUN_TARGETED_VERIFICATION,
RUN_DEPENDENCY_VERIFICATION, RUN_FULL_VERIFICATION, EVIDENCE_INSUFFICIENT,
EVIDENCE_CONFLICTED, BLOCKED.

Repeated execution against an identical state is NOT increased confidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .core import EvidenceDecision, EvidenceRecord, EvidenceStatus
from .invalidation import InvalidationEvent, scan_invalidation


class ReuseOutcome(str, Enum):
    REUSE_CURRENT_EVIDENCE = "reuse_current_evidence"
    RUN_TARGETED_VERIFICATION = "run_targeted_verification"
    RUN_DEPENDENCY_VERIFICATION = "run_dependency_verification"
    RUN_FULL_VERIFICATION = "run_full_verification"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    EVIDENCE_CONFLICTED = "evidence_conflicted"
    BLOCKED = "blocked"


@dataclass
class ReuseResult:
    outcome: ReuseOutcome
    decision: EvidenceDecision
    invalidation_event: Optional[InvalidationEvent] = None
    reused_evidence_ids: List[str] = field(default_factory=list)
    required_verification: List[str] = field(default_factory=list)


class EvidenceReuseEngine:
    def __init__(self, evidence: Optional[List[EvidenceRecord]] = None) -> None:
        self._evidence = list(evidence or [])

    def add(self, rec: EvidenceRecord) -> None:
        self._evidence.append(rec)

    def query(self, claim_id: str, scope: Optional[str] = None) -> List[EvidenceRecord]:
        out = [r for r in self._evidence if r.claim.claim_id == claim_id]
        if scope:
            out = [r for r in out if r.scope == scope]
        return out

    def decide(self, *,
               claim_id: str,
               vsi_state: str = "equivalent",   # equivalent | changed | unknown
               requested_scope: str = "targeted",
               invalidation_reason: Optional[str] = None,
               changed_paths: Optional[List[str]] = None,
               user_fresh: bool = False,
               policy: Optional[Dict] = None) -> ReuseResult:
        """Decide whether existing evidence can be reused.

        policy keys (optional): require_fresh_on_scope_expand (bool),
        allow_reuse_when_equivalent (bool, default True).
        """
        policy = policy or {}
        candidates = self.query(claim_id)
        current = [r for r in candidates if r.status == EvidenceStatus.CURRENT.value]

        # 1. Conflicted evidence -> EVIDENCE_CONFLICTED
        if any(r.status == EvidenceStatus.CONFLICTED.value for r in candidates):
            return self._result(ReuseOutcome.EVIDENCE_CONFLICTED, "equivalent",
                                "conflicted evidence present", [])

        # 2. No current evidence -> insufficient
        if not current:
            if vsi_state == "changed" or invalidation_reason:
                return self._result(ReuseOutcome.RUN_TARGETED_VERIFICATION, "changed",
                                    "no current evidence; state changed", [],
                                    event=None, changed_paths=changed_paths, required=["targeted"])
            return self._result(ReuseOutcome.EVIDENCE_INSUFFICIENT, vsi_state,
                                "no current evidence for claim", [])

        # 3. User explicitly requested fresh -> full (or targeted by scope)
        if user_fresh:
            return self._result(
                ReuseOutcome.RUN_FULL_VERIFICATION if requested_scope == "full"
                else ReuseOutcome.RUN_TARGETED_VERIFICATION,
                "changed", "user requested fresh verification", [],
                event=None, changed_paths=changed_paths,
                required=["full" if requested_scope == "full" else "targeted"])

        # 4. State changed -> scan invalidation
        if vsi_state == "changed" or invalidation_reason:
            reason = invalidation_reason or "working_tree_path_changed"
            event = scan_invalidation(reason, changed_paths or [], self._evidence)
            affected = set(event.affected_evidence_ids)
            # Are any CURRENT evidence for this claim affected?
            claim_current_ids = {r.record_id for r in current}
            if claim_current_ids & affected:
                # Determine required verification breadth from the event.
                if event.invalidation_scope == "full":
                    outcome = ReuseOutcome.RUN_FULL_VERIFICATION
                elif event.invalidation_scope == "transitive":
                    outcome = ReuseOutcome.RUN_DEPENDENCY_VERIFICATION
                else:
                    outcome = (ReuseOutcome.RUN_FULL_VERIFICATION
                               if "full" in event.required_verification
                               else ReuseOutcome.RUN_TARGETED_VERIFICATION)
                return self._result(outcome, "changed",
                                    f"invalidator {reason} affects claim evidence",
                                    [], event, changed_paths,
                                    event.required_verification or ["targeted"])
            # Claim evidence NOT affected -> reuse, but note unaffected remain current
            return self._result(ReuseOutcome.REUSE_CURRENT_EVIDENCE, "equivalent",
                                "state changed but claim evidence unaffected; reuse",
                                list(claim_current_ids))

        # 5. State equivalent and current evidence exists -> REUSE (no rerun)
        if vsi_state == "equivalent":
            if not policy.get("allow_reuse_when_equivalent", True):
                return self._result(ReuseOutcome.RUN_TARGETED_VERIFICATION, "equivalent",
                                    "policy disallows reuse", [])
            return self._result(ReuseOutcome.REUSE_CURRENT_EVIDENCE, "equivalent",
                                "No relevant state change detected; prior proof remains current",
                                [r.record_id for r in current])

        # 6. Unknown state -> conservative targeted
        return self._result(ReuseOutcome.RUN_TARGETED_VERIFICATION, "unknown",
                            "state identity unknown; run targeted", [])

    def _result(self, outcome: ReuseOutcome, state_identity: str, reason: str,
                reused: List[str], event: Optional[InvalidationEvent] = None,
                changed_paths: Optional[List[str]] = None,
                required: Optional[List[str]] = None) -> ReuseResult:
        decision = EvidenceDecision(
            state_identity=state_identity,
            verification_status="CURRENT" if outcome == ReuseOutcome.REUSE_CURRENT_EVIDENCE else "REQUIRED",
            evidence_status="CURRENT" if outcome == ReuseOutcome.REUSE_CURRENT_EVIDENCE else "INVALIDATED",
            invalidation_events=[event.__dict__] if event else [],
            action=outcome.value,
            reason=reason,
            evidence_record_ids=reused,
        )
        return ReuseResult(outcome=outcome, decision=decision,
                          invalidation_event=event, reused_evidence_ids=reused,
                          required_verification=required or [])
