"""CAPT-UPG-018 truthful Cohort Deliberation Chamber projections."""
from __future__ import annotations

from copy import deepcopy


def _state():
    return {
        "cohortId": "coh-18",
        "missionId": "m-18",
        "taskId": "t-18",
        "epoch": 2,
        "rounds": 1,
        "roundCap": 4,
        "participantCap": 4,
        "required": ["planner", "reviewer"],
        "roster": ["planner", "reviewer", "optional"],
        "participantCursors": {"planner": 30, "reviewer": 31, "optional": 29},
        "contributions": [
            # stale epoch: visible history, never current quorum/debt
            {"contributionId": "stale-pass", "participant": "planner", "epoch": 1, "round": 0, "outcome": "PASS", "cursor": 10, "sourceSequences": [9, 10], "material": False, "escalation": None},
            {"contributionId": "stale-dissent", "participant": "optional", "epoch": 1, "round": 0, "outcome": "DISSENT", "cursor": 11, "sourceSequences": [11], "material": True, "escalation": None},
            # current epoch, prior round: reviewer PASS cannot satisfy round 1
            {"contributionId": "reviewer-old-pass", "participant": "reviewer", "epoch": 2, "round": 0, "outcome": "PASS", "cursor": 20, "sourceSequences": [20], "material": False, "escalation": None},
            # current round
            {"contributionId": "planner-pass", "participant": "planner", "epoch": 2, "round": 1, "outcome": "PASS", "cursor": 30, "sourceSequences": [30], "material": False, "escalation": None},
            {"contributionId": "optional-pass", "participant": "optional", "epoch": 2, "round": 1, "outcome": "PASS", "cursor": 29, "sourceSequences": [29], "material": False, "escalation": None},
        ],
        "stoppingReason": None,
        "evidenceIds": ["ev-cohort-18-v1"],
        "latestSteer": {
            "directive": "inspect alternate evidence",
            "reason": "operator steering",
            "steeredBy": "captain",
            "steeredAt": "2026-08-18T08:20:00Z",
            "epoch": 2,
        },
    }


def test_stale_epoch_and_prior_round_do_not_satisfy_current_silence_quorum():
    from capt_ui.operator.cohort_chamber import project_cohort_chamber

    view = project_cohort_chamber(_state())

    assert view["currentEpoch"] == 2
    assert view["currentRound"] == 1
    assert view["projectedSilenceQuorum"] is False
    assert view["requiredPassParticipants"] == ["planner"]
    assert view["missingRequiredPassParticipants"] == ["reviewer"]
    assert view["cognitiveDebt"] == {
        "unresolvedDissent": 0,
        "unresolvedEscalation": 0,
        "requestedEvidence": 0,
        "staleResults": 2,
    }
    by_id = {row["contributionId"]: row for row in view["contributions"]}
    assert by_id["stale-pass"]["temporalClass"] == "stale_epoch"
    assert by_id["stale-dissent"]["countsTowardCurrentDebt"] is False
    assert by_id["reviewer-old-pass"]["temporalClass"] == "prior_round_current_epoch"
    assert by_id["reviewer-old-pass"]["countsTowardCurrentQuorum"] is False
    assert by_id["planner-pass"]["temporalClass"] == "current_round"
    assert view["recordedStoppingReason"] is None
    assert view["projectedStoppingReason"] is None
    assert view["stoppingReasonMatchesProjection"] is True


def test_true_silence_quorum_requires_current_round_pass_from_every_required_participant():
    from capt_ui.operator.cohort_chamber import project_cohort_chamber

    state = _state()
    state["contributions"].append(
        {"contributionId": "reviewer-current-pass", "participant": "reviewer", "epoch": 2, "round": 1, "outcome": "PASS", "cursor": 31, "sourceSequences": [31], "material": False, "escalation": None}
    )
    state["stoppingReason"] = "SILENCE_QUORUM"

    view = project_cohort_chamber(state)

    assert view["projectedSilenceQuorum"] is True
    assert view["requiredPassParticipants"] == ["planner", "reviewer"]
    assert view["missingRequiredPassParticipants"] == []
    assert view["projectedStoppingReason"] == "SILENCE_QUORUM"
    assert view["recordedStoppingReason"] == "SILENCE_QUORUM"
    assert view["stoppingReasonMatchesProjection"] is True


def test_current_epoch_material_dissent_blocks_quorum_even_after_later_pass():
    from capt_ui.operator.cohort_chamber import project_cohort_chamber

    state = _state()
    state["contributions"].extend([
        {"contributionId": "reviewer-current-pass", "participant": "reviewer", "epoch": 2, "round": 1, "outcome": "PASS", "cursor": 31, "sourceSequences": [31], "material": False, "escalation": None},
        {"contributionId": "material-dissent", "participant": "optional", "epoch": 2, "round": 0, "outcome": "DISSENT", "cursor": 25, "sourceSequences": [25], "material": True, "escalation": None},
    ])

    view = project_cohort_chamber(state)

    assert view["requiredPassParticipants"] == ["planner", "reviewer"]
    assert view["cognitiveDebt"]["unresolvedDissent"] == 1
    assert view["projectedSilenceQuorum"] is False
    assert view["projectedStoppingReason"] is None


def test_escalation_and_evidence_request_are_concrete_debt_not_confidence_scores():
    from capt_ui.operator.cohort_chamber import project_cohort_chamber

    state = _state()
    state["contributions"].extend([
        {"contributionId": "reviewer-current-pass", "participant": "reviewer", "epoch": 2, "round": 1, "outcome": "PASS", "cursor": 31, "sourceSequences": [31], "material": False, "escalation": None},
        {"contributionId": "escalate", "participant": "optional", "epoch": 2, "round": 1, "outcome": "ESCALATE", "cursor": 32, "sourceSequences": [32], "material": False, "escalation": "MISSING_EVIDENCE"},
        {"contributionId": "request-evidence", "participant": "planner", "epoch": 2, "round": 0, "outcome": "REQUEST_EVIDENCE", "cursor": 21, "sourceSequences": [21], "material": False, "escalation": None},
    ])

    view = project_cohort_chamber(state)

    assert view["cognitiveDebt"]["unresolvedEscalation"] == 1
    assert view["cognitiveDebt"]["requestedEvidence"] == 1
    assert view["projectedSilenceQuorum"] is False
    assert "confidence" not in view
    assert "confidenceScore" not in view


def test_recorded_stopping_reason_is_not_silently_replaced_by_projection():
    from capt_ui.operator.cohort_chamber import project_cohort_chamber

    state = _state()
    state["stoppingReason"] = "SILENCE_QUORUM"  # inconsistent with missing reviewer current-round PASS
    view = project_cohort_chamber(state)

    assert view["recordedStoppingReason"] == "SILENCE_QUORUM"
    assert view["projectedStoppingReason"] is None
    assert view["stoppingReasonMatchesProjection"] is False
    assert "recorded_stopping_reason_differs_from_projection" in view["integrityWarnings"]


def test_chamber_does_not_invent_unpersisted_contribution_text_or_model_identity():
    from capt_ui.operator.cohort_chamber import project_cohort_chamber

    view = project_cohort_chamber(_state())
    row = view["contributions"][0]
    assert "text" not in row
    assert "proposal" not in row
    assert "model" not in row
    assert "provider" not in row
    assert view["authority"] == "projection_only"


def test_final_permitted_round_without_required_quorum_projects_bounded_incomplete():
    from capt_ui.operator.cohort_chamber import project_cohort_chamber

    state = _state()
    state["roundCap"] = 2  # current round index 1 is the final permitted round
    state["stoppingReason"] = "BOUNDED_INCOMPLETE"
    view = project_cohort_chamber(state)

    assert view["projectedSilenceQuorum"] is False
    assert view["projectedStoppingReason"] == "BOUNDED_INCOMPLETE"
    assert view["recordedStoppingReason"] == "BOUNDED_INCOMPLETE"
    assert view["stoppingReasonMatchesProjection"] is True


def test_future_round_contribution_is_flagged_and_excluded_from_current_quorum_and_debt():
    from capt_ui.operator.cohort_chamber import project_cohort_chamber

    state = _state()
    state["contributions"].append(
        {"contributionId": "future-pass", "participant": "reviewer", "epoch": 2, "round": 2, "outcome": "PASS", "cursor": 40, "sourceSequences": [40], "material": False, "escalation": None}
    )
    state["participantCursors"]["reviewer"] = 40
    view = project_cohort_chamber(state)
    row = next(r for r in view["contributions"] if r["contributionId"] == "future-pass")

    assert row["temporalClass"] == "future_round_current_epoch"
    assert row["countsTowardCurrentQuorum"] is False
    assert row["countsTowardCurrentDebt"] is False
    assert "reviewer" in view["missingRequiredPassParticipants"]
    assert "future_round_contribution:future-pass" in view["integrityWarnings"]
