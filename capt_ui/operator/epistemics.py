"""Truthful epistemic-state projections for CAPT operator surfaces.

This module consumes authoritative/read-model claim and verification data and
produces presentation labels. It never mutates runtime state and never treats a
verification or ClaimGuard decision as universal truth.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


_KNOWN_VERIFICATION_KINDS = {
    "verified",
    "contradicted",
    "observed_unverified",
    "inference",
    "inconclusive",
    "not_tested",
    "failed",
}


def _verification_kind(verification: Mapping[str, Any], claim: Mapping[str, Any]) -> Optional[str]:
    status = verification.get("status")
    if isinstance(status, Mapping):
        kind = status.get("kind")
        if kind:
            return str(kind)
    if isinstance(status, str) and status:
        return status
    value = claim.get("verificationStatus")
    return str(value) if value else None


def _verification_domain(verification: Mapping[str, Any]) -> str:
    for key in ("domain", "verificationDomain", "domainId"):
        value = verification.get(key)
        if value:
            return str(value)
    status = verification.get("status")
    if isinstance(status, Mapping):
        for key in ("domain", "verificationDomain"):
            value = status.get(key)
            if value:
                return str(value)
    return "unspecified"


def project_claim_epistemic_state(
    claim: Mapping[str, Any],
    verification: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Project one claim into ordered, semantically narrow state labels."""
    verification = verification or {}
    stages: List[str] = []

    promotion = str(claim.get("promotionState") or "proposed")
    evidence_ids = list(claim.get("evidenceIds") or [])
    kind = _verification_kind(verification, claim)
    domain = _verification_domain(verification)

    stages.append("CLAIM_PROPOSED")
    if evidence_ids:
        stages.append("EVIDENCE_RECORDED")

    if kind:
        if kind == "verified":
            stages.append("VERIFIED:%s" % domain)
        elif kind == "contradicted":
            stages.append("CONTRADICTED:%s" % domain)
        elif kind == "observed_unverified":
            stages.append("OBSERVED_UNVERIFIED:%s" % domain)
        elif kind == "inference":
            stages.append("INFERENCE:%s" % domain)
        elif kind == "inconclusive":
            stages.append("INCONCLUSIVE:%s" % domain)
        elif kind == "not_tested":
            stages.append("NOT_TESTED:%s" % domain)
        elif kind == "failed":
            stages.append("VERIFICATION_FAILED:%s" % domain)
        else:
            stages.append("VERIFICATION_STATUS:%s:%s" % (kind.upper(), domain))

    terminal_label = {
        "accepted": "CLAIM_ACCEPTED",
        "rejected": "CLAIM_REJECTED",
        "qualified": "CLAIM_QUALIFIED",
        "escalated": "CLAIM_ESCALATED",
        "suppressed": "CLAIM_SUPPRESSED",
        "verified": "CLAIM_VERIFIED_PENDING_DECISION",
        "proposed": "CLAIM_PENDING",
    }.get(promotion, "CLAIM_STATE:%s" % promotion.upper())
    stages.append(terminal_label)

    freshness = verification.get("freshness")
    stale = verification.get("stale")
    if stale is True or str(freshness).lower() == "stale":
        stages.append("STALE")

    committed = verification.get("committed")
    advisory = verification.get("advisory")
    if committed is True:
        provenance_class = "COMMITTED_VERIFICATION"
    elif advisory is True:
        provenance_class = "ADVISORY_VERIFICATION"
    else:
        provenance_class = "VERIFICATION_PROVENANCE_UNKNOWN"

    return {
        "claimId": str(claim.get("claimId") or ""),
        "statement": str(claim.get("statement") or ""),
        "promotionState": promotion,
        "evidenceCount": len(evidence_ids),
        "verificationStatus": kind or "unknown",
        "verificationDomain": domain,
        "verificationProvenance": provenance_class,
        "stages": stages,
        "acceptedIsUniversalTruth": False,
    }


def project_epistemic_ladder(
    claims: Iterable[Mapping[str, Any]],
    verifications_by_claim: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Project all claims without inventing a global scalar certainty state."""
    by_claim = verifications_by_claim or {}
    out: List[Dict[str, Any]] = []
    for claim in claims:
        claim_id = str(claim.get("claimId") or "")
        out.append(project_claim_epistemic_state(claim, by_claim.get(claim_id, {})))
    return out
