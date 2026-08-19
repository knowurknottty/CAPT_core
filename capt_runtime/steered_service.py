"""Governed operator-steering extension for the canonical CAPT RuntimeService.

Selected by the composition root for CAPT-UPG-011. This extends, rather than
replaces, the existing governed RuntimeService and writes steering transitions
to the authoritative Cohort EventStore stream.
"""
from __future__ import annotations

from typing import Any, Dict

from . import commands
from .aggregates.cohort_state import CohortAggregate
from .authority import require_authority
from .errors import IdempotencyConflict
from .governed_service import GovernedRuntimeService
from .store import AppendRequest


class SteeredRuntimeService(GovernedRuntimeService):
    """Canonical governed service with durable human Cohort steering."""

    def steer_cohort(
        self,
        cohort_id: str,
        directive: str,
        reason: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        require_authority("steer_cohort", metadata["actor"]["kind"])
        stream = CohortAggregate.stream_id(cohort_id)

        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            offered = metadata.get("operationFingerprint")
            if offered and prior["operation_fingerprint"] != offered:
                raise IdempotencyConflict("cohort steering idempotency conflict")
            current = self.store.require_state(stream)
            return {
                "status": "idempotent",
                "cohortId": cohort_id,
                "epoch": current["epoch"],
                "latestSteer": current.get("latestSteer"),
                "cohort": current,
            }

        expected = self.store.aggregate_version(stream)
        current = self.store.require_state(stream)
        state = CohortAggregate.steer(
            current,
            directive,
            reason or "operator steering",
            metadata["actor"]["actorId"],
            metadata["issuedAt"],
        )
        steer = dict(state["latestSteer"])
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="CohortSteered",
            payload={
                "eventType": "CohortSteered",
                "cohortId": cohort_id,
                "steer": steer,
            },
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=state["missionId"],
            task_id=state["taskId"],
        )
        result = self._commit(
            [AppendRequest(stream, CohortAggregate.KIND, expected, event, state)],
            metadata,
        )
        return {
            **result,
            "cohortId": cohort_id,
            "epoch": state["epoch"],
            "latestSteer": steer,
            "cohort": state,
        }
