"""Authenticated operator relay for capability/lease revocation (CAPT-UPG-015).

This surface does not own capability authority. It binds the authenticated
operator identity to a contract-valid CapabilityRevocation and delegates to the
composition-owned RuntimeService.revoke() transition.
"""
from __future__ import annotations

from typing import Any, Dict

from capt_runtime.errors import CaptRuntimeError
from desktop.governed_m1_command_service import GovernedRuntimeCommandService
from desktop.m1_command_service import CONTRACT_SCHEMA_VERSION


class LeaseRuntimeCommandService(GovernedRuntimeCommandService):
    """Adds authenticated revoke_capability while delegating all other ops."""

    def execute(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(cmd, dict) or cmd.get("op") != "revoke_capability":
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
        grant_id = payload.get("grantId")
        target_kind = payload.get("targetKind")
        target_id = payload.get("targetId")
        reason = payload.get("reason")
        if target_kind == "grant" and not target_id:
            target_id = grant_id
        if target_kind == "lease" and not target_id:
            target_id = payload.get("leaseId")
        if (
            not grant_id
            or target_kind not in ("grant", "lease")
            or not target_id
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            return self._receipt(
                cmd, status="rejected", classification="malformed",
                error=self._error_envelope(cmd, "malformed", "REVOCATION_PAYLOAD_INVALID"),
            )

        meta = self._operator_metadata(cmd)
        prior = self.store.find_idempotent(cmd["idempotencyKey"])
        if prior is not None:
            if prior["operation_fingerprint"] != meta["operationFingerprint"]:
                return self._receipt(
                    cmd, status="rejected", classification="conflict",
                    error=self._error_envelope(cmd, "conflict", "IDEMPOTENCY_CONFLICT"),
                )
            state = self.store.load_state("capability-" + str(grant_id))
            return self._receipt(
                cmd,
                status="idempotent",
                classification="duplicate",
                result={"grantId": grant_id, "capability": state},
                stream_id="capability-" + str(grant_id),
            )

        revocation = {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "revocationId": payload.get("revocationId") or ("rev-" + cmd["commandId"]),
            "targetKind": target_kind,
            "targetId": str(target_id),
            "reason": reason.strip(),
            "revokedBy": {"actorId": self.operator_id, "kind": "human"},
            "revokedAt": meta["issuedAt"],
        }
        try:
            result = self.svc.revoke(str(grant_id), revocation, meta)
            state = self.store.require_state("capability-" + str(grant_id))
            return self._receipt(
                cmd,
                status="accepted",
                classification="accepted",
                result={
                    "grantId": grant_id,
                    "revocation": revocation,
                    "capability": state,
                    "runtimeResult": result,
                },
                stream_id="capability-" + str(grant_id),
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
        except Exception as exc:  # presentation boundary only
            return self._receipt(
                cmd,
                status="rejected",
                classification="internal_failure",
                error=self._error_envelope(cmd, "internal_failure", type(exc).__name__.upper()),
                detail=str(exc)[:240],
            )
