"""Authenticated operator relay for CAPT-UPG-016 replay-fork intent.

The relay authenticates/binds the operator envelope and forwards a high-level
ReplayForkIntent. RuntimeService alone reconstructs history, builds MissionSpec,
and commits authoritative fork + mission state.
"""
from __future__ import annotations

from typing import Any, Dict

from capt_runtime.errors import CaptRuntimeError
from desktop.lease_command_service import LeaseRuntimeCommandService
from desktop.m1_command_service import CONTRACT_SCHEMA_VERSION


class ReplayRuntimeCommandService(LeaseRuntimeCommandService):
    def execute(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(cmd, dict) or cmd.get("op") != "create_replay_fork":
            return super().execute(cmd)

        required = (
            "commandId", "operatorId", "sessionId", "schemaVersion",
            "correlationId", "idempotencyKey", "timestamp", "op", "payload",
        )
        if any(field not in cmd for field in required):
            return self._receipt(
                cmd, status="rejected", classification="malformed",
                error=self._error_envelope(cmd, "malformed", "ENVELOPE_MALFORMED"),
            )
        if cmd.get("schemaVersion") != CONTRACT_SCHEMA_VERSION:
            return self._receipt(
                cmd, status="rejected", classification="malformed",
                error=self._error_envelope(cmd, "malformed", "ENVELOPE_MALFORMED"),
            )
        if cmd.get("operatorId") != self.operator_id or cmd.get("sessionId") != self.session_id:
            return self._receipt(
                cmd, status="rejected", classification="unauthorized",
                error=self._error_envelope(cmd, "unauthorized", "ENVELOPE_UNAUTHORIZED"),
            )

        metadata = self._operator_metadata(cmd)
        try:
            result = self.svc.create_replay_fork_from_intent(cmd.get("payload") or {}, metadata)
            fork = result["fork"]
            status = "idempotent" if result.get("status") == "idempotent" else "accepted"
            return self._receipt(
                cmd,
                status=status,
                classification="duplicate" if status == "idempotent" else "accepted",
                result={
                    "forkId": fork["forkId"],
                    "sourceSequence": fork["sourceSequence"],
                    "sourceStateDigest": fork["sourceStateDigest"],
                    "sourceChainDigest": fork["sourceChainDigest"],
                    "newMissionId": fork["newMissionId"],
                    "historicalAuthorityReactivated": False,
                },
                stream_id="replay_fork-" + str(fork["forkId"]),
            )
        except CaptRuntimeError as exc:
            classification = getattr(exc, "category", "internal_failure")
            return self._receipt(
                cmd,
                status="rejected",
                classification=classification,
                error=self._error_envelope(
                    cmd, classification, str(exc) if str(exc) else type(exc).__name__.upper()
                ),
                detail=str(exc),
            )
        except Exception as exc:  # transport presentation only
            return self._receipt(
                cmd,
                status="rejected",
                classification="internal_failure",
                error=self._error_envelope(cmd, "internal_failure", type(exc).__name__.upper()),
                detail=str(exc)[:240],
            )
