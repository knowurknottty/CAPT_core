"""Governed execution boundary for CAPT tools.

ToolBroker owns admission, durable execution intent, capability revalidation,
reservation settlement, adapter dispatch, exact settled replay, and restart
reconciliation. Adapters never receive authority merely by being registered.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any, Callable, Dict, Iterable

from . import commands
from .aggregates.capability import CapabilityAggregate
from .aggregates.tool_execution import TERMINAL_STATES, ToolExecutionAggregate
from .contracts import digest, require
from .errors import (
    AuthorityViolation,
    CapabilityDenied,
    IdempotencyConflict,
    IntegrityViolation,
)
from .services import RuntimeService
from .tools.registry import ToolRegistry
from .world_receipt import (
    build_effect_intent,
    receipt_required,
    receipt_side_effect_identity,
    timestamp_at_or_before,
    verify_world_receipt,
)


class ToolBrokerError(RuntimeError):
    pass


class ToolUnavailable(ToolBrokerError):
    pass


def _stable_id(prefix: str, material: str) -> str:
    return prefix + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def tool_request_fingerprint(request: Dict[str, Any]) -> str:
    """Recompute semantic request identity instead of trusting caller digest."""
    semantic = {
        key: deepcopy(request.get(key))
        for key in (
            "toolId", "operation", "arguments", "consequential", "grantId",
            "leaseId", "backendId", "targetIdentity", "filesystemScope",
            "replayPolicy",
        )
    }
    return commands.fingerprint("run_tool", semantic)


def _output_items(value: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    output = [deepcopy(item) for item in value]
    for item in output:
        require("ToolArgument", item)
    return output


class ToolBroker:
    def __init__(
        self,
        runtime: RuntimeService,
        registry: ToolRegistry,
        *,
        now: Callable[[], str],
    ) -> None:
        self.runtime = runtime
        self.store = runtime.store
        self.registry = registry
        self._now = now

    @staticmethod
    def execution_id(idempotency_key: str) -> str:
        return _stable_id("tool-exec-", idempotency_key)

    def metadata(self, execution_id: str, stage: str) -> Dict[str, Any]:
        command_id = _stable_id("toolcmd-", execution_id + ":" + stage)
        return commands.command(
            command_id=command_id,
            idempotency_key=_stable_id("toolidem-", execution_id + ":" + stage),
            operation_fingerprint=commands.fingerprint(
                "tool_execution_" + stage, {"toolExecutionId": execution_id}
            ),
            correlation_id=_stable_id("toolcorr-", execution_id),
            actor_id="tool-broker",
            actor_kind="execution_plane",
            issued_at=self._now(),
        )

    def _validate_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        require("ToolRequest", request)
        expected_fingerprint = tool_request_fingerprint(request)
        if request["operationFingerprint"] != expected_fingerprint:
            raise IntegrityViolation("ToolRequest operationFingerprint does not match semantic request")
        if request.get("reservationId") is not None:
            raise AuthorityViolation("caller may not supply a capability reservationId")

        registration = self.registry.require(request["toolId"])
        descriptor = registration["descriptor"]
        if request["operation"] not in descriptor["operations"]:
            raise AuthorityViolation(
                f"operation {request['operation']} is not declared by tool {request['toolId']}"
            )
        backend_id = request.get("backendId")
        if backend_id not in descriptor["terminalBackends"]:
            raise AuthorityViolation(
                f"backend {backend_id!r} is not admitted for tool {request['toolId']}"
            )
        readiness = self.registry.readiness(request["toolId"])
        if readiness["status"] != "available":
            raise ToolUnavailable(
                f"tool {request['toolId']} readiness={readiness['status']}: {readiness['reason']}"
            )
        effect_class = self.registry.effect_class(request["toolId"], request["operation"])
        consequential = effect_class != "pure_read_only"
        if bool(request["consequential"]) != consequential:
            raise AuthorityViolation(
                f"consequential flag disagrees with effect class {effect_class}"
            )
        if request["operation"] in descriptor["requiredCapabilities"]:
            if not request.get("grantId") or not request.get("leaseId"):
                raise CapabilityDenied(
                    "tool operation requires a bound grant and live lease",
                    request.get("leaseId"),
                )
        return registration

    def _effect_expiry(self, request: Dict[str, Any]) -> str:
        """Bind EffectIntent lifetime to the authoritative capability lease."""
        grant_id = request.get("grantId")
        lease_id = request.get("leaseId")
        if not grant_id or not lease_id:
            raise CapabilityDenied(
                "WORLD_RECEIPT_EFFECT_LEASE_REQUIRED", request.get("leaseId")
            )
        state = self.store.load_state(CapabilityAggregate.stream_id(grant_id))
        lease = (state or {}).get("lease") or {}
        if lease.get("leaseId") != lease_id:
            raise CapabilityDenied("WORLD_RECEIPT_EFFECT_LEASE_NOT_ACTIVE", lease_id)
        expires_at = lease.get("validUntil")
        if not expires_at:
            raise CapabilityDenied("WORLD_RECEIPT_EFFECT_LEASE_EXPIRY_REQUIRED", lease_id)
        return str(expires_at)

    def build_execution(
        self, request: Dict[str, Any], *, operator_id: str, session_id: str
    ) -> Dict[str, Any]:
        registration = self._validate_request(request)
        descriptor = registration["descriptor"]
        adapter = registration["adapter"]
        execution_id = self.execution_id(request["idempotencyKey"])
        effect_intent = None
        if receipt_required(descriptor, request["operation"]):
            prepare_effect = getattr(adapter, "prepare_effect", None)
            if not callable(prepare_effect):
                raise AuthorityViolation("WORLD_RECEIPT_PREPARE_UNSUPPORTED")
            preparation = prepare_effect(deepcopy(request))
            effect_intent = build_effect_intent(
                request, principal_id=operator_id, preparation=preparation,
                expires_at=self._effect_expiry(request),
            )
        execution = {
            "schemaVersion": "1.0.0",
            "toolExecutionId": execution_id,
            "toolRequestId": request["toolRequestId"],
            "operatorId": operator_id,
            "sessionId": session_id,
            "toolId": request["toolId"],
            "operation": request["operation"],
            "operationFingerprint": request["operationFingerprint"],
            "descriptorDigest": registration["descriptorDigest"],
            "adapterId": getattr(adapter, "adapter_id", "adapter-" + descriptor["toolId"]),
            "backendId": request.get("backendId"),
            "effectClass": self.registry.effect_class(request["toolId"], request["operation"]),
            "consequential": request["consequential"],
            "grantId": request.get("grantId"),
            "leaseId": request.get("leaseId"),
            "reservationId": None,
            "state": "prepared",
            "dispatchBoundary": "not_started",
            "result": None,
            "resultDigest": None,
            "sideEffectIdentity": None,
            "effectIntent": effect_intent,
            "worldReceipt": None,
            "settlementStatus": "not_settled",
            "reconciliationReason": None,
            "preparedAt": self._now(),
            "updatedAt": self._now(),
        }
        require("ToolExecution", execution)
        return execution

    @staticmethod
    def _scope_for(request: Dict[str, Any]) -> Dict[str, Any]:
        filesystem_scope = request.get("filesystemScope")
        if filesystem_scope:
            return {"kind": "filesystem", "rootPath": filesystem_scope, "recursive": True}
        return {"kind": "tool", "toolIds": [request["toolId"]]}

    def _result_from_adapter(
        self, request: Dict[str, Any], adapter_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        status = adapter_result.get("status")
        if status not in {"succeeded", "failed", "indeterminate", "denied"}:
            raise ValueError(f"adapter returned invalid status: {status!r}")
        output = _output_items(adapter_result.get("output", []))
        result = {
            "schemaVersion": "1.0.0",
            "toolResultId": _stable_id("tool-result-", request["idempotencyKey"]),
            "toolRequestId": request["toolRequestId"],
            "status": status,
            "output": output,
            "exitCode": adapter_result.get("exitCode"),
            "outputDigest": digest(output),
            "sideEffectIdentity": adapter_result.get("sideEffectIdentity"),
            "error": adapter_result.get("error"),
            "completedAt": self._now(),
        }
        require("ToolResult", result)
        return result

    def _indeterminate_result(
        self,
        tool_request_id: str,
        material: str,
        reason: str,
        *,
        side_effect_identity: str | None = None,
    ) -> Dict[str, Any]:
        output = [{"kind": "string", "name": "reconciliation", "value": reason[:16384]}]
        result = {
            "schemaVersion": "1.0.0",
            "toolResultId": _stable_id("tool-result-", material),
            "toolRequestId": tool_request_id,
            "status": "indeterminate",
            "output": output,
            "exitCode": None,
            "outputDigest": digest(output),
            "sideEffectIdentity": side_effect_identity,
            "error": None,
            "completedAt": self._now(),
        }
        require("ToolResult", result)
        return result

    def _reservation(self, request: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "reservationId": _stable_id("tool-res-", execution_id),
            "leaseId": request["leaseId"],
            "operation": request["operation"],
            "operationFingerprint": request["operationFingerprint"],
            "idempotencyKey": _stable_id("tool-use-", execution_id),
            "state": "open",
            "reservedAt": self._now(),
        }

    def _consumption(
        self,
        execution_id: str,
        reservation_id: str,
        lease_id: str,
        outcome: str,
        side_effect_identity: Any,
    ) -> Dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "consumptionId": _stable_id("tool-consume-", execution_id),
            "reservationId": reservation_id,
            "leaseId": lease_id,
            "outcome": outcome,
            "sideEffectIdentity": (
                str(side_effect_identity)[:1024] if side_effect_identity is not None else None
            ),
            "finalizedAt": self._now(),
        }

    @staticmethod
    def _replay_projection(state: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(state.get("result"))
        if result is None:
            raise IntegrityViolation("terminal ToolExecution is missing durable ToolResult")
        return {
            "toolExecutionId": state["toolExecutionId"],
            "status": result["status"],
            "result": result,
            "state": state["state"],
            "replayed": True,
        }

    def _denied_result(self, request: Dict[str, Any], reason: str) -> Dict[str, Any]:
        output = [{"kind": "string", "name": "denial", "value": reason[:16384]}]
        result = {
            "schemaVersion": "1.0.0",
            "toolResultId": _stable_id("tool-result-", request["idempotencyKey"]),
            "toolRequestId": request["toolRequestId"],
            "status": "denied",
            "output": output,
            "exitCode": None,
            "outputDigest": digest(output),
            "sideEffectIdentity": None,
            "error": None,
            "completedAt": self._now(),
        }
        require("ToolResult", result)
        return result

    def _transition_terminal(
        self,
        execution_id: str,
        from_state: str,
        result: Dict[str, Any],
        *,
        reconciliation_reason: str | None = None,
        world_receipt: Dict[str, Any] | None = None,
        reservation_id: str | None = None,
    ) -> Dict[str, Any]:
        result_digest = digest(result)
        if result["status"] == "indeterminate":
            patch = {
                "result": result,
                "resultDigest": result_digest,
                "sideEffectIdentity": result.get("sideEffectIdentity"),
                "settlementStatus": "reconciliation_required",
                "reconciliationReason": reconciliation_reason or "external effect is indeterminate",
                "worldReceipt": world_receipt,
            }
            if reservation_id is not None:
                patch["reservationId"] = reservation_id
            self.runtime.transition_tool_execution(
                execution_id, "indeterminate", patch,
                self.metadata(execution_id, "indeterminate"),
            )
            return self.store.require_state(ToolExecutionAggregate.stream_id(execution_id))

        terminal_state = "completed" if result["status"] == "succeeded" else "failed"
        if from_state in {"dispatching", "effect_observed"}:
            self.runtime.transition_tool_execution(
                execution_id, "settling",
                {
                    "result": result,
                    "resultDigest": result_digest,
                    "sideEffectIdentity": result.get("sideEffectIdentity"),
                    "settlementStatus": "settling",
                    "dispatchBoundary": "response_completed",
                    "worldReceipt": world_receipt,
                },
                self.metadata(execution_id, "settling"),
            )
        terminal_patch = {
            "result": result,
            "resultDigest": result_digest,
            "sideEffectIdentity": result.get("sideEffectIdentity"),
            "settlementStatus": "settled",
            "worldReceipt": world_receipt,
            "dispatchBoundary": (
                "response_completed"
                if from_state in {"dispatching", "effect_observed", "settling"}
                else "not_started"
            ),
        }
        if reservation_id is not None:
            terminal_patch["reservationId"] = reservation_id
        self.runtime.transition_tool_execution(
            execution_id, terminal_state, terminal_patch,
            self.metadata(execution_id, terminal_state),
        )
        return self.store.require_state(ToolExecutionAggregate.stream_id(execution_id))

    def _settle_predispatch_terminal(
        self,
        execution: Dict[str, Any],
        request: Dict[str, Any],
        result: Dict[str, Any],
        stage: str,
    ) -> Dict[str, Any]:
        """Atomically close pre-dispatch authority and the ToolExecution."""
        reservation_id = execution.get("reservationId")
        if reservation_id is None and execution.get("state") == "prepared":
            orphan = self._open_predispatch_reservation(execution)
            reservation_id = orphan.get("reservationId") if orphan else None
        if reservation_id and request.get("grantId") and request.get("leaseId"):
            consumption = self._consumption(
                execution["toolExecutionId"], reservation_id, request["leaseId"],
                "failed", None,
            )
            self.runtime.settle_predispatch_tool_execution(
                request["grantId"], consumption, execution["toolExecutionId"], result,
                self.metadata(execution["toolExecutionId"], stage),
            )
            return self.store.require_state(
                ToolExecutionAggregate.stream_id(execution["toolExecutionId"])
            )
        return self._transition_terminal(
            execution["toolExecutionId"], execution["state"], result
        )

    def execute(
        self,
        request: Dict[str, Any],
        *,
        operator_id: str,
        session_id: str,
    ) -> Dict[str, Any]:
        require("ToolRequest", request)
        expected_fingerprint = tool_request_fingerprint(request)
        if request["operationFingerprint"] != expected_fingerprint:
            raise IntegrityViolation("ToolRequest operationFingerprint does not match semantic request")
        if request.get("reservationId") is not None:
            raise AuthorityViolation("caller may not supply a capability reservationId")

        execution_id = self.execution_id(request["idempotencyKey"])
        stream = ToolExecutionAggregate.stream_id(execution_id)
        existing = self.store.load_state(stream)
        if existing is not None:
            if existing["operationFingerprint"] != expected_fingerprint:
                raise IdempotencyConflict(
                    f"idempotency key {request['idempotencyKey']!r} reused with different tool request"
                )
            if existing["operatorId"] != operator_id or existing["sessionId"] != session_id:
                raise AuthorityViolation("tool idempotency replay identity mismatch")
            if existing["state"] in TERMINAL_STATES:
                return self._replay_projection(existing)
            if existing["state"] not in {"prepared", "admitted"}:
                raise ToolBrokerError(
                    f"tool execution {execution_id} requires reconciliation at state {existing['state']}"
                )
            registration = self._validate_request(request)
            adapter = registration["adapter"]
            adapter_id = getattr(adapter, "adapter_id", "adapter-" + request["toolId"] )
            if existing["descriptorDigest"] != registration["descriptorDigest"] or existing["adapterId"] != adapter_id:
                raise AuthorityViolation("WORLD_RECEIPT_RESUME_ADAPTER_OR_DESCRIPTOR_DRIFT")
            execution = deepcopy(existing)
        else:
            registration = self._validate_request(request)
            execution = self.build_execution(
                request, operator_id=operator_id, session_id=session_id
            )
            self.runtime.prepare_tool_execution(
                execution, self.metadata(execution_id, "prepared")
            )

        scope = self._scope_for(request)
        effect_intent = execution.get("effectIntent")
        if effect_intent is not None and timestamp_at_or_before(effect_intent["expiresAt"], self._now()):
            denied = self._denied_result(request, "WORLD_RECEIPT_EFFECT_INTENT_EXPIRED")
            state = self._settle_predispatch_terminal(
                execution, request, denied, "expiry-predispatch-settle"
            )
            return {
                "toolExecutionId": execution_id,
                "status": denied["status"],
                "result": denied,
                "state": state["state"],
                "replayed": False,
            }
        try:
            self.runtime.check_lease(
                request["grantId"], request["leaseId"], request["operation"], scope, self._now()
            )
        except CapabilityDenied as exc:
            denied = self._denied_result(request, str(exc))
            state = self._settle_predispatch_terminal(
                execution, request, denied, "deny-predispatch-settle"
            )
            return {
                "toolExecutionId": execution_id,
                "status": denied["status"],
                "result": denied,
                "state": state["state"],
                "replayed": False,
            }

        adapter = registration["adapter"]
        preflight = getattr(adapter, "preflight", None)
        if execution["state"] == "prepared" and callable(preflight):
            try:
                preflight(deepcopy(request))
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, (AuthorityViolation, CapabilityDenied, ValueError)):
                    result = self._denied_result(
                        request, "request-specific tool preflight denied: " + reason
                    )
                else:
                    result = self._result_from_adapter(
                        request,
                        {
                            "status": "failed",
                            "exitCode": None,
                            "output": [
                                {
                                    "kind": "string",
                                    "name": "preflight_error",
                                    "value": reason[:16384],
                                }
                            ],
                            "sideEffectIdentity": None,
                            "error": None,
                        },
                    )
                state = self._transition_terminal(execution_id, execution["state"], result)
                return {
                    "toolExecutionId": execution_id,
                    "status": result["status"],
                    "result": result,
                    "state": state["state"],
                    "replayed": False,
                }

        reservation_id = execution.get("reservationId")
        if request["consequential"] and reservation_id is None:
            reservation = self._reservation(request, execution_id)
            self.runtime.reserve_use(
                request["grantId"], reservation,
                self.metadata(execution_id, "reserve-capability"),
            )
            reservation_id = reservation["reservationId"]

        if execution["state"] == "prepared":
            self.runtime.transition_tool_execution(
                execution_id, "admitted", {"reservationId": reservation_id},
                self.metadata(execution_id, "admitted"),
            )
        self.runtime.transition_tool_execution(
            execution_id, "dispatching", {"dispatchBoundary": "started"},
            self.metadata(execution_id, "dispatching"),
        )

        observed_identity: str | None = None

        def observe_effect(side_effect_identity: str) -> None:
            nonlocal observed_identity
            if not request["consequential"]:
                raise AuthorityViolation("pure read-only tool may not publish side-effect identity")
            if not isinstance(side_effect_identity, str) or not side_effect_identity:
                raise ValueError("observed side-effect identity must be a non-empty string")
            if len(side_effect_identity) > 2048:
                raise ValueError("observed side-effect identity exceeds ToolExecution bound")
            if observed_identity is not None:
                if side_effect_identity != observed_identity:
                    raise IntegrityViolation("adapter attempted to replace observed side-effect identity")
                return
            self.runtime.transition_tool_execution(
                execution_id,
                "effect_observed",
                {
                    "sideEffectIdentity": side_effect_identity,
                    "dispatchBoundary": "effect_observed",
                },
                self.metadata(execution_id, "effect-observed"),
            )
            observed_identity = side_effect_identity

        world_receipt: Dict[str, Any] | None = None
        effect_intent = execution.get("effectIntent")
        try:
            if effect_intent is not None:
                execute_world_effect = getattr(adapter, "execute_world_effect", None)
                if not callable(execute_world_effect):
                    raise AuthorityViolation("WORLD_RECEIPT_EFFECT_UNSUPPORTED")
                adapter_result = execute_world_effect(
                    deepcopy(request), deepcopy(effect_intent), observe_effect
                )
            else:
                execute_observed = getattr(adapter, "execute_observed", None)
                if callable(execute_observed):
                    adapter_result = execute_observed(deepcopy(request), observe_effect)
                else:
                    adapter_result = adapter.execute(deepcopy(request))
            if observed_identity is not None:
                returned_identity = adapter_result.get("sideEffectIdentity")
                if returned_identity is None:
                    adapter_result = deepcopy(adapter_result)
                    adapter_result["sideEffectIdentity"] = observed_identity
                elif returned_identity != observed_identity:
                    raise IntegrityViolation(
                        "adapter result side-effect identity disagrees with observed identity"
                    )
            if effect_intent is not None:
                candidate = adapter_result.get("worldReceipt")
                if not isinstance(candidate, dict):
                    raise IntegrityViolation("WORLD_RECEIPT_MISSING_AFTER_EFFECT")
                verify_world_receipt(effect_intent, candidate)
                verify_receipt = getattr(adapter, "verify_receipt", None)
                if not callable(verify_receipt) or verify_receipt(effect_intent, candidate) is not True:
                    raise IntegrityViolation("WORLD_RECEIPT_TARGET_VERIFICATION_FAILED")
                if observed_identity != receipt_side_effect_identity(candidate):
                    raise IntegrityViolation("WORLD_RECEIPT_OBSERVED_IDENTITY_MISMATCH")
                world_receipt = deepcopy(candidate)
            result = self._result_from_adapter(request, adapter_result)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            if request["consequential"]:
                result = self._indeterminate_result(
                    request["toolRequestId"], request["idempotencyKey"],
                    "adapter failed after dispatch boundary: " + reason,
                    side_effect_identity=observed_identity,
                )
            else:
                result = self._result_from_adapter(request, {
                    "status": "failed", "exitCode": None,
                    "output": [{"kind": "string", "name": "error", "value": reason[:16384]}],
                    "sideEffectIdentity": None, "error": None,
                })

        if request["consequential"] and reservation_id is not None:
            outcome = (
                "succeeded" if result["status"] == "succeeded"
                else "indeterminate" if result["status"] == "indeterminate"
                else "failed"
            )
            consumption = self._consumption(
                execution_id, reservation_id, request["leaseId"], outcome,
                result.get("sideEffectIdentity"),
            )
            try:
                self.runtime.finalize_use(
                    request["grantId"], consumption,
                    self.metadata(execution_id, "finalize-capability"),
                )
            except Exception as exc:
                result = self._indeterminate_result(
                    request["toolRequestId"], request["idempotencyKey"],
                    "capability settlement failed after tool dispatch: "
                    f"{type(exc).__name__}: {exc}",
                    side_effect_identity=result.get("sideEffectIdentity"),
                )

        reason = None
        if result["status"] == "indeterminate":
            reason = next(
                (
                    item["value"] for item in result["output"]
                    if item.get("name") == "reconciliation"
                ),
                "external effect is indeterminate",
            )
        state = self._transition_terminal(
            execution_id,
            "effect_observed" if observed_identity is not None else "dispatching",
            result,
            reconciliation_reason=reason,
            world_receipt=world_receipt,
        )
        return {
            "toolExecutionId": execution_id,
            "status": result["status"],
            "result": result,
            "state": state["state"],
            "replayed": False,
        }

    def _reconciled_success_result(
        self, state: Dict[str, Any], receipt: Dict[str, Any]
    ) -> Dict[str, Any]:
        output = [
            {"kind": "string", "name": "reconciliation",
             "value": "target-local WorldReceipt verified after restart"},
            {"kind": "string", "name": "beforeDigest",
             "value": state["effectIntent"]["basisVersion"]},
            {"kind": "string", "name": "afterDigest",
             "value": receipt["observedStateDigest"]},
        ]
        result = {
            "schemaVersion": "1.0.0",
            "toolResultId": _stable_id("tool-result-", state["toolExecutionId"] + ":reconciled"),
            "toolRequestId": state["toolRequestId"],
            "status": "succeeded", "output": output, "exitCode": None,
            "outputDigest": digest(output),
            "sideEffectIdentity": receipt_side_effect_identity(receipt),
            "error": None, "completedAt": self._now(),
        }
        require("ToolResult", result)
        return result

    def _recovery_failure_result(
        self, state: Dict[str, Any], reason: str
    ) -> Dict[str, Any]:
        output = [{"kind": "string", "name": "reconciliation", "value": reason[:16384]}]
        result = {
            "schemaVersion": "1.0.0",
            "toolResultId": _stable_id(
                "tool-result-", state["toolExecutionId"] + ":recovery-failed"
            ),
            "toolRequestId": state["toolRequestId"],
            "status": "failed",
            "output": output,
            "exitCode": None,
            "outputDigest": digest(output),
            "sideEffectIdentity": None,
            "error": None,
            "completedAt": self._now(),
        }
        require("ToolResult", result)
        return result

    def _open_predispatch_reservation(
        self, state: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        grant_id = state.get("grantId")
        if not grant_id:
            return None
        capability = self.store.load_state(CapabilityAggregate.stream_id(grant_id)) or {}
        expected = _stable_id("tool-res-", state["toolExecutionId"])
        for reservation in capability.get("reservations") or []:
            if reservation.get("reservationId") == expected and reservation.get("state") == "open":
                return deepcopy(reservation)
        return None

    def reconcile_stranded(self) -> list[Dict[str, Any]]:
        """Reconcile crossed effect boundaries without redispatch.

        A verified target-local WorldReceipt may prove a committed effect. If no
        receipt exists, a staged/escrowed effect remains indeterminate even when
        its reversal handle verifies; recovery records that reversible state but
        never upgrades absence of a receipt into success.
        """
        recovered: list[Dict[str, Any]] = []
        for stream_id, kind, _version in self.store.all_aggregates():
            if kind != ToolExecutionAggregate.KIND:
                continue
            state = self.store.require_state(stream_id)

            # A crash may persist the capability reservation immediately before
            # the ToolExecution's admitted transition. No external dispatch has
            # happened, so close that orphan as failed rather than consuming a
            # use or leaving durable phantom authority.
            if state["state"] == "prepared":
                orphan = self._open_predispatch_reservation(state)
                if orphan is None:
                    continue
                reason = (
                    f"runtime recovered ToolExecution {state['toolExecutionId']} "
                    "with an open pre-dispatch capability reservation; no "
                    "external dispatch occurred"
                )
                consumption = self._consumption(
                    state["toolExecutionId"], orphan["reservationId"],
                    state["leaseId"], "failed", None,
                )
                result = self._recovery_failure_result(state, reason)
                self.runtime.settle_predispatch_tool_execution(
                    state["grantId"], consumption, state["toolExecutionId"], result,
                    self.metadata(state["toolExecutionId"], "recover-predispatch-settle"),
                )
                terminal = self.store.require_state(
                    ToolExecutionAggregate.stream_id(state["toolExecutionId"])
                )
                recovered.append(deepcopy(terminal))
                continue

            if state["state"] not in {"dispatching", "effect_observed", "settling"}:
                continue

            try:
                registration = self.registry.require(state["toolId"])
                adapter = registration["adapter"]
            except Exception as exc:
                reason = (
                    f"runtime recovered ToolExecution {state['toolExecutionId']} "
                    f"from {state['state']} but tool {state['toolId']!r} is not "
                    f"available for reconciliation: {type(exc).__name__}: {exc}"
                )
                result = self._indeterminate_result(
                    state["toolRequestId"], state["toolExecutionId"], reason,
                    side_effect_identity=state.get("sideEffectIdentity"),
                )
                if state.get("reservationId") and state.get("grantId") and state.get("leaseId"):
                    consumption = self._consumption(
                        state["toolExecutionId"], state["reservationId"], state["leaseId"],
                        "indeterminate", state.get("sideEffectIdentity"),
                    )
                    try:
                        self.runtime.finalize_use(
                            state["grantId"], consumption,
                            self.metadata(state["toolExecutionId"], "missing-tool-capability"),
                        )
                    except Exception:
                        pass
                terminal = self._transition_terminal(
                    state["toolExecutionId"], state["state"], result,
                    reconciliation_reason=reason,
                )
                recovered.append(deepcopy(terminal))
                continue
            reconciliation_error = None
            reversible_stage_verified = False
            if getattr(adapter, "supports_reconciliation", False) and state.get("effectIntent"):
                reconcile = getattr(adapter, "reconcile", None)
                if callable(reconcile):
                    try:
                        observed = reconcile(deepcopy(state))
                        if observed is not None:
                            verify_world_receipt(state["effectIntent"], observed)
                            verify_receipt = getattr(adapter, "verify_receipt", None)
                            if not callable(verify_receipt) or verify_receipt(state["effectIntent"], observed) is not True:
                                raise IntegrityViolation("WORLD_RECEIPT_TARGET_VERIFICATION_FAILED")
                            result = self._reconciled_success_result(state, observed)
                            if state.get("reservationId") and state.get("grantId") and state.get("leaseId"):
                                consumption = self._consumption(
                                    state["toolExecutionId"], state["reservationId"], state["leaseId"],
                                    "succeeded", result["sideEffectIdentity"],
                                )
                                self.runtime.finalize_use(
                                    state["grantId"], consumption,
                                    self.metadata(state["toolExecutionId"], "reconcile-capability"),
                                )
                            terminal = self._transition_terminal(
                                state["toolExecutionId"], state["state"], result,
                                world_receipt=deepcopy(observed),
                            )
                            recovered.append(deepcopy(terminal))
                            continue
                    except Exception as exc:
                        reconciliation_error = f"{type(exc).__name__}: {exc}"

            intent = state.get("effectIntent") or {}
            if (
                not reconciliation_error
                and intent.get("rollbackStrategy") == "escrow"
                and intent.get("reversalHandle")
            ):
                verify_reversal = getattr(adapter, "verify_reversal_handle", None)
                if callable(verify_reversal):
                    try:
                        reversible_stage_verified = bool(
                            verify_reversal(deepcopy(intent))
                        )
                    except Exception as exc:
                        reconciliation_error = f"{type(exc).__name__}: {exc}"

            reason = (
                f"runtime recovered ToolExecution {state['toolExecutionId']} "
                f"from {state['state']} after dispatch boundary; no proven "
                "adapter reconciliation result or committed target receipt is available"
            )
            if reversible_stage_verified:
                reason += (
                    "; staged effect remains reversible via verified target-local "
                    f"handle {intent['reversalHandle']}"
                )
            if reconciliation_error:
                reason += "; reconciliation proof rejected: " + reconciliation_error
            result = self._indeterminate_result(
                state["toolRequestId"],
                state["toolExecutionId"],
                reason,
                side_effect_identity=state.get("sideEffectIdentity"),
            )

            if state.get("reservationId") and state.get("grantId") and state.get("leaseId"):
                consumption = self._consumption(
                    state["toolExecutionId"], state["reservationId"], state["leaseId"],
                    "indeterminate", state.get("sideEffectIdentity"),
                )
                try:
                    self.runtime.finalize_use(
                        state["grantId"], consumption,
                        self.metadata(state["toolExecutionId"], "reconcile-capability"),
                    )
                except Exception:
                    # The ToolExecution still must not be redispatched. The
                    # reconciliation reason below remains authoritative debt.
                    pass

            terminal = self._transition_terminal(
                state["toolExecutionId"], state["state"], result,
                reconciliation_reason=reason,
            )
            recovered.append(deepcopy(terminal))
        return recovered
