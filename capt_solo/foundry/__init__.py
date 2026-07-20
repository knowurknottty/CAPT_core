"""CAPT Solo v0.4 — Foundry package.

Public surface for the proof-governed cognitive operating system:
Skill Foundry, Proof Engine, ClaimGuard, Capability Registry, Knowledge
Bubbles, Validation Harness, Skill Curator, Composition Engine, Governance.

All consequential actions are CTP-bounded and audited. No module here
bypasses provenance, trust, or transaction auditing.
"""

from capt_solo.foundry.proof import (
    ProofEngine, ProofRequirement, Evidence, ProofAggregate, sha256_of,
    KNOWN_EVIDENCE_TYPES, DEFAULT_EVIDENCE_TTL,
)
from capt_solo.foundry.registry import (
    CapabilityRegistry, Capability, CAPABILITY_LIFECYCLE,
    DEGRADATION_REASONS, PROOF_REQUIRED_CLAIMS,
)
from capt_solo.foundry.claimguard import (
    ClaimGuard, ClaimVerdict, CLAIM_TRIGGERS,
)
from capt_solo.foundry.skill_foundry import (
    SkillFoundry, Skill, SKILL_LIFECYCLE, _bump_version,
)
from capt_solo.foundry.harness import (
    ValidationHarness, ValidationReport, StageResult, REQUIRED_STAGES,
    ALLOWED_PERMISSIONS,
)
from capt_solo.foundry.curator import SkillCurator, CurationFinding
from capt_solo.foundry.composition import (
    CompositionEngine, CompositeWorkflow, CompositionStep,
)
from capt_solo.foundry.workflow_proof import (
    WorkflowProofEngine, WorkflowProof, WORKFLOW_LIFECYCLE,
)
from capt_solo.foundry.bubble import (
    KnowledgeBubbleRuntime, BubbleValidationReport, BUBBLE_LIFECYCLE,
    BUBBLE_FORMAT,
)
from capt_solo.foundry.governance import Governance, GovernanceReceipt
from capt_solo.foundry.columns import (
    decode_list, decode_dict, decode_list_safe, decode_dict_safe,
    ColumnDecodeError,
)

__all__ = [
    "ProofEngine", "ProofRequirement", "Evidence", "ProofAggregate", "sha256_of",
    "KNOWN_EVIDENCE_TYPES", "DEFAULT_EVIDENCE_TTL",
    "CapabilityRegistry", "Capability", "CAPABILITY_LIFECYCLE",
    "DEGRADATION_REASONS", "PROOF_REQUIRED_CLAIMS",
    "ClaimGuard", "ClaimVerdict", "CLAIM_TRIGGERS",
    "SkillFoundry", "Skill", "SKILL_LIFECYCLE", "_bump_version",
    "ValidationHarness", "ValidationReport", "StageResult", "REQUIRED_STAGES",
    "ALLOWED_PERMISSIONS",
    "SkillCurator", "CurationFinding",
    "CompositionEngine", "CompositeWorkflow", "CompositionStep",
    "WorkflowProofEngine", "WorkflowProof", "WORKFLOW_LIFECYCLE",
    "KnowledgeBubbleRuntime", "BubbleValidationReport", "BUBBLE_LIFECYCLE",
    "BUBBLE_FORMAT",
    "Governance", "GovernanceReceipt",
    "decode_list", "decode_dict", "decode_list_safe", "decode_dict_safe",
    "ColumnDecodeError",
]
