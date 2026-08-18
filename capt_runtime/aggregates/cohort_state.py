"""Authoritative durable Cohort aggregate for CAPT-UPG-010.

The cognitive helpers in ``capt_runtime.cohort`` remain non-authoritative
projections. This aggregate owns only the durable state required to reconstruct
bounded Cohort deliberation after restart. RuntimeService/EventStore remain the
sole mutation authority.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from ..errors import AuthorityViolation, IllegalTransition


class CohortAggregate(object):
    KIND = "cohort"

    @staticmethod
    def stream_id(cohort_id: str) -> str:
        if not cohort_id:
            raise ValueError("COHORT_ID_REQUIRED")
        return "cohort-" + cohort_id

    @staticmethod
    def _normalize(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        required = sorted(set(snapshot.get("required") or []))
        roster = sorted(set(snapshot.get("roster") or []))
        if not required:
            raise ValueError("COHORT_REQUIRED_EMPTY")
        if not set(required) <= set(roster):
            raise ValueError("COHORT_REQUIRED_NOT_IN_ROSTER")
        participant_cap = int(snapshot["participantCap"])
        round_cap = int(snapshot["roundCap"])
        epoch = int(snapshot.get("epoch", 0))
        rounds = int(snapshot.get("rounds", 0))
        if participant_cap <= 0 or len(roster) > participant_cap:
            raise ValueError("COHORT_PARTICIPANT_CAP")
        if round_cap <= 0 or rounds < 0 or rounds >= round_cap:
            raise ValueError("COHORT_ROUND_POSITION_INVALID")
        if epoch < 0:
            raise ValueError("COHORT_EPOCH_NEGATIVE")

        seen = set()
        cursors: Dict[str, int] = {str(k): int(v) for k, v in (snapshot.get("participantCursors") or {}).items()}
        contributions = []
        for raw in snapshot.get("contributions") or []:
            item = dict(raw)
            cid = str(item["contributionId"])
            if cid in seen:
                raise ValueError("COHORT_DUPLICATE_CONTRIBUTION")
            seen.add(cid)
            participant = str(item["participant"])
            if participant not in roster:
                raise ValueError("COHORT_PARTICIPANT_NOT_ADMITTED")
            item_epoch = int(item["epoch"])
            item_round = int(item["round"])
            cursor = int(item["cursor"])
            if item_epoch < 0 or item_round < 0 or cursor < 0:
                raise ValueError("COHORT_POSITION_NEGATIVE")
            if item_round >= round_cap:
                raise ValueError("COHORT_CONTRIBUTION_ROUND_OUT_OF_RANGE")
            previous = cursors.get(participant, 0)
            if cursor < previous:
                raise ValueError("COHORT_CURSOR_CANNOT_REGRESS")
            cursors[participant] = max(previous, cursor)
            contributions.append({
                "contributionId": cid,
                "participant": participant,
                "epoch": item_epoch,
                "round": item_round,
                "outcome": str(item["outcome"]),
                "cursor": cursor,
                "sourceSequences": [int(v) for v in item.get("sourceSequences") or []],
                "material": bool(item.get("material", False)),
                "escalation": item.get("escalation"),
            })

        return {
            "cohortId": str(snapshot["cohortId"]),
            "missionId": str(snapshot["missionId"]),
            "taskId": str(snapshot["taskId"]),
            "epoch": epoch,
            "rounds": rounds,
            "roundCap": round_cap,
            "participantCap": participant_cap,
            "required": required,
            "roster": roster,
            "participantCursors": cursors,
            "contributions": contributions,
            "stoppingReason": snapshot.get("stoppingReason"),
            "evidenceIds": list(dict.fromkeys(snapshot.get("evidenceIds") or [])),
            "latestSteer": dict(snapshot["latestSteer"]) if snapshot.get("latestSteer") else None,
        }

    @classmethod
    def create(cls, snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        state = cls._normalize(snapshot)
        if state["epoch"] != 0:
            raise ValueError("COHORT_INITIAL_EPOCH_MUST_BE_ZERO")
        return state

    @classmethod
    def replace_snapshot(cls, current: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        nxt = cls._normalize(snapshot)
        if nxt["cohortId"] != current["cohortId"]:
            raise AuthorityViolation("cohort identity cannot change")
        if nxt["missionId"] != current["missionId"] or nxt["taskId"] != current["taskId"]:
            raise AuthorityViolation("cohort mission/task binding cannot change")
        if nxt["epoch"] < int(current["epoch"]):
            raise IllegalTransition("cohort epoch", str(current["epoch"]), str(nxt["epoch"]))
        old_ids = {c["contributionId"] for c in current.get("contributions") or []}
        new_ids = {c["contributionId"] for c in nxt.get("contributions") or []}
        if not old_ids <= new_ids:
            raise AuthorityViolation("cohort snapshot may not delete admitted contributions")
        for participant, cursor in (current.get("participantCursors") or {}).items():
            if int(nxt["participantCursors"].get(participant, 0)) < int(cursor):
                raise AuthorityViolation("cohort participant cursor may not regress")
        nxt["evidenceIds"] = list(dict.fromkeys(list(current.get("evidenceIds") or []) + list(nxt.get("evidenceIds") or [])))
        return nxt

    @staticmethod
    def attach_evidence(current: Mapping[str, Any], evidence_id: str) -> Dict[str, Any]:
        nxt = dict(current)
        ids = list(nxt.get("evidenceIds") or [])
        if evidence_id not in ids:
            ids.append(evidence_id)
        nxt["evidenceIds"] = ids
        return nxt

    @staticmethod
    def steer(current: Mapping[str, Any], directive: str, reason: str, actor_id: str, issued_at: str) -> Dict[str, Any]:
        if not directive or not directive.strip():
            raise ValueError("COHORT_STEER_DIRECTIVE_REQUIRED")
        nxt = dict(current)
        nxt["epoch"] = int(current["epoch"]) + 1
        nxt["rounds"] = 0
        nxt["stoppingReason"] = None
        nxt["latestSteer"] = {
            "directive": directive,
            "reason": reason,
            "steeredBy": actor_id,
            "steeredAt": issued_at,
            "epoch": nxt["epoch"],
        }
        return nxt
