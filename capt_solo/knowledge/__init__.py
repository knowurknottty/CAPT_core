"""Canonical Knowledge / Evidence / Trust / Proof / Governance convergence (Layer 3).

Phase 3G canonical package. Reuses the hardened MemoryEngine and ontology types
(I-12: no duplicate definitions). Existing canonical engines are re-exported and
bridged here so all five subsystems share one storage/interface foundation:

- Evidence  -> capt_solo.knowledge.evidence.EvidenceStore  (new, canonical)
- Knowledge -> capt_solo.knowledge.knowledge.KnowledgeStore (new, canonical)
- Trust     -> capt_solo.memory.trust (existing canonical trust engine)
- Proof     -> capt_solo.foundry.proof.ProofEngine (existing canonical proof engine)
- Governance-> capt_solo.foundry.governance.Governance (existing canonical governance)

Convergence properties (CANON):
- Evidence promotes claims; knowledge is never silently verified without
  corroborating evidence (I-02).
- Trust state is computed from explicit auditable inputs, never repetition
  (trust engine invariant).
- Proof aggregates are deterministic and reproducible (proof engine).
- Governance receipts are immutable and auditable (governance engine).
"""
from __future__ import annotations

from capt_solo.knowledge.evidence import (
    EvidenceRecord,
    EvidenceStore,
    VerificationStatus,
)
from capt_solo.knowledge.knowledge import (
    KnowledgeItem,
    KnowledgeStore,
    KnowledgeStatus,
)

__all__ = [
    "EvidenceStore",
    "EvidenceRecord",
    "VerificationStatus",
    "KnowledgeStore",
    "KnowledgeItem",
    "KnowledgeStatus",
]
