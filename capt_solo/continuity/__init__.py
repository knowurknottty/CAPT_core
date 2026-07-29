"""Constitutional Verification Envelope (CVE) v0.2 continuity runtime.

The runtime is deliberately local and declarative.  It evaluates supplied
evidence; it never manufactures approvals, signatures, recovery drills, or
production access.
"""

from .runtime import (
    ContinuityError, ContinuityTier, EvaluationStatus, ContinuityPack,
    ContinuityEvidence, ContinuityReceipt, HandoffState, load_policy,
    validate_pack, evaluate_pack, verify_receipt, plan_drill,
)

__all__ = [
    "ContinuityError", "ContinuityTier", "EvaluationStatus", "ContinuityPack",
    "ContinuityEvidence", "ContinuityReceipt", "HandoffState", "load_policy",
    "validate_pack", "evaluate_pack", "verify_receipt", "plan_drill",
]
