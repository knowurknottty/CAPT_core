"""CAPT Desktop Runtime M1 — thin operator command relay (authoritative side).

This module lives on the AUTHORITATIVE runtime side (same process as the
read-only query service). It performs transport concerns only and delegates
planning, authority, aggregate mutation, idempotency, and lifecycle to CAPT
runtime modules/services.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation, CaptRuntimeError, IdempotencyConflict
from capt_runtime.approval_dispatch import register_expected_prompt_digest
from capt_runtime.prompt_approval import request_model_prompt_approval
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.tool_broker import ToolBrokerError, ToolUnavailable
from capt_runtime.tools.registry import UnknownToolId

CONTRACT_SCHEMA_VERSION = "1.0.0"

_REQUIRED_ENVELOPE = (
    "commandId",
    "operatorId",
    "sessionId",
    "schemaVersion",
    "correlationId",
    "idempotencyKey",
    "timestamp",
    "op",
    "payload",
)

_VALID_OPS = (
    "create_mission",
    "request_model_prompt_approval",
    "submit_approval_decision",
    "cancel_task",
    "cancel_driver_run",
    "update_memory_trigger_policy",
    "run_fixed_openharness_inspection",
    "run_approved_hermes_inspection",
    "checkpoint_runtime",
    "shutdown",
    "resume_runtime",
    "run_tool",
)


def _now_rfc3339() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class RuntimeCommandService:
    """Execute governed operator commands against the canonical RuntimeService."""

    def __init__(
        self,
        store: EventStore,
        operator_id: str,
        session_id: str,
        memory_engine: Any = None,
        runtime_service: Optional[RuntimeService] = None,
        tool_broker: Any = None,
    ) -> None:
        self.store = store
        self.svc = runtime_service or RuntimeService(store)
        self.operator_id = operator_id
        self.session_id = session_id
        self.memory_engine = memory_engine
        self.tool_broker = tool_broker
        self.fixed_openharness_runner = None
        self.approved_hermes_runner: Any = None
        self.runtime_checkpoint_runner = None
        self.shutdown_runner = None
        self.resume_runner = None

    def _validate_envelope(self, cmd: Dict[str, Any]) -> Optional[str]:
        if not isinstance(cmd, dict):
            return "malformed"
        if [field for field in _REQUIRED_ENVELOPE if field not in cmd]:
            return "malformed"
        if cmd.get("schemaVersion") != CONTRACT_SCHEMA_VERSION:
            return "malformed"
        if cmd.get("op") not in _VALID_OPS:
            return "malformed"
        if cmd.get("operatorId") != self.operator_id:
            return "unauthorized"
        if cmd.get("sessionId") != self.session_id:
            return "unauthorized"
        return None

    def _mission_context_usage(self, payload: Dict[str, Any]) -> Any:
        from capt_runtime.memory.accounting import ContextUsage, estimate_tokens

        usage = ContextUsage()
        usage.mission_spec = estimate_tokens(json.dumps(payload))
        usage.policy_constraints = estimate_tokens("capt_runtime authority governance policy")
        usage.system_instructions = estimate_tokens("capt runtime operator mission")
        return usage

    def _operator_metadata(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        return commands.command(
            command_id=cmd["commandId"],
            idempotency_key=cmd["idempotencyKey"],
            operation_fingerprint=commands.fingerprint(cmd["op"], cmd["payload"]),
            correlation_id=cmd["correlationId"],
            actor_id=self.operator_id,
            actor_kind="human",
            issued_at=cmd.get("timestamp") or _now_rfc3339(),
            replay_policy="never",
        )

    def execute(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        envelope_err = self._validate_envelope(cmd)
        if envelope_err:
            return self._receipt(
                cmd,
                status="rejected",
                classification=envelope_err,
                error=self._error_envelope(
                    cmd, envelope_err, "ENVELOPE_%s" % envelope_err.upper()
                ),
            )
        op = cmd["op"]
        meta = self._operator_metadata(cmd)
        try:
            if op == "run_tool":
                if self.tool_broker is None:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal",
                        error=self._error_envelope(
                            cmd, "internal", "TOOL_BROKER_UNAVAILABLE"
                        ),
                    )
                request = cmd["payload"]
                if not isinstance(request, dict):
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="validation",
                        error=self._error_envelope(
                            cmd, "validation", "TOOL_REQUEST_MALFORMED"
                        ),
                    )
                if request.get("idempotencyKey") != cmd["idempotencyKey"]:
                    raise AuthorityViolation(
                        "run_tool envelope and ToolRequest idempotency keys must match"
                    )
                result = self.tool_broker.execute(
                    request,
                    operator_id=self.operator_id,
                    session_id=self.session_id,
                )
                replayed = bool(result.get("replayed"))
                return self._receipt(
                    cmd,
                    status="idempotent" if replayed else "accepted",
                    classification="duplicate" if replayed else "accepted",
                    result=result,
                    stream_id="tool_execution-" + str(result["toolExecutionId"]),
                )

            if op == "create_mission":
                if self.memory_engine is not None:
                    mid = cmd["payload"].get("missionId", "")
                    usage = self._mission_context_usage(cmd["payload"])
                    self.memory_engine.require_retrieval_before_planning(mid, usage)
                result = self.svc.create_mission_with_approval(cmd["payload"], meta)

            elif op == "request_model_prompt_approval":
                result = request_model_prompt_approval(self.svc, cmd["payload"], meta)
                status = "idempotent" if result.get("status") == "idempotent" else "accepted"
                return self._receipt(
                    cmd,
                    status=status,
                    classification="duplicate" if status == "idempotent" else "accepted",
                    result=result,
                    stream_id="human_approval-" + str(result.get("requestId", "")),
                )

            elif op == "submit_approval_decision":
                p = cmd["payload"]
                decision = {
                    "schemaVersion": CONTRACT_SCHEMA_VERSION,
                    "requestId": p["requestId"],
                    "decision": p["decision"],
                    "operatorId": self.operator_id,
                    "decidedAt": _now_rfc3339(),
                    "note": p.get("note"),
                    "idempotencyKey": cmd["idempotencyKey"],
                    "correlationId": cmd["correlationId"],
                    "sessionId": self.session_id,
                }
                result = self.svc.submit_human_approval_decision(decision, meta)

            elif op == "cancel_task":
                result = self.svc.cancel_task(
                    cmd["payload"]["taskId"],
                    cmd["payload"].get("reason", "Operator cancelled."),
                    meta,
                )

            elif op == "cancel_driver_run":
                result = self.svc.cancel_driver_run(
                    cmd["payload"]["driverRunId"],
                    cmd["payload"].get("reason", "Operator cancelled."),
                    meta,
                )

            elif op == "update_memory_trigger_policy":
                if self.memory_engine is None:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal_failure",
                        error=self._error_envelope(
                            cmd, "internal_failure", "MEMORY_ENGINE_ABSENT"
                        ),
                        detail="memory engine not wired into this runtime instance",
                    )
                p = cmd["payload"]
                try:
                    new_policy = self.memory_engine.update_policy(
                        retrieval_trigger_steps=p.get("retrievalTriggerSteps"),
                        compression_trigger_steps=p.get("compressionTriggerSteps"),
                        checkpoint_trigger_steps=p.get("checkpointTriggerSteps"),
                        consolidation_trigger_steps=p.get("consolidationTriggerSteps"),
                        hard_stop_trigger_steps=p.get("hardStopTriggerSteps"),
                        model_safe_limit_steps=p.get("modelSafeLimitSteps"),
                        source="operator_selected",
                        operator_id=self.operator_id,
                        command_id=cmd["commandId"],
                        correlation_id=cmd["correlationId"],
                    )
                except ValueError as exc:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="policy_denied",
                        error=self._error_envelope(
                            cmd,
                            "policy_denied",
                            "MEMORY_TRIGGER_CONFIGURATION_INVALID",
                        ),
                        detail=str(exc)[:240],
                    )
                return self._receipt(
                    cmd,
                    status="accepted",
                    classification="accepted",
                    result={
                        "policyVersion": new_policy.policy_version,
                        "policyDigest": new_policy.policy_digest,
                        "retrievalTriggerSteps": new_policy.retrieval_trigger_steps,
                        "retrievalTokens": new_policy.retrieval_tokens(),
                        "compressionTriggerSteps": new_policy.compression_trigger_steps,
                        "compressionTokens": new_policy.compression_tokens(),
                        "checkpointTriggerSteps": new_policy.checkpoint_trigger_steps,
                        "checkpointTokens": new_policy.checkpoint_tokens(),
                        "consolidationTriggerSteps": new_policy.consolidation_trigger_steps,
                        "consolidationTokens": new_policy.consolidation_tokens(),
                        "hardStopTriggerSteps": new_policy.hard_stop_trigger_steps,
                        "hardStopTokens": new_policy.hard_stop_tokens(),
                        "modelSafeLimitSteps": new_policy.model_safe_limit_steps,
                        "source": new_policy.source,
                    },
                )

            elif op == "run_fixed_openharness_inspection":
                runner = getattr(self, "fixed_openharness_runner", None)
                if runner is None:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal_failure",
                        error=self._error_envelope(
                            cmd, "internal_failure", "FIXED_DRIVER_UNAVAILABLE"
                        ),
                    )
                result = runner(cmd)
                status = "idempotent" if result.pop("_idempotent", False) else "accepted"
                return self._receipt(
                    cmd,
                    status=status,
                    classification="duplicate" if status == "idempotent" else "accepted",
                    result=result,
                )

            elif op == "run_approved_hermes_inspection":
                runner = getattr(self, "approved_hermes_runner", None)
                if runner is None or not callable(getattr(runner, "prepare", None)) or not callable(getattr(runner, "execute", None)):
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal_failure",
                        error=self._error_envelope(
                            cmd, "internal_failure", "HERMES_DRIVER_UNAVAILABLE"
                        ),
                    )
                # Admission owns the original command's idempotency key. Check it
                # before preparation so a consumed one-use approval is never read
                # or reconstructed on a retry/crash replay.
                prior_admission = self.store.find_idempotent(cmd["idempotencyKey"])
                if prior_admission is not None:
                    if prior_admission["command_id"] != cmd["commandId"]:
                        raise IdempotencyConflict(
                            "idempotency key %r reused by a different command" % cmd["idempotencyKey"])
                    return self._receipt(
                        cmd, status="idempotent", classification="duplicate",
                        result=self.store.idempotent_result(cmd["idempotencyKey"]) or {},
                    )
                run_fingerprint = commands.fingerprint(
                    "run_approved_hermes_inspection", cmd["payload"]
                )
                prior_run_command = self.store.find_idempotent(cmd["idempotencyKey"])
                if (
                    prior_run_command is not None
                    and prior_run_command["operation_fingerprint"] != run_fingerprint
                ):
                    raise IdempotencyConflict(
                        "idempotency key %r reused with a different operation fingerprint"
                        % cmd["idempotencyKey"]
                    )
                # Preparation is deterministic and side-effect-free. It must
                # precede one-use approval consumption.
                prepared = runner.prepare(cmd)
                identity = prepared.approval_identity
                # The original command idempotency record is committed with the
                # approval consumption and DriverRun intent, bound to the exact
                # credential-free prepared digest.
                admission_meta = commands.command(
                    command_id=prepared.command_id,
                    idempotency_key=prepared.idempotency_key,
                    operation_fingerprint=commands.fingerprint(
                        "admit_approved_model_execution",
                        {"preparedExecutionDigest": prepared.prepared_execution_digest},
                    ),
                    correlation_id=prepared.correlation_id,
                    actor_id="exec-1", actor_kind="execution_plane",
                    issued_at=prepared.issued_at, replay_policy="never",
                )
                admission = self.svc.admit_approved_model_execution(
                    prepared.approval_request_id,
                    identity["promptAssemblyDigest"],
                    prepared.operation,
                    mission_id=identity["missionId"],
                    task_id=identity["taskId"],
                    driver_run_id=identity["driverRunId"],
                    resource=identity["resource"],
                    use_id=prepared.idempotency_key,
                    now=prepared.issued_at,
                    metadata=admission_meta,
                    driver_id="provider" if prepared.provider_id else "hermes",
                    prepared_execution_digest=prepared.prepared_execution_digest,
                )
                if admission.get("status") == "idempotent":
                    # An admission record survives crashes. Never reconstruct
                    # command data or re-dispatch a durable intent on replay.
                    return self._receipt(
                        cmd, status="idempotent", classification="duplicate",
                        result={"driverRunId": prepared.driver_run_id,
                                "preparedExecutionDigest": prepared.prepared_execution_digest},
                    )
                register_expected_prompt_digest(
                    identity["driverRunId"], prepared.dispatch_prompt_digest
                )
                result = runner.execute(prepared)
                # The durable admission receipt is updated only after execution
                # returns; a crash before this line still replays as no-dispatch.
                self.store.complete_claimed_command(
                    prepared.idempotency_key, admission_meta["operationFingerprint"], result)
                if admission.get("status") == "idempotent":
                    result["_idempotent"] = True
                if result.get("status") == "in_progress":
                    return self._receipt(
                        cmd,
                        status="in_progress",
                        classification="in_progress",
                        result=result,
                    )
                status = "idempotent" if result.pop("_idempotent", False) else "accepted"
                return self._receipt(
                    cmd,
                    status=status,
                    classification="duplicate" if status == "idempotent" else "accepted",
                    result=result,
                )

            elif op == "checkpoint_runtime":
                runner = self.runtime_checkpoint_runner
                if runner is None:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal_failure",
                        error=self._error_envelope(
                            cmd, "internal_failure", "CHECKPOINT_UNAVAILABLE"
                        ),
                    )
                result = runner(cmd)
                status = "idempotent" if result.pop("_idempotent", False) else "accepted"
                return self._receipt(
                    cmd,
                    status=status,
                    classification="duplicate" if status == "idempotent" else "accepted",
                    result=result,
                )

            elif op == "shutdown":
                runner = self.shutdown_runner
                if runner is None:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal_failure",
                        error=self._error_envelope(
                            cmd, "internal_failure", "SHUTDOWN_UNAVAILABLE"
                        ),
                    )
                return self._receipt(
                    cmd,
                    status="accepted",
                    classification="accepted",
                    result=runner(),
                )

            elif op == "resume_runtime":
                runner = self.resume_runner
                if runner is None:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal_failure",
                        error=self._error_envelope(
                            cmd, "internal_failure", "RESUME_UNAVAILABLE"
                        ),
                    )
                return self._receipt(
                    cmd,
                    status="accepted",
                    classification="accepted",
                    result=runner(),
                )

            else:
                return self._receipt(
                    cmd,
                    status="rejected",
                    classification="malformed",
                    error=self._error_envelope(cmd, "malformed", "UNKNOWN_OP"),
                )

            return self._receipt_from_runtime(cmd, result)

        except ToolUnavailable as exc:
            return self._receipt(
                cmd,
                status="rejected",
                classification="internal",
                error=self._error_envelope(cmd, "internal", "TOOL_UNAVAILABLE"),
                detail=str(exc)[:240],
            )
        except UnknownToolId as exc:
            return self._receipt(
                cmd,
                status="rejected",
                classification="not_found",
                error=self._error_envelope(cmd, "not_found", "TOOL_NOT_FOUND"),
                detail=str(exc)[:240],
            )
        except ToolBrokerError as exc:
            return self._receipt(
                cmd,
                status="rejected",
                classification="internal",
                error=self._error_envelope(cmd, "internal", "TOOL_BROKER_ERROR"),
                detail=str(exc)[:240],
            )
        except CaptRuntimeError as exc:
            classification = getattr(exc, "category", "internal_failure")
            return self._receipt(
                cmd,
                status="rejected",
                classification=classification,
                error=self._error_envelope(
                    cmd, classification, type(exc).__name__.upper()
                ),
                detail=str(exc)[:240],
            )
        except Exception as exc:  # noqa: BLE001
            return self._receipt(
                cmd,
                status="rejected",
                classification="internal_failure",
                error=self._error_envelope(
                    cmd, "internal_failure", type(exc).__name__.upper()
                ),
                detail=str(exc)[:240],
            )

    def _receipt_from_runtime(
        self, cmd: Dict[str, Any], result: Dict[str, Any]
    ) -> Dict[str, Any]:
        status = result.get("status", "applied")
        classification = "duplicate" if status == "idempotent" else "accepted"
        return self._receipt(
            cmd,
            status="idempotent" if status == "idempotent" else "accepted",
            classification=classification,
            result={
                "missionId": result.get("missionId"),
                "taskId": result.get("taskId"),
                "requestId": result.get("requestId"),
                "targetId": result.get("targetId"),
                "state": result.get("state"),
            },
            stream_id=self._stream_for(cmd, result),
        )

    def _stream_for(
        self, cmd: Dict[str, Any], result: Dict[str, Any]
    ) -> Optional[str]:
        p = cmd["payload"]
        if cmd["op"] == "create_mission":
            return "mission-" + str(result.get("missionId") or p.get("missionId", ""))
        if cmd["op"] == "request_model_prompt_approval":
            return "human_approval-" + str(result.get("requestId", ""))
        if cmd["op"] == "submit_approval_decision":
            return "human_approval-" + str(p.get("requestId", ""))
        if cmd["op"] == "cancel_task":
            return "task-" + str(p.get("taskId", ""))
        if cmd["op"] == "cancel_driver_run":
            return "driverrun-" + str(p.get("driverRunId", ""))
        return None

    def _receipt(
        self,
        cmd: Dict[str, Any],
        status: str,
        classification: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
        stream_id: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "status": status,
            "classification": classification,
            "commandId": cmd.get("commandId"),
            "idempotencyKey": cmd.get("idempotencyKey"),
            "operatorId": self.operator_id,
            "sessionId": self.session_id,
            "streamId": stream_id,
            "result": result or {},
            "error": error,
            "detail": detail,
            "ledgerHead": self.store.head_sequence(),
        }

    def _error_envelope(
        self, cmd: Dict[str, Any], category: str, code: str
    ) -> Dict[str, Any]:
        return {
            "schemaVersion": CONTRACT_SCHEMA_VERSION,
            "category": category,
            "code": code,
            "message": "%s for command %s" % (category, cmd.get("commandId")),
            "occurredAt": _now_rfc3339(),
            "correlationId": cmd.get("correlationId"),
            "streamId": None,
            "expectedVersion": cmd.get("expectedVersion"),
            "actualVersion": None,
        }
