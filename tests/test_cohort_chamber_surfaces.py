"""CAPT-UPG-018 surface contract tests."""
from __future__ import annotations

import json


def _view():
    return {
        "schemaVersion": "1.0.0",
        "kind": "CohortDeliberationChamberProjection",
        "authority": "projection_only",
        "cohortId": "coh-ui",
        "missionId": "m-ui",
        "taskId": "t-ui",
        "currentEpoch": 1,
        "currentRound": 0,
        "roundCap": 3,
        "participantCap": 2,
        "required": ["planner"],
        "roster": ["planner"],
        "participantCursors": {"planner": 4},
        "participants": [{"participant": "planner", "required": True, "cursor": 4, "currentRoundContributionId": "c-1", "currentRoundOutcome": "PASS"}],
        "contributions": [{"contributionId": "c-1", "participant": "planner", "epoch": 1, "round": 0, "outcome": "PASS", "cursor": 4, "sourceSequences": [4], "material": False, "escalation": None, "temporalClass": "current_round", "countsTowardCurrentQuorum": True, "countsTowardCurrentDebt": True}],
        "cognitiveDebt": {"unresolvedDissent": 0, "unresolvedEscalation": 0, "requestedEvidence": 0, "staleResults": 0},
        "requiredPassParticipants": ["planner"],
        "missingRequiredPassParticipants": [],
        "projectedSilenceQuorum": True,
        "projectedStoppingReason": "SILENCE_QUORUM",
        "recordedStoppingReason": "SILENCE_QUORUM",
        "stoppingReasonMatchesProjection": True,
        "evidenceIds": ["ev-1"],
        "latestSteer": None,
        "integrityWarnings": [],
        "semantics": {"proposalTextPersisted": False, "modelIdentityPersisted": False, "confidenceScoreProvided": False, "quorumIsTruthClaim": False},
    }


def test_desktop_headless_payload_is_deterministic_json_projection():
    from desktop.cohort_chamber import render_headless

    raw = render_headless(_view())
    decoded = json.loads(raw)
    assert decoded["authority"] == "projection_only"
    assert decoded["cohortId"] == "coh-ui"
    assert raw == render_headless(_view())


def test_textual_surface_uses_same_truthful_shared_rendering():
    from capt_ui.surfaces.tui.cohort_chamber_app import CohortChamberTUI

    text = CohortChamberTUI.view_text(_view())
    assert "Cohort Deliberation Chamber (projection only)" in text
    assert "SILENCE_QUORUM" in text
    assert "confidence" not in text.lower()
    assert "proposal" not in text.lower()


def test_textual_chamber_mounts_projection_and_submits_governed_steer():
    import asyncio

    from capt_ui.surfaces.tui.cohort_chamber_app import CohortChamberTUI
    from textual.widgets import Input, Static

    class _Op:
        def __init__(self):
            self.steers = []

        def cohort_chamber(self, cohort_id):
            assert cohort_id == "coh-ui"
            return _view()

        def steer_deliberation(self, cohort_id, directive, *, reason="operator steering"):
            self.steers.append((cohort_id, directive, reason))
            return {"status": "accepted", "classification": "accepted"}

        def disconnect(self):
            raise AssertionError("injected operator must not be disconnected by app")

    async def scenario():
        op = _Op()
        app = CohortChamberTUI(cohort_id="coh-ui", operator=op)
        async with app.run_test() as pilot:
            chamber = app.query_one("#chamber", Static)
            assert "SILENCE_QUORUM" in str(chamber.render())
            app.query_one("#directive", Input).value = "inspect alternate evidence"
            app.query_one("#reason", Input).value = "operator correction"
            await pilot.click("#submit-steer")
            await pilot.pause()
            assert op.steers == [
                ("coh-ui", "inspect alternate evidence", "operator correction")
            ]

    asyncio.run(scenario())
