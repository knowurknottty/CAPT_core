"""CAPT Verified State Identity (VSI) — reusable verification-state subsystem.

Verification is attached to the STATE being verified, not to the age of the
conversation. A verification result stays valid while the Verified State Identity
(VSI) remains equivalent. Conversation turns do not invalidate verification.

Public surface:
- VerifiedStateIdentity, build_vsi
- VerificationScope, map_paths_to_scopes, select_scope_for_changes
- VerificationStatus, VerificationRecord, VerificationEvidence, VerificationPolicy
- VerificationStore, VerificationEngine
"""
from __future__ import annotations

from .identity import VerifiedStateIdentity, build_vsi, vsi_equivalent, diff_vsi, VsiDiffReason
from .scope import (
    VerificationScope, SCOPE_PATH_GLOBS, map_paths_to_scopes,
    select_scope_for_changes,
)
from .record import (
    VerificationStatus, VerificationRecord, VerificationEvidence, VerificationPolicy,
)
from .store import VerificationStore
from .engine import VerificationEngine

__all__ = [
    "VerifiedStateIdentity", "build_vsi", "vsi_equivalent", "diff_vsi", "VsiDiffReason",
    "VerificationScope", "SCOPE_PATH_GLOBS", "map_paths_to_scopes", "select_scope_for_changes",
    "VerificationStatus", "VerificationRecord", "VerificationEvidence", "VerificationPolicy",
    "VerificationStore", "VerificationEngine",
]
