"""Guard Integration — structured evidence decision contract.

A runtime guard should not merely demand "fresh verification". It should evaluate
a structured decision:

{
  "state_identity": "equivalent",
  "verification_status": "CURRENT",
  "evidence_status": "CURRENT",
  "invalidation_events": [],
  "action": "REUSE_CURRENT_EVIDENCE",
  "reason": "No relevant state change detected"
}

This module builds that contract from the VSI + EvidenceReuseEngine, so a guard
can consume it and avoid verification loops when the verified state is unchanged.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .core import EvidenceDecision
from .reuse import EvidenceReuseEngine, ReuseOutcome
from .invalidation import scan_invalidation, InvalidationReason


def build_guard_decision(*,
                         claim_id: str,
                         vsi_state: str,
                         evidence: List,
                         invalidation_reason: Optional[str] = None,
                         changed_paths: Optional[List[str]] = None,
                         user_fresh: bool = False,
                         requested_scope: str = "targeted") -> Dict:
    """Produce the structured guard decision.

    `evidence` is a list of EvidenceRecord. Returns a JSON-serializable dict
    matching the contract above.
    """
    eng = EvidenceReuseEngine(evidence)
    res = eng.decide(claim_id=claim_id, vsi_state=vsi_state,
                     requested_scope=requested_scope,
                     invalidation_reason=invalidation_reason,
                     changed_paths=changed_paths, user_fresh=user_fresh)
    d: EvidenceDecision = res.decision
    return {
        "state_identity": d.state_identity,
        "verification_status": d.verification_status,
        "evidence_status": d.evidence_status,
        "invalidation_events": d.invalidation_events,
        "action": d.action,
        "reason": d.reason,
        "evidence_record_ids": d.evidence_record_ids,
        "required_verification": res.required_verification,
    }


# Convenience: the canonical "unchanged state" decision a guard can return
# without recomputation.
def reuse_decision(claim_id: str, evidence_record_ids: List[str]) -> Dict:
    return {
        "state_identity": "equivalent",
        "verification_status": "CURRENT",
        "evidence_status": "CURRENT",
        "invalidation_events": [],
        "action": ReuseOutcome.REUSE_CURRENT_EVIDENCE.value,
        "reason": "No relevant state change detected",
        "evidence_record_ids": evidence_record_ids,
        "required_verification": [],
    }
