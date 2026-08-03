"""CAPT Desktop Runtime M1 — governed operator command service (authoritative side).

This module lives on the AUTHORITATIVE runtime side (same process as the
read-only query service). It translates desktop-originated operator commands
into real CAPT RuntimeService mutations through the governed command path:

    Desktop command
    -> authenticated IPC
    -> session/operator resolution   (bound to the authenticated connection)
    -> schema + command validation
    -> policy/authority evaluation   (RuntimeService.require_authority)
    -> aggregate mutation            (CAPT aggregates own all state)
    -> transactional event commit    (EventStore.commit_command)
    -> command receipt               (classified response)
    -> desktop projection update     (client-side, read-only)

The desktop never mutates CAPT state directly. Every consequential act is
authored by CAPT with a proper CommandMetadata envelope (commandId,
operatorId, sessionId, schemaVersion, correlationId, causationId,
idempotencyKey, timestamp, typed payload).

Operator identity (Phase 3): the service is constructed per authenticated
connection with the session's bound operatorId and sessionId. A command whose
operatorId or sessionId does not match the connection's bound identity is
rejected as `unauthorized` (prevents operator-ID spoofing and cross-session
authority). The session token alone is never treated as unrestricted
authority: every command still passes through CAPT authority evaluation.

No enterprise identity, multi-user, or tenant-isolation claim is made. This is
a single-user macOS desktop operator console; the operator is the local user.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional

from capt_runtime import commands, contracts
from capt_runtime.errors import (
    AuthorityViolation,
    CapabilityDenied,
    ConcurrencyConflict,
    ContractViolation,
    IdempotencyConflict,
    IllegalTransition,
    IntegrityViolation,
    NotFound,
    ReconciliationRequired,
)
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore

CONTRACT_SCHEMA_VERSION = "1.0.0"

# Required command envelope fields.
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
)


def _now_rfc3339() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _classify_error(exc: Exception) -> str:
    if isinstance(exc, ContractViolation):
        return "malformed"
    if isinstance(exc, (AuthorityViolation, CapabilityDenied)):
        return "unauthorized"
    if isinstance(exc, ConcurrencyConflict):
        return "stale_version"
    if isinstance(exc, IdempotencyConflict):
        return "duplicate"
    if isinstance(exc, IllegalTransition):
        return "already_terminal"
    if isinstance(exc, NotFound):
        return "not_found"
    if isinstance(exc, ReconciliationRequired):
        return "reconciliation_required"
    if isinstance(exc, IntegrityViolation):
        return "internal_failure"
    return "internal_failure"


class RuntimeCommandService:
    """Executes governed operator commands against the real CAPT runtime.

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
        now: Optional[Any] = None,
    ) -> None:
        self.store = store
        self.svc = RuntimeService(store)
        self.operator_id = operator_id
        self.session_id = session_id
        self._now = now or _now_rfc3339

    # -- envelope / identity validation ----------------------------------

    def _validate_envelope(self, cmd: Dict[str, Any]) -> Optional[str]:
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
        # operator bound to this authenticated session.
        if cmd.get("operatorId") != self.operator_id:
            return "unauthorized"
        if cmd.get("sessionId") != self.session_id:
            return "unauthorized"
        return None

    def _metadata(self, cmd: Dict[str, Any], operation: str, subject: Dict[str, Any], actor_kind: str = "human", idem_suffix: str = "") -> Dict[str, Any]:
        # Inner CAPT acts derive a distinct idempotency key from the outer
        # operator command so the store does not reject them as replays of the
        # outer command. The outer key still scopes the operator command.
        idek = cmd["idempotencyKey"] + (":" + idem_suffix if idem_suffix else "")
        fp_input = operation + ":" + contracts.digest(subject)
        return commands.command(
            command_id=cmd["commandId"] + (":" + idem_suffix if idem_suffix else ""),
            idempotency_key=idek,
            operation_fingerprint="sha256:" + hashlib.sha256(fp_input.encode()).hexdigest(),
            correlation_id=cmd["correlationId"],
            causation_id=cmd.get("causationId"),
            actor_id=self.operator_id,
            actor_kind=actor_kind,
            issued_at=cmd.get("timestamp") or self._now(),
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
        try:
            if op == "create_mission":
                return self._cmd_create_mission(cmd)
            if op == "submit_approval_decision":
                return self._cmd_submit_approval_decision(cmd)
            if op == "cancel_task":
                return self._cmd_cancel_task(cmd)
            if op == "cancel_driver_run":
                return self._cmd_cancel_driver_run(cmd)
            return self._receipt(
                cmd, status="rejected", classification="malformed",
                error=self._error_envelope(cmd, "malformed", "UNKNOWN_OP"),
            )
        except Exception as exc:  # noqa: BLE001
            classification = _classify_error(exc)
            return self._receipt(
                cmd, status="rejected", classification=classification,
                error=self._error_envelope(cmd, classification, type(exc).__name__.upper()),
                detail=str(exc)[:240],
            )

    # -- command: create_mission -----------------------------------------

    def _cmd_create_mission(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        p = cmd["payload"]
        mission_id = p["missionId"]
        # Idempotency at the mission level: if it already exists, reconstruct
        # the composite result without creating duplicates.
        if self.store.aggregate_version("mission-" + mission_id) > 0:
            existing = self._reconstruct_mission(mission_id)
            return self._receipt(
                cmd, status="idempotent", classification="duplicate",
                result=existing, stream_id="mission-" + mission_id,
            )

        spec = self._build_mission_spec(p)
        meta = self._metadata(cmd, "create_mission", {"missionId": mission_id})
        self.svc.create_mission(spec, meta)

        result: Dict[str, Any] = {"missionId": mission_id, "taskId": None, "requestId": None}
        requires_approval = bool(p.get("requiresApproval"))
        if requires_approval:
            task_id = p.get("taskId") or (mission_id + "-task-1")
            task = self._build_task(mission_id, task_id, p)
            self.svc.create_task(
                task, self._metadata(cmd, "create_task", {"taskId": task_id}, actor_kind="cognitive_plane", idem_suffix="task")
            )
            request_id = p.get("requestId") or (mission_id + "-approval-1")
            request = self._build_approval_request(mission_id, task_id, request_id, p)
            self.svc.request_human_approval(
                request,
                self._metadata(cmd, "request_human_approval", {"requestId": request_id}, actor_kind="execution_plane", idem_suffix="approval"),
            )
            result["taskId"] = task_id
            result["requestId"] = request_id
        return self._receipt(
            cmd, status="accepted", classification="accepted",
            result=result, stream_id="mission-" + mission_id,
        )

    def _build_mission_spec(self, p: Dict[str, Any]) -> Dict[str, Any]:
        objectives = p.get("objectives") or [
            {"objectiveId": "obj-1", "statement": p.get("objective", "Operator mission"), "priority": 1}
        ]
        constraints = p.get("constraints", [])
        success = p.get("successCriteria") or [
            {"criterionId": "sc-1", "statement": "Mission objective achieved", "requiresVerification": True}
        ]
        termination = p.get("terminationCriteria") or [
            {"criterionId": "tc-1", "statement": "Invariant violation terminates mission", "terminalState": "failed"}
        ]
        return {
            "schemaVersion": "1.0.0",
            "missionId": p["missionId"],
            "rawRequest": p.get("rawRequest", p.get("objective", "")),
            "normalizedRequest": p.get("normalizedRequest", p.get("objective", "")),
            "objectives": objectives,
            "constraints": constraints,
            "successCriteria": success,
            "terminationCriteria": termination,
            "unresolvedAmbiguities": p.get("unresolvedAmbiguities", []),
            "taskGraphId": None,
            "createdAt": self._now(),
        }

    def _build_task(self, mission_id: str, task_id: str, p: Dict[str, Any]) -> Dict[str, Any]:
        scope = p.get("scope") or {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}
        if "recursive" not in scope:
            scope = {**scope, "recursive": False}
        return {
            "taskId": task_id,
            "missionId": mission_id,
            "title": p.get("objective", "Operator task"),
            "state": "pending",
            "consequential": bool(p.get("consequential", True)),
            "capabilityRequirements": [
                {
                    "requirementId": "req-1",
                    "capabilityId": p.get("requestedCapability", "cap.fs.read"),
                    "operations": p.get("operations", ["repository.read"]),
                    "scope": scope,
                }
            ],
            "assignedDriverId": None,
            "attempt": 0,
            "maxAttempts": 1,
            "recoveryState": "none",
        }

    def _build_approval_request(
        self, mission_id: str, task_id: str, request_id: str, p: Dict[str, Any]
    ) -> Dict[str, Any]:
        scope = p.get("scope") or {"kind": "filesystem", "rootPath": "/tmp", "recursive": False}
        if "recursive" not in scope:
            scope = {**scope, "recursive": False}
        return {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "missionId": mission_id,
            "taskId": task_id,
            "requestedCapability": p.get("requestedCapability", "cap.fs.read"),
            "resource": p.get("resource", p.get("target", "/tmp")),
            "operation": p.get("operation", "RepositoryRead"),
            "scope": scope,
            "riskClassification": p.get("riskClassification", "low"),
            "policyReason": p.get("policyReason", "Operator-initiated consequential action requires approval."),
            "requestedBy": {"actorId": "exec-1", "kind": "execution_plane"},
            "expiresAt": p.get("expiresAt", "2030-01-01T00:00:00Z"),
            "remainingUses": p.get("remainingUses"),
            "correlationId": p.get("correlationId", "corr-m1"),
            "createdAt": self._now(),
        }

    def _reconstruct_mission(self, mission_id: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"missionId": mission_id, "taskId": None, "requestId": None}
        # Find a task belonging to this mission.
        for (sid, _kind, _ver) in self.store.all_aggregates():
            if sid.startswith("task-") or sid.startswith("human_approval-"):
                st = self.store.load_state(sid)
                if st and st.get("missionId") == mission_id:
                    if sid.startswith("task-"):
                        result["taskId"] = st.get("taskId")
                    elif sid.startswith("human_approval-"):
                        result["requestId"] = st.get("requestId")
        return result

    # -- command: submit_approval_decision -------------------------------

    def _cmd_submit_approval_decision(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        p = cmd["payload"]
        request_id = p["requestId"]
        stream = "human_approval-" + request_id
        if self.store.aggregate_version(stream) == 0:
            return self._receipt(
                cmd, status="rejected", classification="not_found",
                error=self._error_envelope(cmd, "not_found", "APPROVAL_NOT_FOUND"),
                stream_id=stream,
            )
        current = self.store.load_state(stream)
        # Idempotency replay: if this exact command idempotency key was already
        # committed, return the original result without a new event. This must
        # be checked before the aggregate transition (which would otherwise
        # raise IllegalTransition on an already-terminal request).
        prior = self.store.find_idempotent(cmd["idempotencyKey"])
        if prior is not None:
            return self._receipt(
                cmd, status="idempotent", classification="duplicate",
                result={"requestId": request_id, "state": current.get("state")},
                stream_id=stream,
            )
        # Expiry and terminal checks are enforced by the aggregate and the
        # store's idempotency layer. We do NOT short-circuit here: a replay with
        # the same idempotency key must return idempotent (not already_terminal),
        # and the store handles that. A different key on a terminal/expired
        # request raises IllegalTransition/AuthorityViolation -> classified.
        decision = {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "decision": p["decision"],  # "approve" | "deny"
            "operatorId": self.operator_id,  # bound, not taken from payload
            "decidedAt": self._now(),
            "note": p.get("note"),
            "idempotencyKey": cmd["idempotencyKey"],
            "correlationId": cmd["correlationId"],
            "sessionId": self.session_id,
        }
        meta = self._metadata(cmd, "submit_human_approval_decision", {"requestId": request_id})
        res = self.svc.submit_human_approval_decision(decision, meta)
        if res.get("replayed") or res.get("status") == "idempotent":
            return self._receipt(
                cmd, status="idempotent", classification="duplicate",
                result={"requestId": request_id, "state": self.store.load_state(stream)["state"]},
                stream_id=stream,
            )
        return self._receipt(
            cmd, status="accepted", classification="accepted",
            result={"requestId": request_id, "state": self.store.load_state(stream)["state"]},
            stream_id=stream,
        )

    # -- command: cancel_task / cancel_driver_run ------------------------

    def _cmd_cancel_task(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        return self._cancel(cmd, "task", cmd["payload"]["taskId"], self.svc.cancel_task)

    def _cmd_cancel_driver_run(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        return self._cancel(cmd, "driverrun", cmd["payload"]["driverRunId"], self.svc.cancel_driver_run)

    def _cancel(self, cmd: Dict[str, Any], kind: str, target_id: str, fn) -> Dict[str, Any]:
        stream = kind + "-" + target_id
        if self.store.aggregate_version(stream) == 0:
            return self._receipt(
                cmd, status="rejected", classification="not_found",
                error=self._error_envelope(cmd, "not_found", "TARGET_NOT_FOUND"),
                stream_id=stream,
            )
        current = self.store.load_state(stream)
        # Idempotency replay: if this exact command idempotency key was already
        # committed, return the original result without a new event. This must
        # be checked before the aggregate transition (which would otherwise
        # raise IllegalTransition on an already-terminal target).
        prior = self.store.find_idempotent(cmd["idempotencyKey"])
        if prior is not None:
            return self._receipt(
                cmd, status="idempotent", classification="duplicate",
                result={"targetId": target_id, "state": current.get("state")},
                stream_id=stream,
            )
        # Terminal check; a different key on a terminal target raises
        # IllegalTransition -> already_terminal.
        meta = self._metadata(cmd, "cancel_" + kind, {kind + "Id": target_id})
        res = fn(target_id, cmd["payload"].get("reason", "Operator cancelled."), meta)
        if res.get("replayed") or res.get("status") == "idempotent":
            return self._receipt(
                cmd, status="idempotent", classification="duplicate",
                result={"targetId": target_id, "state": self.store.load_state(stream)["state"]},
                stream_id=stream,
            )
        return self._receipt(
            cmd, status="accepted", classification="accepted",
            result={"targetId": target_id, "state": self.store.load_state(stream)["state"]},
            stream_id=stream,
        )

    # -- receipt / error helpers -----------------------------------------

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
            "occurredAt": self._now(),
            "correlationId": cmd.get("correlationId"),
            "streamId": None,
            "expectedVersion": cmd.get("expectedVersion"),
            "actualVersion": None,
        }
