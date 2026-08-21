"""Truthful Cohort Deliberation Chamber projections (CAPT-UPG-018).

This module is presentation-only. It consumes authoritative Cohort aggregate
state and computes a deterministic operator view. It cannot admit
contributions, decide authoritative stopping state, or mutate capability/runtime
state.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


_DEBT_OUTCOMES = frozenset({"ESCALATE", "REQUEST_EVIDENCE"})


def _contribution_sort_key(item: Mapping[str, Any]):
    return (
        int(item.get("epoch", 0)),
        int(item.get("round", 0)),
        int(item.get("cursor", 0)),
        str(item.get("contributionId") or ""),
    )


def project_cohort_chamber(state: Mapping[str, Any]) -> Dict[str, Any]:
    """Project one authoritative Cohort snapshot into truthful operator state."""
    cohort_id = str(state.get("cohortId") or "")
    if not cohort_id:
        raise ValueError("COHORT_CHAMBER_ID_REQUIRED")

    current_epoch = int(state.get("epoch", 0))
    current_round = int(state.get("rounds", 0))
    round_cap = int(state.get("roundCap", 0))
    required = sorted(str(v) for v in (state.get("required") or []))
    roster = sorted(str(v) for v in (state.get("roster") or []))
    declared_cursors = {
        str(k): int(v) for k, v in (state.get("participantCursors") or {}).items()
    }
    warnings: List[str] = []

    rows: List[Dict[str, Any]] = []
    current_epoch_rows: List[Dict[str, Any]] = []
    latest_current_round: Dict[str, Dict[str, Any]] = {}
    observed_cursors: Dict[str, int] = {}

    for raw in sorted((state.get("contributions") or []), key=_contribution_sort_key):
        contribution = {
            "contributionId": str(raw.get("contributionId") or ""),
            "participant": str(raw.get("participant") or ""),
            "epoch": int(raw.get("epoch", 0)),
            "round": int(raw.get("round", 0)),
            "outcome": str(raw.get("outcome") or ""),
            "cursor": int(raw.get("cursor", 0)),
            "sourceSequences": [int(v) for v in (raw.get("sourceSequences") or [])],
            "material": bool(raw.get("material", False)),
            "escalation": raw.get("escalation"),
        }
        participant = contribution["participant"]
        observed_cursors[participant] = max(
            observed_cursors.get(participant, 0), contribution["cursor"]
        )

        if contribution["epoch"] != current_epoch:
            temporal_class = "stale_epoch"
            counts_quorum = False
            counts_debt = False
        elif contribution["round"] < current_round:
            temporal_class = "prior_round_current_epoch"
            counts_quorum = False
            counts_debt = True
            current_epoch_rows.append(contribution)
        elif contribution["round"] == current_round:
            temporal_class = "current_round"
            counts_quorum = True
            counts_debt = True
            current_epoch_rows.append(contribution)
            prior = latest_current_round.get(participant)
            if prior is None or contribution["cursor"] > prior["cursor"]:
                latest_current_round[participant] = contribution
        else:
            # A future-round contribution should not normally survive Cohort
            # aggregate admission. Never use it for current quorum/debt.
            temporal_class = "future_round_current_epoch"
            counts_quorum = False
            counts_debt = False
            warnings.append(
                "future_round_contribution:%s" % contribution["contributionId"]
            )

        row = dict(contribution)
        row["temporalClass"] = temporal_class
        row["countsTowardCurrentQuorum"] = counts_quorum
        row["countsTowardCurrentDebt"] = counts_debt
        rows.append(row)

    for participant, observed in observed_cursors.items():
        declared = declared_cursors.get(participant)
        if declared is not None and declared < observed:
            warnings.append("participant_cursor_behind_contribution:%s" % participant)

    unresolved_dissent = sum(
        row["outcome"] == "DISSENT" and bool(row.get("material"))
        for row in current_epoch_rows
    )
    unresolved_escalation = sum(
        row["outcome"] == "ESCALATE" for row in current_epoch_rows
    )
    requested_evidence = sum(
        row["outcome"] == "REQUEST_EVIDENCE" for row in current_epoch_rows
    )
    stale_results = sum(row["temporalClass"] == "stale_epoch" for row in rows)
    debt = {
        "unresolvedDissent": unresolved_dissent,
        "unresolvedEscalation": unresolved_escalation,
        "requestedEvidence": requested_evidence,
        "staleResults": stale_results,
    }

    required_pass = sorted(
        participant
        for participant in required
        if participant in latest_current_round
        and latest_current_round[participant]["outcome"] == "PASS"
    )
    missing_required = sorted(set(required).difference(required_pass))
    has_current_debt = bool(
        unresolved_dissent or unresolved_escalation or requested_evidence
    )
    silence_quorum = not missing_required and not has_current_debt
    at_cap = round_cap > 0 and current_round + 1 >= round_cap
    if has_current_debt:
        projected_stopping: Optional[str] = "BOUNDED_INCOMPLETE" if at_cap else None
    elif silence_quorum:
        projected_stopping = "SILENCE_QUORUM"
    elif at_cap:
        projected_stopping = "BOUNDED_INCOMPLETE"
    else:
        projected_stopping = None

    recorded_stopping = state.get("stoppingReason")
    stopping_matches = recorded_stopping == projected_stopping
    if not stopping_matches:
        warnings.append("recorded_stopping_reason_differs_from_projection")

    participant_rows = []
    for participant in roster:
        latest = latest_current_round.get(participant)
        participant_rows.append(
            {
                "participant": participant,
                "required": participant in required,
                "cursor": declared_cursors.get(participant),
                "currentRoundContributionId": latest.get("contributionId") if latest else None,
                "currentRoundOutcome": latest.get("outcome") if latest else None,
            }
        )

    return {
        "schemaVersion": "1.0.0",
        "kind": "CohortDeliberationChamberProjection",
        "authority": "projection_only",
        "cohortId": cohort_id,
        "missionId": state.get("missionId"),
        "taskId": state.get("taskId"),
        "currentEpoch": current_epoch,
        "currentRound": current_round,
        "roundCap": round_cap,
        "participantCap": int(state.get("participantCap", 0)),
        "required": required,
        "roster": roster,
        "participantCursors": declared_cursors,
        "participants": participant_rows,
        "contributions": rows,
        "cognitiveDebt": debt,
        "requiredPassParticipants": required_pass,
        "missingRequiredPassParticipants": missing_required,
        "projectedSilenceQuorum": silence_quorum,
        "projectedStoppingReason": projected_stopping,
        "recordedStoppingReason": recorded_stopping,
        "stoppingReasonMatchesProjection": stopping_matches,
        "evidenceIds": list(state.get("evidenceIds") or []),
        "latestSteer": dict(state["latestSteer"]) if state.get("latestSteer") else None,
        "integrityWarnings": sorted(set(warnings)),
        "semantics": {
            "proposalTextPersisted": False,
            "modelIdentityPersisted": False,
            "confidenceScoreProvided": False,
            "quorumIsTruthClaim": False,
        },
    }


def render_cohort_chamber_text(view: Mapping[str, Any]) -> str:
    """Deterministic human-readable headless rendering of a chamber projection."""
    lines = [
        "Cohort Deliberation Chamber (projection only)",
        "cohort=%s mission=%s task=%s" % (
            view.get("cohortId"), view.get("missionId"), view.get("taskId")
        ),
        "epoch=%s round=%s/%s recorded=%s projected=%s" % (
            view.get("currentEpoch"),
            view.get("currentRound"),
            view.get("roundCap"),
            view.get("recordedStoppingReason"),
            view.get("projectedStoppingReason"),
        ),
        "required_pass=%s missing_required=%s" % (
            ",".join(view.get("requiredPassParticipants") or []) or "<none>",
            ",".join(view.get("missingRequiredPassParticipants") or []) or "<none>",
        ),
        "debt=%s" % dict(view.get("cognitiveDebt") or {}),
    ]
    for row in view.get("contributions") or []:
        lines.append(
            "%s e%s/r%s %s %s cursor=%s material=%s escalation=%s [%s]" % (
                row.get("contributionId"), row.get("epoch"), row.get("round"),
                row.get("participant"), row.get("outcome"), row.get("cursor"),
                row.get("material"), row.get("escalation"), row.get("temporalClass"),
            )
        )
    if view.get("integrityWarnings"):
        lines.append("warnings=%s" % ",".join(view["integrityWarnings"]))
    return "\n".join(lines)
