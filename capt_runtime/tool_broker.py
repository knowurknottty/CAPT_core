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

    def build_execution(
        self, request: Dict[str, Any], *, operator_id: str, session_id: str
    ) -> Dict[str, Any]:
        registration = self._validate_request(request)
        descriptor = registration["descriptor"]
        adapter = registration["adapter"]
        execution_id = self.execution_id(request["idempotencyKey"])
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
        self, tool_request_id: str, material: str, reason: str
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
            "sideEffectIdentity": None,
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
    ) -> Dict[str, Any]:
        result_digest = digest(result)
        if result["status"] == "indeterminate":
            patch = {
                "result": result,
                "resultDigest": result_digest,
                "sideEffectIdentity": result.get("sideEffectIdentity"),
                "settlementStatus": "reconciliation_required",
                "reconciliationReason": reconciliation_reason or "external effect is indeterminate",
            }
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
                },
                self.metadata(execution_id, "settling"),
            )
        self.runtime.transition_tool_execution(
            execution_id, terminal_state,
            {
                "result": result,
                "resultDigest": result_digest,
                "sideEffectIdentity": result.get("sideEffectIdentity"),
                "settlementStatus": "settled",
                "dispatchBoundary": (
                    "response_completed" if from_state in {"dispatching", "effect_observed"}
                    else "not_started"
                ),
            },
            self.metadata(execution_id, terminal_state),
        )
        return self.store.require_state(ToolExecutionAggregate.stream_id(execution_id))

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
            raise ToolBrokerError(
                f"tool execution {execution_id} is already in progress at state {existing['state']}"
            )

        registration = self._validate_request(request)
        execution = self.build_execution(
            request, operator_id=operator_id, session_id=session_id
        )
        self.runtime.prepare_tool_execution(
            execution, self.metadata(execution_id, "prepared")
        )

        scope = self._scope_for(request)
        try:
            self.runtime.check_lease(
                request["grantId"], request["leaseId"], request["operation"], scope, self._now()
            )
        except CapabilityDenied as exc:
            denied = self._denied_result(request, str(exc))
            state = self._transition_terminal(execution_id, "prepared", denied)
            return {
                "toolExecutionId": execution_id,
                "status": denied["status"],
                "result": denied,
                "state": state["state"],
                "replayed": False,
            }

        adapter = registration["adapter"]
        preflight = getattr(adapter, "preflight", None)
        if callable(preflight):
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
                state = self._transition_terminal(execution_id, "prepared", result)
                return {
                    "toolExecutionId": execution_id,
                    "status": result["status"],
                    "result": result,
                    "state": state["state"],
                    "replayed": False,
                }

        reservation_id = None
        if request["consequential"]:
            reservation = self._reservation(request, execution_id)
            self.runtime.reserve_use(
                request["grantId"], reservation,
                self.metadata(execution_id, "reserve-capability"),
            )
            reservation_id = reservation["reservationId"]

        self.runtime.transition_tool_execution(
            execution_id, "admitted", {"reservationId": reservation_id},
            self.metadata(execution_id, "admitted"),
        )
        self.runtime.transition_tool_execution(
            execution_id, "dispatching", {"dispatchBoundary": "started"},
            self.metadata(execution_id, "dispatching"),
        )

        try:
            adapter_result = adapter.execute(deepcopy(request))
            result = self._result_from_adapter(request, adapter_result)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            if request["consequential"]:
                result = self._indeterminate_result(
                    request["toolRequestId"], request["idempotencyKey"],
                    "adapter failed after dispatch boundary: " + reason,
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
            execution_id, "dispatching", result, reconciliation_reason=reason
        )
        return {
            "toolExecutionId": execution_id,
            "status": result["status"],
            "result": result,
            "state": state["state"],
            "replayed": False,
        }

    def reconcile_stranded(self) -> list[Dict[str, Any]]:
        """Fail closed for executions that crossed an external dispatch boundary.

        Slice A has no adapter-specific read-only reconciliation proof. A
        stranded dispatch therefore becomes durable `indeterminate`; execution
        is never called from recovery.
        """
        recovered: list[Dict[str, Any]] = []
        for stream_id, kind, _version in self.store.all_aggregates():
            if kind != ToolExecutionAggregate.KIND:
                continue
            state = self.store.require_state(stream_id)
            if state["state"] not in {"dispatching", "effect_observed", "settling"}:
                continue

            registration = self.registry.require(state["toolId"])
            adapter = registration["adapter"]
            if getattr(adapter, "supports_reconciliation", False):
                reconcile = getattr(adapter, "reconcile", None)
                if callable(reconcile):
                    # Reconciliation may observe external state, but recovery
                    # never invokes adapter.execute(). Slice-A adapters do not
                    # currently implement this branch.
                    observed = reconcile(deepcopy(state))
                    if observed is not None:
                        raise ToolBrokerError(
                            "adapter reconciliation result contract is not implemented in Slice A"
                        )

            reason = (
                f"runtime recovered ToolExecution {state['toolExecutionId']} "
                f"from {state['state']} after dispatch boundary; no proven "
                "adapter reconciliation result is available"
            )
            result = self._indeterminate_result(
                state["toolRequestId"], state["toolExecutionId"], reason
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
