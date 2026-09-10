from __future__ import annotations

from capt_runtime import commands
from capt_runtime.council import (
    ClaimObservation, ClaimStance, CouncilLaunchAuthorization, CouncilTier,
    analyze_claims, council_digest,
)
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.store import EventStore
from capt_ui.operator.council_chamber import project_council_chamber
from tests.capt_runtime.test_council_alpha import make_council


def meta(name: str):
    return commands.command(
        command_id="cmd-ui-" + name, idempotency_key="idem-ui-" + name,
        operation_fingerprint=commands.fingerprint(name, {"name": name}),
        correlation_id="corr-ui-council", actor_id="capt-runtime", actor_kind="system",
        issued_at="2026-09-10T18:10:00Z", replay_policy="never",
    )


def admitted_state(tier: CouncilTier, *, vessels_per_cohort: int | None = None):
    store = EventStore(":memory:")
    definition = make_council(tier, vessels_per_cohort=vessels_per_cohort)
    auth = CouncilLaunchAuthorization(
        council_digest(definition), extreme_ack=tier == CouncilTier.EXTREME,
        custom_scale_ack=tier == CouncilTier.EXTREME and vessels_per_cohort not in (None, 18),
    )
    state = GovernedRuntimeService(store).admit_council_plan(
        definition, auth, meta("admit-" + tier.value)
    )["council"]
    return store, definition, state


def test_small_projection_exposes_truthful_topology_and_logical_blast():
    store, definition, state = admitted_state(CouncilTier.SMALL)
    view = project_council_chamber(state)
    assert view["authority"] == "projection_only"
    assert view["tier"] == "small"
    assert view["cohortCount"] == 2
    assert view["logicalVessels"] == 6
    assert view["blastStatus"] == "logical_blast_ready"
    assert view["timingCounts"] == {
        "logicalDispatched": 6, "transportAdmitted": 0,
        "providerStarted": 0, "completed": 0,
    }
    assert [(row["providerId"], row["modelId"]) for row in view["cohorts"]] == [
        (c.provider_id, c.model_id) for c in definition.cohorts
    ]
    assert len(view["vesselPreview"]) == 6
    assert view["vesselPreviewTruncated"] is False
    store.close()

def test_extreme_projection_summarizes_24000_vessels_without_rendering_all_rows():
    store, _, state = admitted_state(CouncilTier.EXTREME, vessels_per_cohort=1000)
    view = project_council_chamber(state)
    assert view["tier"] == "extreme"
    assert view["logicalVessels"] == 24000
    assert len(view["vesselPreview"]) == 64
    assert view["vesselPreviewTruncated"] is True
    assert view["launchInterlock"] == {
        "extremeAcknowledged": True,
        "customScaleAcknowledged": True,
        "maximumSpendUsd": None,
    }
    store.close()


def test_projection_preserves_dispute_and_surfaces_targeted_challenge_candidate():
    store, definition, _ = admitted_state(CouncilTier.SMALL)
    svc = GovernedRuntimeService(store)
    analysis = analyze_claims(definition, (
        ClaimObservation("a", "claim A", "c00", "c00-v0001", ClaimStance.SUPPORT, 0.8),
        ClaimObservation("a", "claim A", "c01", "c01-v0001", ClaimStance.DISSENT, 0.9),
    ))
    state = svc.record_council_analysis(definition.council_id, analysis, meta("analysis"))["council"]
    view = project_council_chamber(state)
    assert view["epistemicSummary"]["disputedClaims"] == 1
    assert view["epistemicSummary"]["verifiedClaims"] == 0
    assert view["challengeCandidates"] == [
        {"claimId": "a", "reason": "material_dispute"}
    ]
    store.close()
