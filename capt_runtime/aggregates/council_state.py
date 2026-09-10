"""Authoritative durable Model Council aggregate.

Council owns immutable admitted topology and append-only epistemic analyses.
It never owns provider execution, Verification, or ClaimGuard authority.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from ..council import council_definition_from_record, council_digest
from ..errors import AuthorityViolation, IntegrityViolation


class CouncilAggregate(object):
    KIND = "council"

    @staticmethod
    def stream_id(council_id: str) -> str:
        council_id = str(council_id).strip()
        if not council_id:
            raise ValueError("COUNCIL_ID_REQUIRED")
        return "council-" + council_id

    @classmethod
    def create(cls, plan: Mapping[str, Any]) -> Dict[str, Any]:
        definition = council_definition_from_record(plan["definition"])
        expected_digest = council_digest(definition)
        if str(plan["councilDigest"]) != expected_digest:
            raise IntegrityViolation("COUNCIL_PLAN_DIGEST_MISMATCH")
        state = {
            "councilId": definition.council_id,
            "councilDigest": expected_digest,
            "definition": dict(plan["definition"]),
            "tier": definition.tier.value,
            "cohortCount": len(definition.cohorts),
            "vesselsPerCohort": definition.vessels_per_cohort,
            "logicalVesselCount": definition.logical_vessel_count,
            "launchAuthorization": dict(plan.get("launchAuthorization") or {}),
            "admittedAt": str(plan["admittedAt"]),
            "verificationState": "unverified",
            "analysisHistory": [],
        }
        if str(plan.get("councilId") or definition.council_id) != definition.council_id:
            raise IntegrityViolation("COUNCIL_PLAN_IDENTITY_MISMATCH")
        return state

    @classmethod
    def record_analysis(
        cls, current: Mapping[str, Any], analysis: Mapping[str, Any]
    ) -> Dict[str, Any]:
        if str(analysis.get("councilDigest") or "") != str(current["councilDigest"]):
            raise AuthorityViolation("COUNCIL_ANALYSIS_DIGEST_MISMATCH")
        if str(analysis.get("verificationState") or "unverified") != "unverified":
            raise AuthorityViolation("COUNCIL_ANALYSIS_CANNOT_SELF_VERIFY")
        nxt = dict(current)
        history = [dict(item) for item in current.get("analysisHistory") or []]
        history.append(dict(analysis))
        nxt["analysisHistory"] = history
        nxt["verificationState"] = "unverified"
        return nxt

    @classmethod
    def replay_create(cls, plan: Mapping[str, Any]) -> Dict[str, Any]:
        return cls.create(plan)

    @classmethod
    def replay_record_analysis(
        cls, current: Mapping[str, Any], analysis: Mapping[str, Any]
    ) -> Dict[str, Any]:
        return cls.record_analysis(current, analysis)
