"""CAPT-native Explore -> Converge -> Enhance -> Handoff planning contracts.

The council reasons; CAPT freezes the contract. This module is intentionally
effect-free so planning can be digested and verified before a coding model is
granted write authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .contracts import digest

SCHEMA_VERSION = "capt-moa-planning-r1"


class PlanningValidationError(ValueError):
    """The MoA planning bundle violates a handoff invariant."""


class Decision(str, Enum):
    ACCEPT = "accept"
    REVISE = "revise"
    REJECT = "reject"
    DEFER = "defer"


class EnhancementKind(str, Enum):
    ENHANCEMENT = "enhancement"
    UPGRADE = "upgrade"
    NOVEL = "novel"


@dataclass(frozen=True)
class ExploreFinding:
    finding_id: str
    source_id: str
    model_id: str
    summary: str
    weaknesses: tuple[str, ...]
    candidate_solutions: tuple[str, ...]
    risks: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConvergenceDecision:
    decision_id: str
    topic: str
    disposition: Decision
    rationale: str
    source_finding_ids: tuple[str, ...]
    dissent_finding_ids: tuple[str, ...] = ()
    required_changes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnhancementProposal:
    proposal_id: str
    kind: EnhancementKind
    title: str
    value: str
    risk: str
    dependencies: tuple[str, ...]
    rationale: str
    source_finding_ids: tuple[str, ...]
    disposition: Decision = Decision.DEFER


@dataclass(frozen=True)
class ImplementationContract:
    contract_id: str
    objective: str
    source_state_digest: str
    exact_files: tuple[str, ...]
    components: tuple[str, ...]
    schemas_apis: tuple[str, ...]
    invariants: tuple[str, ...]
    migration_rules: tuple[str, ...]
    tests_golden_vectors: tuple[str, ...]
    prohibited_changes: tuple[str, ...]
    rollback_strategy: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    verification_gates: tuple[str, ...]
    accepted_decision_ids: tuple[str, ...]
    dissent_summary: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanningBundle:
    council_id: str
    explore_findings: tuple[ExploreFinding, ...]
    convergence_decisions: tuple[ConvergenceDecision, ...]
    implementation_contract: ImplementationContract
    enhancements: tuple[EnhancementProposal, ...] = ()


def _required(label: str, value: str) -> None:
    if not value or not value.strip():
        raise PlanningValidationError(f"{label.upper()}_REQUIRED")


def _required_tuple(label: str, values: Iterable[str]) -> None:
    cleaned = tuple(value for value in values if value and value.strip())
    if not cleaned:
        raise PlanningValidationError(f"{label.upper()}_REQUIRED")


def validate_bundle(bundle: PlanningBundle) -> None:
    _required("council_id", bundle.council_id)
    if not bundle.explore_findings:
        raise PlanningValidationError("EXPLORE_FINDINGS_REQUIRED")
    if not bundle.convergence_decisions:
        raise PlanningValidationError("CONVERGENCE_DECISIONS_REQUIRED")


    finding_ids: set[str] = set()
    source_ids: set[str] = set()
    for finding in bundle.explore_findings:
        _required("finding_id", finding.finding_id)
        _required("source_id", finding.source_id)
        _required("model_id", finding.model_id)
        _required("summary", finding.summary)
        _required_tuple("weaknesses", finding.weaknesses)
        _required_tuple("candidate_solutions", finding.candidate_solutions)
        _required_tuple("risks", finding.risks)
        if finding.finding_id in finding_ids:
            raise PlanningValidationError("DUPLICATE_FINDING_ID")
        finding_ids.add(finding.finding_id)
        source_ids.add(finding.source_id)

    if len(source_ids) < 2:
        raise PlanningValidationError("INDEPENDENT_SOURCES_REQUIRED")

    decision_ids: set[str] = set()
    for decision in bundle.convergence_decisions:
        _required("decision_id", decision.decision_id)
        _required("topic", decision.topic)
        _required("rationale", decision.rationale)
        if decision.decision_id in decision_ids:
            raise PlanningValidationError("DUPLICATE_DECISION_ID")
        decision_ids.add(decision.decision_id)

        unknown = (
            set(decision.source_finding_ids) | set(decision.dissent_finding_ids)
        ) - finding_ids
        if unknown:
            raise PlanningValidationError("UNKNOWN_FINDING_REFERENCE")

    contract = bundle.implementation_contract
    _required("contract_id", contract.contract_id)
    _required("objective", contract.objective)
    if not contract.source_state_digest.startswith("sha256:"):
        raise PlanningValidationError("SOURCE_STATE_DIGEST_REQUIRED")
    for label, values in (
        ("exact_files", contract.exact_files),
        ("components", contract.components),
        ("invariants", contract.invariants),
        ("tests_golden_vectors", contract.tests_golden_vectors),
        ("prohibited_changes", contract.prohibited_changes),
        ("rollback_strategy", contract.rollback_strategy),
        ("verification_gates", contract.verification_gates),
    ):
        _required_tuple(label, values)

    if set(contract.accepted_decision_ids) - decision_ids:
        raise PlanningValidationError("UNKNOWN_ACCEPTED_DECISION")


    for proposal in bundle.enhancements:
        _required("proposal_id", proposal.proposal_id)
        _required("title", proposal.title)
        _required("value", proposal.value)
        _required("risk", proposal.risk)
        _required("rationale", proposal.rationale)
        if set(proposal.source_finding_ids) - finding_ids:
            raise PlanningValidationError("UNKNOWN_ENHANCEMENT_FINDING")


def _finding_dict(value: ExploreFinding) -> dict[str, object]:
    return {
        "findingId": value.finding_id,
        "sourceId": value.source_id,
        "modelId": value.model_id,
        "summary": value.summary,
        "weaknesses": list(value.weaknesses),
        "candidateSolutions": list(value.candidate_solutions),
        "risks": list(value.risks),
        "evidenceIds": list(value.evidence_ids),
        "assumptions": list(value.assumptions),
    }


def _decision_dict(value: ConvergenceDecision) -> dict[str, object]:
    return {
        "decisionId": value.decision_id,
        "topic": value.topic,
        "disposition": value.disposition.value,
        "rationale": value.rationale,

        "sourceFindingIds": list(value.source_finding_ids),
        "dissentFindingIds": list(value.dissent_finding_ids),
        "requiredChanges": list(value.required_changes),
    }


def _contract_dict(value: ImplementationContract) -> dict[str, object]:
    return {
        "contractId": value.contract_id,
        "objective": value.objective,
        "sourceStateDigest": value.source_state_digest,
        "exactFiles": list(value.exact_files),
        "components": list(value.components),
        "schemasApis": list(value.schemas_apis),
        "invariants": list(value.invariants),
        "migrationRules": list(value.migration_rules),
        "testsGoldenVectors": list(value.tests_golden_vectors),
        "prohibitedChanges": list(value.prohibited_changes),
        "rollbackStrategy": list(value.rollback_strategy),
        "unresolvedQuestions": list(value.unresolved_questions),
        "verificationGates": list(value.verification_gates),
        "acceptedDecisionIds": list(value.accepted_decision_ids),
        "dissentSummary": list(value.dissent_summary),
    }


def _enhancement_dict(value: EnhancementProposal) -> dict[str, object]:
    return {
        "proposalId": value.proposal_id,
        "kind": value.kind.value,
        "title": value.title,
        "value": value.value,
        "risk": value.risk,
        "dependencies": list(value.dependencies),
        "rationale": value.rationale,
        "sourceFindingIds": list(value.source_finding_ids),
        "disposition": value.disposition.value,
    }


def planning_bundle_dict(bundle: PlanningBundle) -> dict[str, object]:
    validate_bundle(bundle)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "councilId": bundle.council_id,
        "explore": [_finding_dict(value) for value in bundle.explore_findings],
        "convergence": [
            _decision_dict(value) for value in bundle.convergence_decisions
        ],
        "implementationContract": _contract_dict(bundle.implementation_contract),
        "enhancements": [_enhancement_dict(value) for value in bundle.enhancements],
    }


def planning_bundle_digest(bundle: PlanningBundle) -> str:
    return digest(planning_bundle_dict(bundle))


def implementation_contract_digest(contract: ImplementationContract) -> str:
    return digest({"schemaVersion": SCHEMA_VERSION, **_contract_dict(contract)})


def freeze_handoff(bundle: PlanningBundle) -> dict[str, object]:
    """Return the immutable CAPT handoff surface for the coding agent."""
    validate_bundle(bundle)
    contract = bundle.implementation_contract
    accepted_enhancements = [
        _enhancement_dict(value)
        for value in bundle.enhancements
        if value.disposition in (Decision.ACCEPT, Decision.REVISE)
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "councilId": bundle.council_id,
        "planningBundleDigest": planning_bundle_digest(bundle),
        "implementationContractDigest": implementation_contract_digest(contract),
        "implementationContract": _contract_dict(contract),
        "acceptedEnhancements": accepted_enhancements,
        "rawCouncilReasoningIncluded": False,
    }
