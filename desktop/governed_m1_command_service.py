"""Thin authenticated operator relay for governed Cohort steering.

All non-steering commands are delegated unchanged to RuntimeCommandService.
The steering command is admitted at the same authenticated transport boundary
and then delegated to the composition-owned canonical RuntimeService.
"""
from __future__ import annotations

from typing import Any, Dict

from capt_runtime.errors import CaptRuntimeError
from desktop.m1_command_service import CONTRACT_SCHEMA_VERSION, RuntimeCommandService


class GovernedRuntimeCommandService(RuntimeCommandService):
    """Adds the CAPT-UPG-011 command surface without adding authority."""

    def execute(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(cmd, dict) or cmd.get("op") != "steer_deliberation":
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

        payload = cmd.get("payload") or {}
        cohort_id = payload.get("cohortId")
        directive = payload.get("directive")
        if not cohort_id or not isinstance(directive, str) or not directive.strip():
            return self._receipt(
                cmd, status="rejected", classification="malformed",
                error=self._error_envelope(cmd, "malformed", "STEER_PAYLOAD_INVALID"),
            )

        metadata = self._operator_metadata(cmd)
        try:
            result = self.svc.steer_cohort(
                str(cohort_id), directive, payload.get("reason", "operator steering"), metadata
            )
            status = "idempotent" if result.get("status") == "idempotent" else "accepted"
            return self._receipt(
                cmd,
                status=status,
                classification="duplicate" if status == "idempotent" else "accepted",
                result={
                    "cohortId": result["cohortId"],
                    "epoch": result["epoch"],
                    "latestSteer": result.get("latestSteer"),
                },
                stream_id="cohort-" + str(cohort_id),
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
