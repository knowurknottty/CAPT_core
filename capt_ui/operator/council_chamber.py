"""Read-only operator projection for authoritative Model Council state."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from capt_runtime.council import (
    build_logical_blast,
    council_definition_from_record,
)


def _challenge_candidates(analysis: Mapping[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for claim in analysis.get("claims") or []:
        status = str(claim.get("status") or "")
        reason = None
        if status == "disputed":
            reason = "material_dispute"
        elif status == "minority" and max(
            float(claim.get("maxSupportConfidence") or 0.0),
            float(claim.get("maxDissentConfidence") or 0.0),
        ) >= 0.90:
            reason = "high_confidence_minority"
        elif (
            status == "converged"
            and not (claim.get("dissentCohorts") or [])
            and not (claim.get("insufficientCohorts") or [])
            and not (claim.get("abstainCohorts") or [])
            and not (claim.get("evidenceIds") or [])
        ):
            reason = "unsupported_unanimity"
        if reason:
            out.append({"claimId": str(claim["claimId"]), "reason": reason})
    return out

def project_council_chamber(
    state: Mapping[str, Any], *, vessel_preview_limit: int = 64
) -> Dict[str, Any]:
    council_id = str(state.get("councilId") or "")
    if not council_id:
        raise ValueError("COUNCIL_CHAMBER_ID_REQUIRED")
    if vessel_preview_limit < 0:
        raise ValueError("COUNCIL_CHAMBER_PREVIEW_LIMIT_NEGATIVE")

    definition = council_definition_from_record(state["definition"])
    blast = build_logical_blast(definition)
    preview = [
        {
            "vesselId": item.vessel_id,
            "cohortId": item.cohort_id,
            "providerId": item.provider_id,
            "modelId": item.model_id,
            "configurationId": item.configuration_id,
            "ordinal": item.ordinal,
            "timingStage": "logical_dispatched",
            "logicalDispatchedAt": state.get("admittedAt"),
        }
        for item in blast[:vessel_preview_limit]
    ]

    analyses = list(state.get("analysisHistory") or [])
    latest = analyses[-1] if analyses else None
    claims = list((latest or {}).get("claims") or [])
    status_counts = {
        key: sum(str(claim.get("status") or "") == key for claim in claims)
        for key in ("converged", "disputed", "minority", "insufficient_evidence", "unresolved")
    }
    launch = dict(state.get("launchAuthorization") or {})
    cohorts = [
        {
            "cohortId": c.cohort_id,
            "providerId": c.provider_id,
            "modelId": c.model_id,
            "configurationId": c.configuration_id,
            "vessels": definition.vessels_per_cohort,
        }
        for c in definition.cohorts
    ]
    return {
        "schemaVersion": "1.0.0",
        "kind": "ModelCouncilChamberProjection",
        "authority": "projection_only",
        "councilId": council_id,
        "councilDigest": state.get("councilDigest"),
        "tier": definition.tier.value,
        "cohortCount": len(definition.cohorts),
        "vesselsPerCohort": definition.vessels_per_cohort,
        "logicalVessels": definition.logical_vessel_count,
        "cohorts": cohorts,
        "blastStatus": "analysis_recorded" if analyses else "logical_blast_ready",
        "timingCounts": {
            "logicalDispatched": definition.logical_vessel_count,
            "transportAdmitted": 0,
            "providerStarted": 0,
            "completed": 0,
        },
        "launchInterlock": {
            "extremeAcknowledged": bool(launch.get("extremeAck", False)),
            "customScaleAcknowledged": bool(launch.get("customScaleAck", False)),
            "maximumSpendUsd": launch.get("maximumSpendUsd"),
        },
        "epistemicSummary": {
            "analysisCount": len(analyses),
            "claimCount": len(claims),
            "convergedClaims": status_counts["converged"],
            "disputedClaims": status_counts["disputed"],
            "minorityClaims": status_counts["minority"],
            "insufficientEvidenceClaims": status_counts["insufficient_evidence"],
            "unresolvedClaims": status_counts["unresolved"],
            "verifiedClaims": sum(
                str(claim.get("verificationState") or "unverified") == "verified"
                for claim in claims
            ),
            "rawObservationCount": len((latest or {}).get("rawObservations") or []),
            "distinctModelSources": (latest or {}).get("distinctModelSources"),
        },
        "challengeCandidates": _challenge_candidates(latest or {}),
        "vesselPreview": preview,
        "vesselPreviewLimit": vessel_preview_limit,
        "vesselPreviewTruncated": len(blast) > len(preview),
        "verificationState": "unverified",
    }
