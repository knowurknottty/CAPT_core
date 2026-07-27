"""CAPT Invention Engine — structured engineering reasoning on math+physics.

Builds on capt_solo.engines.mathematics and .physics. NOT an LLM-only wrapper or
generate_idea(prompt). Uses explicit structured artifacts across a 17-step
workflow, with feasibility scoring (explainable components), constraint tracking,
contradiction detection, safety gates, evidence references, revision history,
provenance, and exportable reports.

Artifact maturity ladder (explicit, never auto-promoted by detail alone):
  idea < hypothesis < conceptual_design < calculated_design < simulated_design
  < prototype < validated_prototype < production_ready

No patentability claims are made. Prior-art interfaces are stubs (no patent
search performed unless explicitly wired to a source).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from capt_solo.engines.mathematics import Number, Quantity, DerivationTrace
from capt_solo.engines.physics import PhysicsResult, PhysicsError


class ArtifactStage(Enum):
    IDEA = "idea"
    HYPOTHESIS = "hypothesis"
    CONCEPTUAL_DESIGN = "conceptual_design"
    CALCULATED_DESIGN = "calculated_design"
    SIMULATED_DESIGN = "simulated_design"
    PROTOTYPE = "prototype"
    VALIDATED_PROTOTYPE = "validated_prototype"
    PRODUCTION_READY = "production_ready"

    def __lt__(self, other: "ArtifactStage") -> bool:
        return _stage_index(self) < _stage_index(other)


_STAGE_ORDER = list(ArtifactStage)


def _stage_index(stage: ArtifactStage) -> int:
    return _STAGE_ORDER.index(stage)


class SafetyGate(Enum):
    PASS = "pass"
    REVIEW = "review"
    BLOCK = "block"


@dataclass
class FeasibilityComponent:
    """One explainable component of a feasibility score (0..1)."""
    name: str
    score: float
    weight: float
    rationale: str

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"component score must be in [0,1], got {self.score}")
        if self.weight < 0:
            raise ValueError("weight must be non-negative")


@dataclass
class Revision:
    revision_id: str
    timestamp: str
    summary: str
    prior_stage: Optional[ArtifactStage]
    new_stage: Optional[ArtifactStage]


@dataclass
class InventionRecord:
    """A structured invention artifact with full provenance."""
    problem: str
    constraints: List[str] = field(default_factory=list)
    existing_approaches: List[str] = field(default_factory=list)
    functional_decomposition: List[str] = field(default_factory=list)
    candidate_principles: List[str] = field(default_factory=list)
    candidate_mechanisms: List[str] = field(default_factory=list)
    candidate_architectures: List[str] = field(default_factory=list)
    calculations: List[Dict[str, Any]] = field(default_factory=list)
    physical_feasibility: List[str] = field(default_factory=list)
    tradeoffs: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    safety_analysis: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    manufacturing: List[str] = field(default_factory=list)
    testable_hypotheses: List[str] = field(default_factory=list)
    prototype_plan: List[str] = field(default_factory=list)
    validation_criteria: List[str] = field(default_factory=list)
    failure_analysis: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    uncertainty: List[str] = field(default_factory=list)
    revisions: List[Revision] = field(default_factory=list)
    stage: ArtifactStage = ArtifactStage.IDEA
    feasibility: List[FeasibilityComponent] = field(default_factory=list)
    safety_gate: SafetyGate = SafetyGate.PASS
    provenance: Optional[str] = None
    trace: Optional[DerivationTrace] = None

    def add_revision(self, revision: Revision) -> None:
        self.revisions.append(revision)
        if revision.new_stage is not None:
            self.stage = revision.new_stage

    def feasibility_score(self) -> float:
        """Weighted mean of component scores; 0.0 if no components."""
        if not self.feasibility:
            return 0.0
        total_w = sum(c.weight for c in self.feasibility)
        if total_w == 0:
            return sum(c.score for c in self.feasibility) / len(self.feasibility)
        return sum(c.score * c.weight for c in self.feasibility) / total_w

    def detect_contradictions(self) -> List[str]:
        """Lightweight contradiction detection: flags empty required sections
        relative to the current stage, and explicit contradiction notes."""
        found = list(self.contradictions)
        if _stage_index(self.stage) >= _stage_index(ArtifactStage.CALCULATED_DESIGN) and not self.calculations:
            found.append("stage requires calculations but none recorded")
        if _stage_index(self.stage) >= _stage_index(ArtifactStage.PROTOTYPE) and not self.prototype_plan:
            found.append("stage requires prototype plan but none recorded")
        if _stage_index(self.stage) >= _stage_index(ArtifactStage.VALIDATED_PROTOTYPE) and not self.validation_criteria:
            found.append("validated stage requires validation criteria")
        return found

    def evaluate_safety(self) -> SafetyGate:
        """Safety gate: any BLOCK-level keyword escalates; otherwise REVIEW if
        open safety items remain; else PASS."""
        block_words = ("lethal", "weapon", "explosive", "bioweapon", "uncontained release")
        for item in self.safety_analysis + self.failure_analysis:
            low = item.lower()
            if any(w in low for w in block_words):
                self.safety_gate = SafetyGate.BLOCK
                return self.safety_gate
        if not self.safety_analysis:
            self.safety_gate = SafetyGate.REVIEW
        else:
            self.safety_gate = SafetyGate.PASS
        return self.safety_gate

    def export_report(self) -> str:
        """Export a human-readable report (no patentability claims)."""
        lines = [
            f"# Invention Record",
            f"Stage: {self.stage.value}",
            f"Problem: {self.problem}",
            f"Feasibility: {self.feasibility_score():.3f}",
            f"Safety gate: {self.safety_gate.value}",
            "",
            "## Constraints",
            *[f"- {c}" for c in self.constraints],
            "## Functional decomposition",
            *[f"- {f}" for f in self.functional_decomposition],
            "## Candidate principles",
            *[f"- {p}" for p in self.candidate_principles],
            "## Candidate mechanisms",
            *[f"- {m}" for m in self.candidate_mechanisms],
            "## Candidate architectures",
            *[f"- {a}" for a in self.candidate_architectures],
            "## Calculations",
            *[f"- {c}" for c in self.calculations],
            "## Physical feasibility",
            *[f"- {p}" for p in self.physical_feasibility],
            "## Tradeoffs",
            *[f"- {t}" for t in self.tradeoffs],
            "## Contradictions",
            *[f"- {c}" for c in self.detect_contradictions()],
            "## Safety analysis",
            *[f"- {s}" for s in self.safety_analysis],
            "## Materials",
            *[f"- {m}" for m in self.materials],
            "## Manufacturing",
            *[f"- {m}" for m in self.manufacturing],
            "## Validation criteria",
            *[f"- {v}" for v in self.validation_criteria],
            "## Failure analysis",
            *[f"- {f}" for f in self.failure_analysis],
            "## Evidence",
            *[f"- {e}" for e in self.evidence],
            "## Uncertainty",
            *[f"- {u}" for u in self.uncertainty],
            "## Revisions",
            *[f"- {r.revision_id}: {r.summary} ({r.prior_stage} -> {r.new_stage})"
              for r in self.revisions],
            "",
            "NOTE: This record makes no patentability claim. Prior-art search is",
            "not performed unless explicitly wired to a source.",
        ]
        return "\n".join(lines)


class InventionEngine:
    """Structured invention reasoning on top of math + physics."""

    def new_record(self, problem: str) -> InventionRecord:
        return InventionRecord(problem=problem, provenance="capt_solo.engines.invention")

    def add_calculation(self, rec: InventionRecord, label: str, result: Any,
                        source: str = "") -> None:
        """Attach a calculation result (Quantity, PhysicsResult, or Number).
        Integrates directly with math/physics outputs — no re-derivation."""
        if isinstance(result, PhysicsResult):
            value = result.quantity.as_float()
            dim = str(result.quantity.dimension)
            rel = result.relation
        elif isinstance(result, Quantity):
            value = result.as_float()
            dim = str(result.dimension)
            rel = "quantity"
        elif isinstance(result, Number):
            value = result.as_float()
            dim = "dimensionless"
            rel = "number"
        else:
            value = result
            dim = "unknown"
            rel = "raw"
        rec.calculations.append({
            "label": label, "value": value, "dimension": dim,
            "relation": rel, "source": source,
        })

    def assess_feasibility(self, rec: InventionRecord,
                           components: List[FeasibilityComponent]) -> float:
        rec.feasibility = components
        return rec.feasibility_score()

    def finalize(self, rec: InventionRecord) -> InventionRecord:
        """Run contradiction detection + safety gate; do not auto-promote stage."""
        rec.detect_contradictions()
        rec.evaluate_safety()
        return rec
