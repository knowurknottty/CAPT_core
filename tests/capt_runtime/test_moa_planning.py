from capt_runtime.moa_planning import (
    ConvergenceDecision,
    Decision,
    EnhancementKind,
    EnhancementProposal,
    ExploreFinding,
    ImplementationContract,
    PlanningBundle,
    PlanningValidationError,
    freeze_handoff,
    implementation_contract_digest,
    planning_bundle_digest,
    validate_bundle,
)


def _bundle():
    findings = (
        ExploreFinding(
            "f-hy3", "ref-hy3", "hy3", "epoch risk",
            ("epoch ambiguity",), ("pin conventions",), ("boundary drift",),
            ("e-src-1",), ("Gregorian input",),
        ),
        ExploreFinding(
            "f-deepseek", "ref-deepseek", "deepseek-v4", "test drift",
            ("docs can diverge",), ("golden vectors",), ("silent regression",),
            ("e-src-2",), (),
        ),
    )

    decisions = (
        ConvergenceDecision(
            "d-conventions", "calendar conventions", Decision.ACCEPT,
            "pin system-specific semantics", ("f-hy3",), (),
            ("emit convention metadata",),
        ),
        ConvergenceDecision(
            "d-shared-layer", "shared conversion layer", Decision.REJECT,
            "generic policy erases system boundaries", ("f-deepseek",),
            ("f-hy3",), (),
        ),
    )
    contract = ImplementationContract(
        "ic-r1", "promote richer calculators safely", "sha256:" + "a" * 64,
        ("src/engine.py",), ("unified signature",), ("signature.systems",),
        ("preserve system boundaries",), ("additive schema only",),
        ("golden vector A",), ("no motif vote inflation",),
        ("restore frozen source patch",), ("true solar time unresolved",),
        ("focused tests", "full tests"), ("d-conventions",),
        ("shared conversion layer rejected",),
    )

    enhancements = (
        EnhancementProposal(
            "e-1", EnhancementKind.UPGRADE, "contract-derived capability docs",
            "prevents code-doc drift", "moderate implementation work",
            ("contract metadata",), "derive displayed capability from code",
            ("f-deepseek",), Decision.ACCEPT,
        ),
    )
    return PlanningBundle(
        "maxed-out-r1", findings, decisions, contract, enhancements
    )


def test_bundle_validates_and_digest_is_deterministic():
    bundle = _bundle()
    validate_bundle(bundle)
    assert planning_bundle_digest(bundle) == planning_bundle_digest(bundle)
    assert implementation_contract_digest(bundle.implementation_contract).startswith(
        "sha256:"
    )


def test_freeze_handoff_excludes_raw_reasoning_and_keeps_dissent():
    handoff = freeze_handoff(_bundle())
    assert handoff["rawCouncilReasoningIncluded"] is False
    contract = handoff["implementationContract"]
    assert contract["dissentSummary"] == ["shared conversion layer rejected"]
    assert handoff["acceptedEnhancements"][0]["proposalId"] == "e-1"

def test_independent_sources_are_required():
    bundle = _bundle()
    one_source = tuple(
        ExploreFinding(
            item.finding_id, "same-source", item.model_id, item.summary,
            item.weaknesses, item.candidate_solutions, item.risks,
            item.evidence_ids, item.assumptions,
        )
        for item in bundle.explore_findings
    )
    broken = PlanningBundle(
        bundle.council_id,
        one_source,
        bundle.convergence_decisions,
        bundle.implementation_contract,
        bundle.enhancements,
    )
    try:
        validate_bundle(broken)
    except PlanningValidationError as exc:
        assert str(exc) == "INDEPENDENT_SOURCES_REQUIRED"
    else:
        raise AssertionError("expected independent-source validation failure")


def test_unknown_finding_reference_is_rejected():
    bundle = _bundle()
    bad_decision = ConvergenceDecision(
        "d-bad", "bad", Decision.ACCEPT, "bad reference", ("missing",)
    )
    broken = PlanningBundle(
        bundle.council_id,
        bundle.explore_findings,
        bundle.convergence_decisions + (bad_decision,),
        bundle.implementation_contract,
        bundle.enhancements,
    )
    try:
        validate_bundle(broken)
    except PlanningValidationError as exc:
        assert str(exc) == "UNKNOWN_FINDING_REFERENCE"
    else:
        raise AssertionError("expected unknown-finding validation failure")

