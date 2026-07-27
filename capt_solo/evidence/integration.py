"""Integration: VSI <-> Evidence (proof-preserving reuse).

Bridges Verified State Identity records into EvidenceRecords so that a verified
state can be reused as evidence without recomputation, and so that an invalidation
event can mark the corresponding verification record invalidated (not silently
reused).

This is the concrete wiring behind the decision flow:
  existing proof -> current state identity (VSI) -> invalidation scan
  -> no invalidator -> evidence remains current -> reuse without execution.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from .core import (
    EvidenceRecord, EvidenceClaim, EvidenceSource, EvidenceClass, EvidenceStatus,
    EvidenceScope,
)
from .invalidation import scan_invalidation, InvalidationReason
from .reuse import EvidenceReuseEngine, ReuseOutcome


def vsi_record_to_evidence(vsi_record: Dict, *, project_id: str = "capt-solo",
                           repository: str = "") -> EvidenceRecord:
    """Convert a stored VSI VerificationRecord dict into an EvidenceRecord.

    The evidence 'claim' is the verification outcome (e.g. 'suite passed for
    scope X at HEAD Y'). The source paths come from the VSI scoped file hashes.
    The evidence_status mirrors the VSI status (current vs invalidated).
    """
    vsi = vsi_record.get("vsi", {})
    scope = vsi.get("verification_scope", "full")
    head = vsi.get("head_commit", "")
    status = vsi_record.get("status", "verification_current")
    claim = EvidenceClaim(
        claim_id=f"vsi:{vsi_record.get('record_id', 'unknown')}",
        statement=f"verification {status} for scope={scope} at head={head}",
        claim_type="verification_outcome")
    src_paths = list(vsi.get("scope_file_hashes", {}).keys())
    src = EvidenceSource(
        source_type="verification_run", reference=vsi_record.get("evidence", {}).get("location", ""),
        repository=repository or vsi.get("repository", ""), project_id=project_id,
        branch=vsi.get("active_branch", ""), head_commit=head, source_paths=src_paths)
    ev_status = (EvidenceStatus.CURRENT.value if status in (
        "verification_current", "state_unchanged") else
        EvidenceStatus.INVALIDATED.value if status == "verification_invalidated" else
        EvidenceStatus.PARTIAL.value)
    rec = EvidenceRecord(
        record_id=f"ev-from-{vsi_record.get('record_id', 'unknown')}",
        claim=claim, evidence_class=EvidenceClass.VERIFICATION.value,
        source=src, status=ev_status, scope=EvidenceScope.PROJECT.value,
        project_id=project_id, repository_identity=repository or vsi.get("repository", ""),
        verification_record_id=vsi_record.get("record_id"),
        verification_scope=scope,
        provenance_chain=[f"vsi:{vsi_record.get('record_id')}"])
    return rec


def build_reuse_from_vsi(vsi_records: List[Dict], *, claim_id: str,
                         vsi_state: str, invalidation_reason: Optional[str] = None,
                         changed_paths: Optional[List[str]] = None,
                         project_id: str = "capt-solo", repository: str = "") -> Dict:
    """Build a guard decision from VSI records + current state.

    Converts VSI records to evidence, runs the reuse engine, returns the
    structured decision. This is the end-to-end proof-preserving reuse path.
    """
    evidence = [vsi_record_to_evidence(r, project_id=project_id, repository=repository)
                for r in vsi_records]
    eng = EvidenceReuseEngine(evidence)
    res = eng.decide(claim_id=claim_id, vsi_state=vsi_state,
                     invalidation_reason=invalidation_reason, changed_paths=changed_paths)
    return {
        "state_identity": res.decision.state_identity,
        "verification_status": res.decision.verification_status,
        "evidence_status": res.decision.evidence_status,
        "action": res.decision.action,
        "reason": res.decision.reason,
        "evidence_record_ids": res.decision.evidence_record_ids,
        "required_verification": res.required_verification,
    }


def invalidate_vsi_records(vsi_records: List[Dict], *, reason: str,
                           changed_paths: List[str]) -> Dict:
    """Scan invalidation against VSI-derived evidence and return affected record ids."""
    evidence = [vsi_record_to_evidence(r) for r in vsi_records]
    ev = scan_invalidation(reason, changed_paths, evidence)
    affected_records = [r_id.replace("ev-from-", "") for r_id in ev.affected_evidence_ids]
    return {
        "event_id": ev.event_id,
        "affected_vsi_records": affected_records,
        "unaffected_vsi_records": [r_id.replace("ev-from-", "")
                                   for r_id in ev.unaffected_evidence_ids],
        "invalidation_scope": ev.invalidation_scope,
    }
