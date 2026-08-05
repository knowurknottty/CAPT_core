"""CAPT Desktop Runtime M1 — thin operator command relay (authoritative side).

This module lives on the AUTHORITATIVE runtime side (same process as the
read-only query service). It is intentionally thin: it performs ONLY what a
client/transport boundary must, and delegates all authority, planning,
orchestration, and idempotency to CAPT Runtime:

    Desktop command (operator intent)
    -> authenticated IPC (operatorId + sessionId bound to the connection)
    -> envelope validation (transport: required fields, schema, op, identity)
    -> RuntimeService.<method>(intent, operator CommandMetadata)
         * authority evaluation      (capt_runtime.authority)
         * planning (MissionSpec/TaskNode/ApprovalRequest construction)
         * cross-aggregate orchestration (single governed transaction)
         * idempotency replay        (EventStore.find_idempotent)
         * aggregate mutation         (CAPT aggregates own all state)
         * transactional event commit (EventStore.commit_command)
    -> classified receipt (status / classification / result / error)

The desktop NEVER builds aggregates, evaluates authority, plans tasks, or
mutates CAPT state. Those live in capt_runtime. The only desktop-owned
concerns are: per-connection operator/session binding (transport
authentication), command routing, and receipt/error *presentation* (the
classification string is taken from the runtime's own error taxonomy, not
re-derived here).

No enterprise identity, multi-user, or tenant-isolation claim is made. This is
a single-user macOS desktop operator console; the operator is the local user.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from capt_runtime import commands
from capt_runtime.errors import CaptRuntimeError
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore

CONTRACT_SCHEMA_VERSION = "1.0.0"

# Required command envelope fields (transport contract with the client).
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
    "submit_approval_decision",
    "cancel_task",
    "cancel_driver_run",
    "update_memory_trigger_policy",
)


def _now_rfc3339() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class RuntimeCommandService:
    """Executes governed operator commands by delegating to CAPT Runtime.

    One instance is created per authenticated desktop connection, bound to that
    connection's operatorId and sessionId. The binding is the sole source of
    operator identity for commands; the desktop cannot escalate by claiming a
    different operatorId or sessionId.
    """

    def __init__(
        self,
        store: EventStore,
        operator_id: str,
        session_id: str,
        memory_engine: Any = None,
        runtime_service: Optional[RuntimeService] = None,
    ) -> None:
        self.store = store
        # Production operator surfaces inject the canonical composition-owned
        # service.  The fallback preserves existing isolated unit-test callers.
        self.svc = runtime_service or RuntimeService(store)
        self.operator_id = operator_id
        self.session_id = session_id
        self.memory_engine = memory_engine  # optional MemoryTriggerEngine

    # -- envelope / identity validation (transport boundary) -------------

    def _validate_envelope(self, cmd: Dict[str, Any]) -> Optional[str]:
        """Transport-level validation only. Authority/planning live in Runtime."""
        if not isinstance(cmd, dict):
            return "malformed"
        missing = [f for f in _REQUIRED_ENVELOPE if f not in cmd]
        if missing:
            return "malformed"
        if cmd.get("schemaVersion") != CONTRACT_SCHEMA_VERSION:
            return "malformed"
        if cmd.get("op") not in _VALID_OPS:
            return "malformed"
        # Operator identity binding: the command must be issued by the
        # operator bound to this authenticated session. This is transport
        # authentication, not runtime authority (which Runtime also enforces).
        if cmd.get("operatorId") != self.operator_id:
            return "unauthorized"
        if cmd.get("sessionId") != self.session_id:
            return "unauthorized"
        return None

    def _mission_context_usage(self, payload: Dict[str, Any]) -> Any:
        """Estimate context usage for a mission intent (ESTIMATED tokens).

        Uses the runtime-owned accounting module; the estimate is labeled
        ESTIMATED because no exact tokenizer is available. This is the current
        context usage at mission creation, used to decide whether the retrieval
        trigger fires.
        """
        from capt_runtime.memory.accounting import ContextUsage, estimate_tokens
        u = ContextUsage()
        u.mission_spec = estimate_tokens(json.dumps(payload))
        u.policy_constraints = estimate_tokens("capt_runtime authority governance policy")
        u.system_instructions = estimate_tokens("capt runtime operator mission")
        return u

    def _operator_metadata(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Build the human operator CommandMetadata for this command.

        The operatorId is the connection-bound identity; the actor kind is
        always "human" (operator commands). Runtime decides the inner actor
        kinds for planning/execution.
        """
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

    # -- dispatch ---------------------------------------------------------

    def execute(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        envelope_err = self._validate_envelope(cmd)
        if envelope_err:
            return self._receipt(
                cmd, status="rejected", classification=envelope_err,
                error=self._error_envelope(cmd, envelope_err, "ENVELOPE_%s" % envelope_err.upper()),
            )
        op = cmd["op"]
        meta = self._operator_metadata(cmd)
        try:
            if op == "create_mission":
                # Mandatory memory retrieval trigger BEFORE planning: CAPT owns
                # the trigger decision. The operator intent is submitted; the
                # runtime fires the governed memory query and assembles the
                # ContextPack before planning the mission.
                if self.memory_engine is not None:
                    mid = cmd["payload"].get("missionId", "")
                    usage = self._mission_context_usage(cmd["payload"])
                    self.memory_engine.require_retrieval_before_planning(mid, usage)
                result = self.svc.create_mission_with_approval(cmd["payload"], meta)
            elif op == "submit_approval_decision":
                # Assemble the HumanApprovalDecision contract from the operator's
                # minimal input (requestId + decision) and the authenticated
                # session identity. This is contract/transport assembly, not
                # runtime authority or planning (which Runtime owns).
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
                    cmd["payload"]["taskId"], cmd["payload"].get("reason", "Operator cancelled."), meta
                )
            elif op == "cancel_driver_run":
                result = self.svc.cancel_driver_run(
                    cmd["payload"]["driverRunId"], cmd["payload"].get("reason", "Operator cancelled."), meta
                )
            elif op == "update_memory_trigger_policy":
                if self.memory_engine is None:
                    return self._receipt(
                        cmd, status="rejected", classification="internal_failure",
                        error=self._error_envelope(cmd, "internal_failure", "MEMORY_ENGINE_ABSENT"),
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
                        cmd, status="rejected", classification="policy_denied",
                        error=self._error_envelope(cmd, "policy_denied", "MEMORY_TRIGGER_CONFIGURATION_INVALID"),
                        detail=str(exc)[:240],
                    )
                return self._receipt(
                    cmd, status="accepted", classification="accepted",
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
            else:
                return self._receipt(
                    cmd, status="rejected", classification="malformed",
                    error=self._error_envelope(cmd, "malformed", "UNKNOWN_OP"),
                )
            return self._receipt_from_runtime(cmd, result)
        except CaptRuntimeError as exc:
            # Classification comes from the runtime's own error taxonomy
            # (errors.py sets .category). The desktop does not re-derive it.
            classification = getattr(exc, "category", "internal_failure")
            return self._receipt(
                cmd, status="rejected", classification=classification,
                error=self._error_envelope(cmd, classification, type(exc).__name__.upper()),
                detail=str(exc)[:240],
            )
        except Exception as exc:  # noqa: BLE001
            return self._receipt(
                cmd, status="rejected", classification="internal_failure",
                error=self._error_envelope(cmd, "internal_failure", type(exc).__name__.upper()),
                detail=str(exc)[:240],
            )

    # -- receipt / error helpers (presentation only) ---------------------

    def _receipt_from_runtime(self, cmd: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        status = result.get("status", "applied")
        if status == "idempotent":
            classification = "duplicate"
        elif status == "applied":
            classification = "accepted"
        else:
            classification = "accepted"
        return self._receipt(
            cmd, status=("idempotent" if status == "idempotent" else "accepted"),
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

    def _stream_for(self, cmd: Dict[str, Any], result: Dict[str, Any]) -> Optional[str]:
        p = cmd["payload"]
        if cmd["op"] == "create_mission":
            return "mission-" + str(result.get("missionId") or p.get("missionId", ""))
        if cmd["op"] == "submit_approval_decision":
            return "human_approval-" + str(p.get("requestId", ""))
        if cmd["op"] == "cancel_task":
            return "task-" + str(p.get("taskId", ""))
        if cmd["op"] == "cancel_driver_run":
            return "driverrun-" + str(p.get("driverRunId", ""))
        return None

    def _receipt(
        self, cmd: Dict[str, Any], status: str, classification: str,
        result: Optional[Dict[str, Any]] = None, error: Optional[Dict[str, Any]] = None,
        stream_id: Optional[str] = None, detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "status": status,  # accepted | rejected | idempotent
            "classification": classification,  # explicit outcome class
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

    def _error_envelope(self, cmd: Dict[str, Any], category: str, code: str) -> Dict[str, Any]:
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
