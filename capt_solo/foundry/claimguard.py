"""CAPT Solo v0.4 — ClaimGuard.

Before CAPT reports a completion-type claim (complete, fixed, migrated,
production-ready, tested, secure, verified, successful, ready), ClaimGuard
validates the supporting proof. Missing proof results in downgraded language.

Example:
    Instead of "Migration completed."
    Return "Migration implementation exists but verification evidence is incomplete."

ClaimGuard is integrated into plugin tools, CLI, verification, documentation
generation, and release reporting. It never fabricates confidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from capt_solo.foundry.registry import (
    CapabilityRegistry, PROOF_REQUIRED_CLAIMS, Capability,
)
from capt_solo.foundry.proof import ProofEngine


# Trigger words that, if used without proof, must be downgraded.
CLAIM_TRIGGERS = {
    "complete": "completion evidence (proof aggregate satisfied)",
    "completed": "completion evidence (proof aggregate satisfied)",
    "fixed": "fix verification evidence (passing test / procedure run)",
    "migrated": "migration verification evidence",
    "production-ready": "production-readiness evidence (integration + static analysis)",
    "tested": "test-pass evidence",
    "secure": "security review evidence",
    "verified": "verification proof (required evidence present)",
    "successful": "success evidence (procedure run / command output)",
    "ready": "readiness evidence",
}


@dataclass
class ClaimVerdict:
    """Result of validating a claim against the registry + proof engine."""

    claim: str
    supported: bool
    language: str          # the downgraded or approved statement
    missing: List[str] = field(default_factory=list)
    capability_id: Optional[str] = None
    lifecycle: Optional[str] = None
    evidence_count: int = 0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim, "supported": self.supported,
            "language": self.language, "missing": self.missing,
            "capability_id": self.capability_id, "lifecycle": self.lifecycle,
            "evidence_count": self.evidence_count, "reason": self.reason,
        }


class ClaimGuard:
    """Validates claims against the Capability Registry and Proof Engine."""

    def __init__(self, registry: CapabilityRegistry,
                 proof: Optional[ProofEngine] = None) -> None:
        self._reg = registry
        self._proof = proof

    def _detect_claim_word(self, text: str) -> Optional[str]:
        low = text.lower()
        for word in CLAIM_TRIGGERS:
            if re.search(r"\b" + re.escape(word) + r"\b", low):
                return word
        return None

    def verify_claim(self, text: str,
                     capability_id: Optional[str] = None) -> ClaimVerdict:
        """Validate a natural-language claim. Returns downgraded language if unsupported."""
        word = self._detect_claim_word(text)
        if word is None:
            # no proof-requiring claim word present — pass through
            return ClaimVerdict(claim=text, supported=True, language=text,
                                reason="no proof-required claim word detected")

        # resolve capability
        cap = None
        if capability_id:
            cap = self._reg.get(capability_id)
        if cap is None:
            cap = self._reg.query(text)
        if cap is None:
            # no registered capability at all — cannot support the claim
            missing = [CLAIM_TRIGGERS[word]]
            return ClaimVerdict(
                claim=text, supported=False,
                language=f"{text} — but NO registered capability matches; "
                         f"claim is UNSUPPORTED (no proof).",
                missing=missing, reason="no matching capability in registry")

        # capability exists; check lifecycle + proof
        if cap.lifecycle in ("revoked",):
            return ClaimVerdict(
                claim=text, supported=False,
                language=f"{text} — but capability '{cap.identifier}' is REVOKED; "
                         f"claim is UNSUPPORTED.",
                missing=["capability revoked"], capability_id=cap.identifier,
                lifecycle=cap.lifecycle, reason="capability revoked")

        if cap.lifecycle in ("deprecated",):
            return ClaimVerdict(
                claim=text, supported=False,
                language=f"{text} — but capability '{cap.identifier}' is DEPRECATED; "
                         f"claim is UNSUPPORTED.",
                missing=["capability deprecated"], capability_id=cap.identifier,
                lifecycle=cap.lifecycle, reason="capability deprecated")

        if cap.lifecycle == "verified":
            # verified: claim supported
            return ClaimVerdict(
                claim=text, supported=True, language=text,
                capability_id=cap.identifier, lifecycle=cap.lifecycle,
                evidence_count=len(cap.evidence),
                reason="capability verified with proof")

        # candidate / validated / experimental / degraded: proof incomplete
        missing = [CLAIM_TRIGGERS[word]]
        if self._proof is not None:
            agg = self._proof.aggregate(cap.identifier)
            for ur in agg.unsatisfied_requirements:
                missing.append(
                    f"{ur['type']} ({ur['have']}/{ur['min_count']})")
        lifecycle_note = {
            "candidate": "implementation exists but verification evidence is incomplete",
            "validated": "validated but not yet verified (proof aggregate unsatisfied)",
            "experimental": "experimental; proof not yet established",
            "degraded": self._degradation_note(cap),
        }.get(cap.lifecycle, "verification evidence is incomplete")
        return ClaimVerdict(
            claim=text, supported=False,
            language=f"{text} — but {lifecycle_note}.",
            missing=missing, capability_id=cap.identifier,
            lifecycle=cap.lifecycle,
            evidence_count=len(cap.evidence),
            reason=f"capability lifecycle={cap.lifecycle}; proof incomplete")

    def _degradation_note(self, cap) -> str:
        """Scoped, reason-aware degradation language.

        A capability degraded ONLY on a specific platform (e.g. macOS) must
        NOT be reported as globally revoked. The latest degradation record
        (if available) drives the wording.
        """
        recs = []
        if self._reg is not None and hasattr(self._reg, "get_degradations"):
            try:
                recs = self._reg.get_degradations(cap.identifier)
            except Exception:
                recs = []
        if recs:
            latest = recs[0]
            reason = latest.get("reason", "unknown")
            scope = latest.get("affected_scope", "global")
            expl = latest.get("explanation", "")
            if scope and scope != "global":
                return (f"degraded on {scope} only (reason: {reason}); "
                        f"not globally revoked — {expl}")
            return f"degraded (reason: {reason}) — {expl}"
        # no structured record: fall back to generic scoped language
        if getattr(cap, "degradation_state", "none") not in ("none", ""):
            return (f"previously verified but now degraded "
                    f"(state={cap.degradation_state})")
        return "previously verified but now degraded (evidence stale/revoked)"

    def assert_capability(self, identifier: str) -> ClaimVerdict:
        """Explicit 'can CAPT do X?' query. Never answers yes without registry proof."""
        cap = self._reg.get(identifier)
        if cap is None:
            return ClaimVerdict(
                claim=f"capability:{identifier}", supported=False,
                language=f"CAPT cannot confirm capability '{identifier}': "
                         f"not registered in the Capability Registry.",
                missing=["capability not registered"],
                reason="no registry entry")
        if cap.lifecycle == "verified":
            return ClaimVerdict(
                claim=f"capability:{identifier}", supported=True,
                language=f"CAPT can perform '{identifier}' (verified).",
                capability_id=identifier, lifecycle="verified",
                evidence_count=len(cap.evidence),
                reason="verified capability")
        note = {
            "candidate": "registered but not yet validated",
            "validated": "validated but proof requirements not yet satisfied",
            "proven": "proof requirements satisfied but not yet governance-approved",
            "experimental": "experimental",
            "degraded": "degraded (evidence incomplete/stale)",
            "deprecated": "deprecated",
            "revoked": "revoked",
        }.get(cap.lifecycle, "unknown state")
        return ClaimVerdict(
            claim=f"capability:{identifier}", supported=False,
            language=f"CAPT cannot confirm '{identifier}' as ready: {note}.",
            missing=[f"lifecycle={cap.lifecycle}"],
            capability_id=identifier, lifecycle=cap.lifecycle,
            reason=f"capability lifecycle={cap.lifecycle}")
