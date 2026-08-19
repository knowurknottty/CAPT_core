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
    OWNED_FIELDS = frozenset(
        {
            "cohort.epoch",
            "cohort.rounds",
            "cohort.roundCap",
            "cohort.participantCap",
            "cohort.required",
            "cohort.roster",
            "cohort.participantCursors",
            "cohort.contributions",
            "cohort.stoppingReason",
            "cohort.evidenceIds",
            "cohort.latestSteer",
        }
    )
    REFERENCE_FIELDS = frozenset({"cohortId", "missionId", "taskId"})

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
        declared_cursors: Dict[str, int] = {
            str(k): int(v) for k, v in (snapshot.get("participantCursors") or {}).items()
        }
        if any(participant not in roster for participant in declared_cursors):
            raise ValueError("COHORT_CURSOR_PARTICIPANT_NOT_ADMITTED")
        if any(cursor < 0 for cursor in declared_cursors.values()):
            raise ValueError("COHORT_CURSOR_NEGATIVE")
        observed_cursors: Dict[str, int] = {}
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
            if item_epoch > epoch:
                raise ValueError("COHORT_FUTURE_EPOCH_CONTRIBUTION")
            if item_round >= round_cap:
                raise ValueError("COHORT_CONTRIBUTION_ROUND_OUT_OF_RANGE")
            if item_epoch == epoch and item_round > rounds:
                raise ValueError("COHORT_FUTURE_ROUND_CONTRIBUTION")
            previous = observed_cursors.get(participant, 0)
            if cursor < previous:
                raise ValueError("COHORT_CONTRIBUTION_CURSOR_CANNOT_REGRESS")
            observed_cursors[participant] = cursor
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

        for participant, observed in observed_cursors.items():
            declared = declared_cursors.get(participant)
            if declared is None:
                declared_cursors[participant] = observed
            elif declared < observed:
                raise ValueError("COHORT_CURSOR_BEHIND_CONTRIBUTION")

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
            "participantCursors": declared_cursors,
            "contributions": contributions,
            "stoppingReason": snapshot.get("stoppingReason"),
            "evidenceIds": list(dict.fromkeys(snapshot.get("evidenceIds") or [])),
            "latestSteer": dict(snapshot["latestSteer"]) if snapshot.get("latestSteer") else None,
        }


    @staticmethod
    def _derived_stopping_reason(state: Mapping[str, Any]) -> Any:
        epoch = int(state["epoch"])
        round_index = int(state["rounds"])
        values = [c for c in state.get("contributions") or [] if int(c["epoch"]) == epoch]
        has_debt = any(
            c["outcome"] in {"ESCALATE", "REQUEST_EVIDENCE"}
            or (c["outcome"] == "DISSENT" and bool(c.get("material", False)))
            for c in values
        )
        at_cap = round_index + 1 >= int(state["roundCap"])
        if has_debt:
            return "BOUNDED_INCOMPLETE" if at_cap else None
        latest: Dict[str, Mapping[str, Any]] = {}
        for contribution in values:
            if int(contribution["round"]) == round_index:
                latest[str(contribution["participant"])] = contribution
        passed = {
            participant for participant, contribution in latest.items()
            if contribution["outcome"] == "PASS"
        }
        if set(state["required"]) <= passed:
            return "SILENCE_QUORUM"
        return "BOUNDED_INCOMPLETE" if at_cap else None

    @classmethod
    def create(cls, snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        state = cls._normalize(snapshot)
        if state["epoch"] != 0:
            raise ValueError("COHORT_INITIAL_EPOCH_MUST_BE_ZERO")
        if state.get("evidenceIds"):
            raise AuthorityViolation("cohort snapshot may not seed evidence authority")
        if state.get("latestSteer") is not None:
            raise AuthorityViolation("initial cohort snapshot may not seed steering authority")
        expected_stop = cls._derived_stopping_reason(state)
        if state.get("stoppingReason") != expected_stop:
            raise AuthorityViolation("cohort stopping reason must be deterministically derived")
        return state

    @classmethod
    def replace_snapshot(cls, current: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        nxt = cls._normalize(snapshot)
        if nxt["cohortId"] != current["cohortId"]:
            raise AuthorityViolation("cohort identity cannot change")
        if nxt["missionId"] != current["missionId"] or nxt["taskId"] != current["taskId"]:
            raise AuthorityViolation("cohort mission/task binding cannot change")
        for field in ("required", "roster", "participantCap", "roundCap"):
            if nxt[field] != current[field]:
                raise AuthorityViolation("cohort quorum/roster/cap configuration is immutable after creation")
        # Epoch transitions are owned only by the human steering path.
        if int(nxt["epoch"]) != int(current["epoch"]):
            raise AuthorityViolation("cohort snapshot persistence may not change deliberation epoch")
        if int(nxt["rounds"]) < int(current["rounds"]):
            raise AuthorityViolation("cohort round position may not regress")

        old_by_id = {c["contributionId"]: c for c in current.get("contributions") or []}
        new_by_id = {c["contributionId"]: c for c in nxt.get("contributions") or []}
        if not set(old_by_id) <= set(new_by_id):
            raise AuthorityViolation("cohort snapshot may not delete admitted contributions")
        for contribution_id, prior in old_by_id.items():
            if new_by_id[contribution_id] != prior:
                raise AuthorityViolation("cohort snapshot may not rewrite admitted contributions")
        for participant, cursor in (current.get("participantCursors") or {}).items():
            if int(nxt["participantCursors"].get(participant, 0)) < int(cursor):
                raise AuthorityViolation("cohort participant cursor may not regress")

        offered_steer = nxt.get("latestSteer")
        current_steer = current.get("latestSteer")
        if offered_steer is not None and offered_steer != current_steer:
            raise AuthorityViolation("cohort snapshot may not forge steering authority")
        nxt["latestSteer"] = dict(current_steer) if current_steer else None
        # Evidence linkage is owned by RuntimeService admission, never snapshot input.
        if nxt.get("evidenceIds"):
            raise AuthorityViolation("cohort snapshot may not supply evidence authority")
        nxt["evidenceIds"] = list(current.get("evidenceIds") or [])
        expected_stop = cls._derived_stopping_reason(nxt)
        if nxt.get("stoppingReason") != expected_stop:
            raise AuthorityViolation("cohort stopping reason must be deterministically derived")
        return nxt

    @classmethod
    def replay_create(cls, snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        """Reconstruct a RuntimeService-authored CohortCreated event.

        Unlike caller-facing ``create``, the persisted event may already contain
        the evidence ID minted atomically by RuntimeService. The event ledger is
        the authority boundary here; all structural/quorum invariants are still
        revalidated.
        """
        state = cls._normalize(snapshot)
        if state["epoch"] != 0:
            raise ValueError("COHORT_INITIAL_EPOCH_MUST_BE_ZERO")
        if state.get("latestSteer") is not None:
            raise AuthorityViolation("initial cohort event may not contain steering state")
        if state.get("stoppingReason") != cls._derived_stopping_reason(state):
            raise AuthorityViolation("cohort stopping reason must be deterministically derived")
        return state

    @classmethod
    def replay_replace(cls, current: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Dict[str, Any]:
        """Reconstruct a RuntimeService-authored CohortSnapshotPersisted event."""
        nxt = cls._normalize(snapshot)
        if nxt["cohortId"] != current["cohortId"]:
            raise AuthorityViolation("cohort identity cannot change")
        if nxt["missionId"] != current["missionId"] or nxt["taskId"] != current["taskId"]:
            raise AuthorityViolation("cohort mission/task binding cannot change")
        for field in ("required", "roster", "participantCap", "roundCap"):
            if nxt[field] != current[field]:
                raise AuthorityViolation("cohort quorum/roster/cap configuration is immutable after creation")
        if int(nxt["epoch"]) != int(current["epoch"]):
            raise AuthorityViolation("cohort snapshot persistence may not change deliberation epoch")
        if int(nxt["rounds"]) < int(current["rounds"]):
            raise AuthorityViolation("cohort round position may not regress")
        old_by_id = {c["contributionId"]: c for c in current.get("contributions") or []}
        new_by_id = {c["contributionId"]: c for c in nxt.get("contributions") or []}
        if not set(old_by_id) <= set(new_by_id):
            raise AuthorityViolation("cohort snapshot may not delete admitted contributions")
        for contribution_id, prior in old_by_id.items():
            if new_by_id[contribution_id] != prior:
                raise AuthorityViolation("cohort snapshot may not rewrite admitted contributions")
        for participant, cursor in (current.get("participantCursors") or {}).items():
            if int(nxt["participantCursors"].get(participant, 0)) < int(cursor):
                raise AuthorityViolation("cohort participant cursor may not regress")
        if nxt.get("latestSteer") != current.get("latestSteer"):
            raise AuthorityViolation("snapshot event may not rewrite steering state")
        prior_evidence = set(current.get("evidenceIds") or [])
        next_evidence = set(nxt.get("evidenceIds") or [])
        if not prior_evidence <= next_evidence:
            raise AuthorityViolation("snapshot event may not delete Cohort evidence links")
        if nxt.get("stoppingReason") != cls._derived_stopping_reason(nxt):
            raise AuthorityViolation("cohort stopping reason must be deterministically derived")
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
