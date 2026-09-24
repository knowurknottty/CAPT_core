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
    OWNED_FIELDS = frozenset({
        "council.councilDigest",
        "council.definition",
        "council.tier",
        "council.cohortCount",
        "council.vesselsPerCohort",
        "council.logicalVesselCount",
        "council.launchAuthorization",
        "council.admittedAt",
        "council.verificationState",
        "council.analysisHistory",
        "council.scheduleHistory",
    })
    REFERENCE_FIELDS = frozenset({"councilId"})

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
            "scheduleHistory": [],
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
    def record_schedule(
        cls, current: Mapping[str, Any], schedule: Mapping[str, Any]
    ) -> Dict[str, Any]:
        if str(schedule.get("councilId") or "") != str(current["councilId"]):
            raise AuthorityViolation("COUNCIL_SCHEDULE_IDENTITY_MISMATCH")
        if str(schedule.get("councilDigest") or "") != str(current["councilDigest"]):
            raise AuthorityViolation("COUNCIL_SCHEDULE_DIGEST_MISMATCH")
        if int(schedule.get("logicalVesselCount", -1)) != int(current["logicalVesselCount"]):
            raise AuthorityViolation("COUNCIL_SCHEDULE_LOGICAL_COUNT_MISMATCH")
        if int(schedule.get("physicalSlotCount", -1)) != int(current["cohortCount"]):
            raise AuthorityViolation("COUNCIL_SCHEDULE_SLOT_COUNT_MISMATCH")
        slots = schedule.get("slots") or []
        if len(slots) != int(current["cohortCount"]):
            raise AuthorityViolation("COUNCIL_SCHEDULE_SLOT_COUNT_MISMATCH")
        nxt = dict(current)
        history = [dict(item) for item in current.get("scheduleHistory") or []]
        history.append(dict(schedule))
        nxt["scheduleHistory"] = history
        return nxt

    @classmethod
    def replay_create(cls, plan: Mapping[str, Any]) -> Dict[str, Any]:
        return cls.create(plan)

    @classmethod
    def replay_record_analysis(
        cls, current: Mapping[str, Any], analysis: Mapping[str, Any]
    ) -> Dict[str, Any]:
        return cls.record_analysis(current, analysis)

    @classmethod
    def replay_record_schedule(
        cls, current: Mapping[str, Any], schedule: Mapping[str, Any]
    ) -> Dict[str, Any]:
        return cls.record_schedule(current, schedule)
