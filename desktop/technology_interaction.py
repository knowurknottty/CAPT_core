"""CAPT authority for local technology-interaction permits.

Permits are deliberately ephemeral and monotonic-time bounded. Durable state
records only safe binding/digest metadata so a restart fails closed instead of
resurrecting execution authority.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict

from capt_runtime import commands, contracts
from capt_runtime.aggregates import HumanApprovalAggregate
from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


_LOW_RISK = frozenset({"observe", "reversible_local", "navigation"})
_CONSEQUENTIAL = frozenset(
    {"external_write", "credential_or_secret", "financial_or_legal"}
)
_ALLOWED_RISKS = _LOW_RISK | _CONSEQUENTIAL
_ALLOWED_PHASES = ("attempted", "transport", "observed")


def _require_digest(name: str, value: Any) -> str:
    text = str(value or "")
    if len(text) != 71 or not text.startswith("sha256:"):
        raise AuthorityViolation(f"TIA_{name.upper()}_DIGEST_REQUIRED")
    try:
        int(text[7:], 16)
    except ValueError as exc:
        raise AuthorityViolation(f"TIA_{name.upper()}_DIGEST_REQUIRED") from exc
    return text


def _parse_instant(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise AuthorityViolation("TIA_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None:
        raise AuthorityViolation("TIA_TIMESTAMP_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _expires_at(issued_at: str, seconds: int = 300) -> str:
    parsed = _parse_instant(issued_at)
    return (parsed + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_safe_identifier(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise AuthorityViolation(f"TIA_{name}_INVALID")
    text = value.strip()
    if not text or len(text) > 128 or text != value:
        raise AuthorityViolation(f"TIA_{name}_INVALID")
    if any(ord(ch) < 33 or ord(ch) == 127 for ch in text):
        raise AuthorityViolation(f"TIA_{name}_INVALID")
    return text


class TechnologyInteractionAuthority:
    """Issue and consume target-scoped, one-use technology permits."""

    def __init__(
        self,
        store: EventStore,
        runtime_service: RuntimeService,
        *,
        operator_id: str,
        session_id: str,
        monotonic: Callable[[], float] = time.monotonic,
        permit_ttl_seconds: float = 30.0,
    ) -> None:
        self.store = store
        self.runtime = runtime_service
        self.operator_id = str(operator_id)
        self.session_id = str(session_id)
        self._monotonic = monotonic
        self._permit_ttl = float(permit_ttl_seconds)
        self._permits: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()

    def _state_root_digest(self) -> str:
        return contracts.digest({"ledgerPath": str(Path(self.store.path).resolve())})

    def _binding(self, request: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        interaction_id = _require_safe_identifier(
            "INTERACTION_ID", request.get("interactionId")
        )
        technology = _require_safe_identifier("TECHNOLOGY", request.get("technology"))
        attempt_id = _require_safe_identifier(
            "AUTHORIZATION_ATTEMPT_ID", request.get("authorizationAttemptId")
        )
        risk = str(request.get("riskClass") or "")
        if risk not in _ALLOWED_RISKS:
            raise AuthorityViolation("TIA_RISK_CLASS_INVALID")
        capabilities = request.get("capabilities")
        if not isinstance(capabilities, list) or not capabilities:
            raise AuthorityViolation("TIA_CAPABILITIES_REQUIRED")
        if any(not isinstance(item, str) or not item.strip() or item != item.strip() for item in capabilities):
            raise AuthorityViolation("TIA_CAPABILITIES_INVALID")
        normalized_capabilities = sorted(set(capabilities))
        observation_scope = request.get("observationScope")
        if not isinstance(observation_scope, dict):
            raise AuthorityViolation("TIA_OBSERVATION_SCOPE_REQUIRED")
        binding = {
            "interactionId": interaction_id,
            "actionDigest": _require_digest("action", request.get("actionDigest")),
            "technology": technology,
            "targetDigest": _require_digest("target", request.get("targetDigest")),
            "capabilities": normalized_capabilities,
            "observationScopeDigest": contracts.digest(observation_scope),
            "riskClass": risk,
            "operatorId": self.operator_id,
            "sessionId": self.session_id,
            "stateRootDigest": self._state_root_digest(),
        }
        return binding, attempt_id

    def _identity_digest(self, interaction_id: str) -> str:
        return contracts.digest(
            {
                "interactionId": interaction_id,
                "operatorId": self.operator_id,
                "sessionId": self.session_id,
            }
        )

    def _request_id(self, interaction_id: str) -> str:
        return "tia-approval-" + self._identity_digest(interaction_id)[7:31]

    def _permit_id(self, interaction_id: str) -> str:
        return "tia-permit-" + self._identity_digest(interaction_id)[7:31]

    @staticmethod
    def _binding_matches(state: Dict[str, Any], binding: Dict[str, Any]) -> bool:
        scope = state.get("scope") or {}
        stored = scope.get("technologyInteraction")
        return isinstance(stored, dict) and contracts.digest(stored) == contracts.digest(binding)

    def _approval_decision_session(self, request_id: str) -> str | None:
        stream = HumanApprovalAggregate.stream_id(request_id)
        for event in reversed(self.store.read_stream(stream)):
            payload = event.get("payload") or {}
            if payload.get("eventType") == "HumanApprovalDecided":
                decision = payload.get("decision") or {}
                session_id = decision.get("sessionId")
                return str(session_id) if session_id else None
        return None

    def _approval_metadata(
        self, meta: Dict[str, Any], request_id: str, binding: Dict[str, Any]
    ) -> Dict[str, Any]:
        return commands.command(
            command_id=meta["commandId"] + ":tia-approval",
            idempotency_key="idem-" + request_id,
            operation_fingerprint=commands.fingerprint(
                "request_human_approval", {"requestId": request_id, "binding": binding}
            ),
            correlation_id=meta["correlationId"],
            actor_id="tia-execution",
            actor_kind="execution_plane",
            issued_at=meta["issuedAt"],
            replay_policy="never",
        )

    def _ensure_approval(
        self, binding: Dict[str, Any], meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        request_id = self._request_id(binding["interactionId"])
        stream = HumanApprovalAggregate.stream_id(request_id)
        state = self.store.load_state(stream)
        if state is not None:
            if not self._binding_matches(state, binding):
                raise AuthorityViolation("TIA_APPROVAL_BINDING_MISMATCH")
            return state

        context_hash = self._identity_digest(binding["interactionId"])[7:23]
        request = {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "missionId": "tia-session-" + context_hash,
            "taskId": "tia-interaction-" + context_hash,
            "requestedCapability": "cap.tia." + binding["technology"],
            "resource": binding["targetDigest"],
            "operation": "TechnologyInteraction",
            "scope": {"technologyInteraction": binding},
            "riskClassification": "consequential",
            "policyReason": "Consequential technology interaction requires exact human approval.",
            "requestedBy": {"actorId": "tia-execution", "kind": "execution_plane"},
            "expiresAt": _expires_at(meta["issuedAt"]),
            "remainingUses": 1,
            "correlationId": meta["correlationId"],
            "createdAt": meta["issuedAt"],
        }
        self.runtime.request_human_approval(
            request, self._approval_metadata(meta, request_id, binding)
        )
        return self.store.require_state(stream)

    def _durable_permit(self, permit_id: str) -> Dict[str, Any] | None:
        result = self.store.idempotent_result(permit_id)
        return result if isinstance(result, dict) else None

    def _issue_permit(
        self,
        binding: Dict[str, Any],
        *,
        approval_request_id: str | None,
        authorization_attempt_id: str,
    ) -> Dict[str, Any]:
        permit_id = self._permit_id(binding["interactionId"])
        fingerprint = commands.fingerprint("technology_interaction_permit", binding)
        existing = self._permits.get(permit_id)
        if existing is not None:
            if existing["bindingDigest"] != contracts.digest(binding):
                raise AuthorityViolation("TIA_PERMIT_BINDING_MISMATCH")
            if existing["phase"] == "authorized" and self._monotonic() <= existing["expiresMonotonic"]:
                return dict(existing["public"])
            return {}

        prior = self._durable_permit(permit_id)
        if prior is not None:
            return {}
        self.store.claim_command(permit_id, fingerprint, "cmd-" + permit_id)
        now = self._monotonic()
        public = {
            "permitId": permit_id,
            "interactionId": binding["interactionId"],
            "actionDigest": binding["actionDigest"],
            "technology": binding["technology"],
            "targetDigest": binding["targetDigest"],
            "capabilityDigest": contracts.digest(binding["capabilities"]),
            "observationScopeDigest": binding["observationScopeDigest"],
            "riskClass": binding["riskClass"],
            "authorizationAttemptId": authorization_attempt_id,
            "operatorId": self.operator_id,
            "sessionId": self.session_id,
            "stateRootDigest": binding["stateRootDigest"],
            "approvalRequestId": approval_request_id,
            "remainingUses": 1,
        }
        record = {
            "public": public,
            "bindingDigest": contracts.digest(binding),
            "fingerprint": fingerprint,
            "expiresMonotonic": now + self._permit_ttl,
            "phase": "authorized",
            "remainingUses": 1,
            "terminal": False,
        }
        self._permits[permit_id] = record
        self.store.complete_claimed_command(
            permit_id,
            fingerprint,
            {
                "status": "authorized",
                "phase": "authorized",
                "permit": public,
                "remainingUses": 1,
                "terminal": False,
            },
        )
        return dict(public)

    def authorize(
        self, request: Dict[str, Any], meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Authorize one exact interaction or return the approval needed for it."""
        binding, authorization_attempt_id = self._binding(request)
        with self._lock:
            if binding["riskClass"] in _CONSEQUENTIAL:
                approval = self._ensure_approval(binding, meta)
                state = approval.get("state")
                if state == "requested":
                    return {
                        "status": "approval_required",
                        "requestId": approval["requestId"],
                        "interactionId": binding["interactionId"],
                        "actionDigest": binding["actionDigest"],
                        "authorizationAttemptId": authorization_attempt_id,
                    }
                if state != "approved":
                    raise AuthorityViolation("TIA_APPROVAL_NOT_APPROVED")
                if str(approval.get("operatorId") or "") != self.operator_id:
                    raise AuthorityViolation("TIA_APPROVAL_OPERATOR_MISMATCH")
                if self._approval_decision_session(str(approval["requestId"])) != self.session_id:
                    raise AuthorityViolation("TIA_APPROVAL_SESSION_MISMATCH")
                if _parse_instant(approval.get("expiresAt")) < _parse_instant(meta["issuedAt"]):
                    raise AuthorityViolation("TIA_APPROVAL_EXPIRED")
                approval_request_id = str(approval["requestId"])
            else:
                approval_request_id = None

            permit = self._issue_permit(
                binding,
                approval_request_id=approval_request_id,
                authorization_attempt_id=authorization_attempt_id,
            )
            if not permit:
                return {
                    "status": "reconciliation_required",
                    "interactionId": binding["interactionId"],
                    "actionDigest": binding["actionDigest"],
                }
            return {"status": "authorized", "permit": permit}

    def _require_live_permit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        permit_id = str(payload.get("permitId") or "")
        if not permit_id:
            raise AuthorityViolation("TIA_PERMIT_ID_REQUIRED")
        record = self._permits.get(permit_id)
        if record is not None:
            public = record["public"]
        else:
            durable = self._durable_permit(permit_id)
            public = durable.get("permit") if durable else None
            if not isinstance(public, dict):
                raise AuthorityViolation("TIA_PERMIT_UNKNOWN")
        if public.get("operatorId") != self.operator_id:
            raise AuthorityViolation("TIA_PERMIT_OPERATOR_MISMATCH")
        if public.get("sessionId") != self.session_id:
            raise AuthorityViolation("TIA_PERMIT_SESSION_MISMATCH")
        if public.get("interactionId") != str(payload.get("interactionId") or ""):
            raise AuthorityViolation("TIA_PERMIT_INTERACTION_MISMATCH")
        if public.get("targetDigest") != _require_digest("target", payload.get("targetDigest")):
            raise AuthorityViolation("TIA_PERMIT_TARGET_MISMATCH")
        if public.get("actionDigest") != _require_digest("action", payload.get("actionDigest")):
            raise AuthorityViolation("TIA_PERMIT_ACTION_MISMATCH")
        if record is None:
            raise AuthorityViolation("TIA_PERMIT_NOT_ACTIVE_RECONCILIATION_REQUIRED")
        return record

    def record_outcome(
        self, payload: Dict[str, Any], meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Consume a permit at dispatch-attempt and durably record safe phase digests."""
        phase = str(payload.get("phase") or "")
        if phase not in _ALLOWED_PHASES:
            raise AuthorityViolation("TIA_OUTCOME_PHASE_INVALID")
        outcome_digest = _require_digest("outcome", payload.get("outcomeDigest"))
        allowed = {
            "permitId", "interactionId", "actionDigest", "targetDigest", "phase",
            "outcomeDigest", "transportDigest", "observationDigest", "errorDigest",
            "adapterId", "route",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise AuthorityViolation("TIA_OUTCOME_UNSAFE_FIELD_REJECTED")
        safe_metadata: Dict[str, str] = {}
        for key, label in (
            ("transportDigest", "transport"),
            ("observationDigest", "observation"),
            ("errorDigest", "error"),
        ):
            if key in payload:
                safe_metadata[key] = _require_digest(label, payload[key])
        for key, label in (("adapterId", "ADAPTER_ID"), ("route", "ROUTE")):
            if key in payload:
                safe_metadata[key] = _require_safe_identifier(label, payload[key])

        with self._lock:
            record = self._require_live_permit(payload)
            if phase == "attempted":
                if record["phase"] != "authorized" or record["remainingUses"] != 1:
                    raise AuthorityViolation("TIA_PERMIT_ALREADY_CONSUMED")
                if self._monotonic() > record["expiresMonotonic"]:
                    record["phase"] = "expired"
                    record["terminal"] = True
                    self._persist_phase(record, outcome_digest=None)
                    raise AuthorityViolation("TIA_PERMIT_EXPIRED")
                record["phase"] = "attempted"
                record["remainingUses"] = 0
            elif phase == "transport":
                if record["phase"] != "attempted":
                    raise AuthorityViolation("TIA_OUTCOME_PHASE_ORDER_INVALID")
                record["phase"] = "transport"
            elif phase == "observed":
                if record["phase"] != "transport":
                    raise AuthorityViolation("TIA_OUTCOME_PHASE_ORDER_INVALID")
                record["phase"] = "observed"
                record["terminal"] = True

            record["outcomeDigest"] = outcome_digest
            for key, value in safe_metadata.items():
                record[key] = value
            self._persist_phase(record, outcome_digest=outcome_digest)
            return {
                "status": "recorded",
                "permitId": record["public"]["permitId"],
                "interactionId": record["public"]["interactionId"],
                "phase": record["phase"],
                "outcomeDigest": outcome_digest,
                "remainingUses": record["remainingUses"],
                "terminal": bool(record["terminal"]),
            }

    def _persist_phase(
        self, record: Dict[str, Any], *, outcome_digest: str | None
    ) -> None:
        safe = {
            "status": "recorded" if record["phase"] != "expired" else "expired",
            "phase": record["phase"],
            "permit": record["public"],
            "remainingUses": record["remainingUses"],
            "terminal": bool(record["terminal"]),
            "outcomeDigest": outcome_digest,
        }
        for key in (
            "transportDigest", "observationDigest", "errorDigest", "adapterId", "route"
        ):
            if key in record:
                safe[key] = record[key]
        self.store.complete_claimed_command(
            record["public"]["permitId"], record["fingerprint"], safe
        )
