"""Replay-fork provenance aggregate (CAPT-UPG-016).

A fork records where a new governed continuation was seeded from. It does not
copy or reactivate historical capability, approval, task, or execution state.
"""
from __future__ import annotations

from typing import Any, Dict


class ReplayForkAggregate(object):
    KIND = "replay_fork"
    OWNED_FIELDS = frozenset(
        {
            "replay_fork.sourceSequence",
            "replay_fork.sourceEventId",
            "replay_fork.sourceStateDigest",
            "replay_fork.sourceChainDigest",
            "replay_fork.reason",
            "replay_fork.createdAt",
            "replay_fork.historicalAuthorityReactivated",
            "replay_fork.state",
        }
    )
    REFERENCE_FIELDS = frozenset({"forkId", "newMissionId", "createdBy"})

    @staticmethod
    def stream_id(fork_id: str) -> str:
        return "replay_fork-" + fork_id

    @staticmethod
    def create(record: Dict[str, Any]) -> Dict[str, Any]:
        if not record.get("forkId"):
            raise ValueError("REPLAY_FORK_ID_REQUIRED")
        if int(record.get("sourceSequence", -1)) < 0:
            raise ValueError("REPLAY_FORK_SOURCE_SEQUENCE_INVALID")
        if not record.get("newMissionId"):
            raise ValueError("REPLAY_FORK_NEW_MISSION_REQUIRED")
        if not str(record.get("reason") or "").strip():
            raise ValueError("REPLAY_FORK_REASON_REQUIRED")
        if record.get("historicalAuthorityReactivated") is not False:
            raise ValueError("REPLAY_FORK_CANNOT_REACTIVATE_HISTORICAL_AUTHORITY")
        return {
            "forkId": str(record["forkId"]),
            "sourceSequence": int(record["sourceSequence"]),
            "sourceEventId": record.get("sourceEventId"),
            "sourceStateDigest": str(record["sourceStateDigest"]),
            "sourceChainDigest": str(record["sourceChainDigest"]),
            "newMissionId": str(record["newMissionId"]),
            "reason": str(record["reason"]),
            "createdBy": dict(record["createdBy"]),
            "createdAt": str(record["createdAt"]),
            "historicalAuthorityReactivated": False,
            "state": "created",
        }
