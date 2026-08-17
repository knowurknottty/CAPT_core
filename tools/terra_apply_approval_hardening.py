from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


def write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


write(
    "capt_runtime/model_approval_binding.py",
    '''"""Canonical execution binding for governed model-operator approvals.

The human-visible/model-visible prompt is only one part of execution identity.
This module binds it to the concrete run identity and to the exact text that
will cross the selected driver boundary.  It is pure construction code: no
approval state is created or consumed here.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict

from .contracts import digest
from .drivers.hermes import build_prompt as build_hermes_prompt
from .operator_provenance import build_model_operator_prompt_assembly

MODEL_OPERATOR_OPERATIONS = [
    "RepositoryRead",
    "FilesystemRead",
    "ArtifactCreate",
    "AnalysisOnly",
]
MODEL_OPERATOR_TOOLS = ["terminal"]
MODEL_OPERATOR_BUDGETS = {
    "maxSeconds": 600,
    "maxArtifacts": 1,
    "maxObservations": 10,
}


def raw_text_digest(text: str) -> str:
    """Digest exact UTF-8 bytes sent to an external model boundary."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def staging_root_for_ledger(ledger_path: str, driver_run_id: str) -> str:
    return str(Path(ledger_path).parent / "staging" / driver_run_id)


def build_bound_model_operator_approval(
    *,
    human_prompt: str,
    response_mode: str,
    enhancement_engine: str,
    mission_id: str,
    task_id: str,
    driver_run_id: str,
    target_root: str,
    provider: str,
    model: str,
    requested_context_budget: int,
    human_verification_required: bool,
    executable: str,
    staging_root: str,
) -> Dict[str, Any]:
    """Return the model-visible assembly plus its execution admission binding."""
    assembly = build_model_operator_prompt_assembly(
        human_prompt=human_prompt,
        response_mode=response_mode,
        enhancement_engine=enhancement_engine,
    )
    provider_id = str(provider or "")
    model_id = str(model or "")
    executable_selector = str(executable or "")
    driver_kind = "provider" if provider_id else "hermes"

    if driver_kind == "provider":
        dispatch_prompt = assembly["modelVisiblePrompt"]
    else:
        dispatch_prompt = build_hermes_prompt(
            {
                "filesystemPolicy": {
                    "rootPath": target_root,
                    "allowedPaths": [target_root, staging_root],
                    "writesAllowed": False,
                },
                "permittedTools": list(MODEL_OPERATOR_TOOLS),
                "budgets": dict(MODEL_OPERATOR_BUDGETS),
            },
            list(MODEL_OPERATOR_OPERATIONS),
            objective=assembly["modelVisiblePrompt"],
        )

    dispatch_prompt_digest = raw_text_digest(dispatch_prompt)
    binding = {
        "missionId": mission_id,
        "taskId": task_id,
        "driverRunId": driver_run_id,
        "targetRoot": target_root,
        "provider": provider_id,
        "model": model_id,
        "requestedContextBudget": int(requested_context_budget),
        "humanVerificationRequired": bool(human_verification_required),
        "executable": executable_selector,
        "driverKind": driver_kind,
        "basePromptAssemblyDigest": assembly["promptAssemblyDigest"],
        "dispatchPromptDigest": dispatch_prompt_digest,
    }
    approval_digest = digest(
        {
            "basePromptAssemblyDigest": assembly["promptAssemblyDigest"],
            "executionBinding": binding,
        }
    )
    return {
        **assembly,
        "basePromptAssemblyDigest": assembly["promptAssemblyDigest"],
        "promptAssemblyDigest": approval_digest,
        "executionBinding": binding,
        "dispatchPromptDigest": dispatch_prompt_digest,
    }
''',
)

write(
    "capt_runtime/approval_dispatch.py",
    '''"""In-process fail-closed check for exact model text at driver dispatch.

RuntimeService remains the durable authority.  This registry carries the
already-authorized dispatch digest across the final in-process seam from the
command service to a driver.  Standalone driver conformance tests that do not
use the governed model-operator command path have no registered expectation.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional

from .errors import AuthorityViolation

_LOCK = threading.RLock()
_EXPECTED: Dict[str, str] = {}


def register_expected_prompt_digest(driver_run_id: str, prompt_digest: str) -> None:
    if not driver_run_id or not prompt_digest:
        raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DISPATCH_BINDING_MISSING")
    with _LOCK:
        prior = _EXPECTED.get(driver_run_id)
        if prior is not None and prior != prompt_digest:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DISPATCH_BINDING_CONFLICT")
        _EXPECTED[driver_run_id] = prompt_digest


def require_expected_prompt_digest(driver_run_id: str, actual_digest: str) -> Optional[str]:
    """Verify a registered governed run; leave standalone driver calls untouched."""
    with _LOCK:
        expected = _EXPECTED.get(driver_run_id)
    if expected is None:
        return None
    if expected != actual_digest:
        raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DISPATCH_DIGEST_MISMATCH")
    return expected
''',
)

write(
    "capt_runtime/prompt_approval.py",
    '''"""Runtime-owned planning for bounded model-execution human approval.

The operator surface submits intent.  CAPT binds the model-visible prompt to
provider/model selection, requested context policy, verification preference,
resource/run identity, requested Hermes executable selector, and the exact
outbound driver prompt digest.  Mutation still occurs only through
RuntimeService; UI state is never accepted as approval authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from . import commands
from .contracts import require
from .errors import AuthorityViolation
from .model_approval_binding import (
    build_bound_model_operator_approval,
    staging_root_for_ledger,
)


def _expiry_from(issued_at: str) -> str:
    """Return a deterministic 15-minute approval window from command issuance."""
    try:
        stamp = issued_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(stamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    return (dt + timedelta(minutes=15)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _attempt_suffix(idempotency_key: str) -> str:
    return commands.fingerprint(
        "model_prompt_approval_attempt", {"idempotencyKey": idempotency_key}
    ).split(":", 1)[1][:24]


def request_model_prompt_approval(
    service: Any,
    intent: Dict[str, Any],
    operator_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Plan and persist one one-use approval for a concrete model execution."""
    require("CommandMetadata", operator_metadata)
    if operator_metadata.get("actor", {}).get("kind") != "human":
        raise AuthorityViolation("MODEL_PROMPT_APPROVAL_MUST_BE_HUMAN_AUTHORED")

    objective = str(intent.get("objective", "")).strip()
    target_root = str(intent.get("targetRoot", "")).strip()
    if not objective or not target_root:
        raise AuthorityViolation("MODEL_PROMPT_APPROVAL_OBJECTIVE_OR_TARGET_MISSING")

    suffix = _attempt_suffix(operator_metadata["idempotencyKey"])
    request_id = str(intent.get("requestId") or ("approval-model-" + suffix))
    mission_id = str(intent.get("missionId") or ("m-model-" + suffix))
    task_id = str(intent.get("taskId") or (mission_id + "-task-1"))
    driver_run_id = str(intent.get("driverRunId") or ("dr-model-" + suffix))
    response_mode = str(intent.get("responseMode", "SPOCK"))
    enhancement_engine = str(intent.get("promptEnhancement", "OFF"))
    provider = str(intent.get("provider", "")).strip()
    model = str(intent.get("model", "")).strip()
    requested_context_budget = int(intent.get("requestedContextBudget", 32_000))
    human_verification_required = bool(intent.get("humanVerificationRequired", True))
    executable = str(intent.get("executable", "") or "")
    assembly = build_bound_model_operator_approval(
        human_prompt=objective,
        response_mode=response_mode,
        enhancement_engine=enhancement_engine,
        mission_id=mission_id,
        task_id=task_id,
        driver_run_id=driver_run_id,
        target_root=target_root,
        provider=provider,
        model=model,
        requested_context_budget=requested_context_budget,
        human_verification_required=human_verification_required,
        executable=executable,
        staging_root=staging_root_for_ledger(service.store.path, driver_run_id),
    )
    expires_at = str(intent.get("expiresAt") or _expiry_from(operator_metadata["issuedAt"]))
    request = {
        "schemaVersion": "1.0.0",
        "requestId": request_id,
        "missionId": mission_id,
        "taskId": task_id,
        "requestedCapability": "cap.fs.read",
        "resource": target_root,
        "operation": "ModelOperatorInspection",
        "scope": {
            "kind": "filesystem",
            "rootPath": target_root,
            "recursive": True,
            "approvalBinding": assembly["executionBinding"],
        },
        "riskClassification": "low",
        "policyReason": (
            "Approve one concrete %s/%s read-only model execution bound to exact dispatch text."
            % (provider or "hermes", model or "hermes")
        ),
        "requestedBy": {"actorId": "exec-1", "kind": "execution_plane"},
        "expiresAt": expires_at,
        "remainingUses": 1,
        "correlationId": operator_metadata["correlationId"],
        "createdAt": operator_metadata["issuedAt"],
        "promptAssemblyDigest": assembly["promptAssemblyDigest"],
    }
    inner_metadata = commands.command(
        command_id=("cmd-model-approval-" + suffix),
        idempotency_key=("idem-model-approval-" + suffix),
        operation_fingerprint=commands.fingerprint("request_human_approval", request),
        correlation_id=operator_metadata["correlationId"],
        actor_id="exec-1",
        actor_kind="execution_plane",
        issued_at=operator_metadata["issuedAt"],
        replay_policy="never",
    )
    result = service.request_human_approval(request, inner_metadata)
    authoritative = service.store.require_state("human_approval-" + request_id)
    return {
        "status": result.get("status", "applied"),
        "requestId": request_id,
        "missionId": mission_id,
        "taskId": task_id,
        "driverRunId": driver_run_id,
        "promptAssemblyDigest": authoritative["promptAssemblyDigest"],
        "basePromptAssemblyDigest": assembly["basePromptAssemblyDigest"],
        "dispatchPromptDigest": assembly["dispatchPromptDigest"],
        "modelVisiblePromptDigest": assembly["modelVisiblePromptDigest"],
        "expiresAt": authoritative["expiresAt"],
    }
''',
)

replace_once(
    "capt_runtime/authority.py",
    '    "submit_human_approval_decision": frozenset({HUMAN}),\n',
    '    "submit_human_approval_decision": frozenset({HUMAN}),\n    "consume_human_approval": frozenset({EXECUTION, SYSTEM}),\n',
)

replace_once(
    "contracts/schema/common.schema.json",
    '''    "Principal": {
''',
    '''    "HumanApprovalConsumption": {
      "title": "HumanApprovalConsumption",
      "description": "Durable one-use admission of a previously approved model execution.",
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schemaVersion", "requestId", "useId", "consumedAt", "missionId",
        "taskId", "driverRunId", "resource", "operation", "promptAssemblyDigest"
      ],
      "properties": {
        "schemaVersion": { "$ref": "common.schema.json#/$defs/SchemaVersion" },
        "requestId": { "$ref": "common.schema.json#/$defs/Identifier" },
        "useId": { "$ref": "common.schema.json#/$defs/Identifier" },
        "consumedAt": { "$ref": "common.schema.json#/$defs/Timestamp" },
        "missionId": { "$ref": "common.schema.json#/$defs/Identifier" },
        "taskId": { "$ref": "common.schema.json#/$defs/Identifier" },
        "driverRunId": { "$ref": "common.schema.json#/$defs/Identifier" },
        "resource": { "type": "string", "maxLength": 1024 },
        "operation": { "type": "string", "maxLength": 128 },
        "promptAssemblyDigest": { "$ref": "common.schema.json#/$defs/Digest" }
      }
    },
    "Principal": {
''',
)

replace_once(
    "contracts/schema/event.schema.json",
    '''        "HumanApprovalRequested",
        "HumanApprovalDecided"
''',
    '''        "HumanApprovalRequested",
        "HumanApprovalDecided",
        "HumanApprovalConsumed"
''',
)
replace_once(
    "contracts/schema/event.schema.json",
    '''        {
          "title": "HumanApprovalDecidedPayload",
          "type": "object",
          "additionalProperties": false,
          "required": ["eventType", "decision"],
          "properties": {
            "eventType": { "type": "string", "const": "HumanApprovalDecided" },
            "decision": { "$ref": "common.schema.json#/$defs/HumanApprovalDecision" }
          }
        }
''',
    '''        {
          "title": "HumanApprovalDecidedPayload",
          "type": "object",
          "additionalProperties": false,
          "required": ["eventType", "decision"],
          "properties": {
            "eventType": { "type": "string", "const": "HumanApprovalDecided" },
            "decision": { "$ref": "common.schema.json#/$defs/HumanApprovalDecision" }
          }
        },
        {
          "title": "HumanApprovalConsumedPayload",
          "type": "object",
          "additionalProperties": false,
          "required": ["eventType", "consumption"],
          "properties": {
            "eventType": { "type": "string", "const": "HumanApprovalConsumed" },
            "consumption": { "$ref": "common.schema.json#/$defs/HumanApprovalConsumption" }
          }
        }
''',
)

replace_once(
    "capt_runtime/aggregates/human_approval.py",
    'APPROVAL_TERMINAL: FrozenSet[str] = frozenset({"approved", "denied", "expired"})\n\nAPPROVAL_TRANSITIONS: Dict[str, FrozenSet[str]] = {\n    "requested": frozenset({"approved", "denied", "expired"}),\n    "approved": frozenset(),\n    "denied": frozenset(),\n    "expired": frozenset(),\n}\n',
    'APPROVAL_TERMINAL: FrozenSet[str] = frozenset({"denied", "expired", "consumed"})\n\nAPPROVAL_TRANSITIONS: Dict[str, FrozenSet[str]] = {\n    "requested": frozenset({"approved", "denied", "expired"}),\n    "approved": frozenset({"consumed", "expired"}),\n    "denied": frozenset(),\n    "expired": frozenset(),\n    "consumed": frozenset(),\n}\n',
)
replace_once(
    "capt_runtime/aggregates/human_approval.py",
    '            "human_approval.decidedIdempotencyKeys",\n',
    '            "human_approval.decidedIdempotencyKeys",\n            "human_approval.remainingUses",\n            "human_approval.consumedAt",\n            "human_approval.consumedBy",\n',
)
replace_once(
    "capt_runtime/aggregates/human_approval.py",
    '            "decidedIdempotencyKeys": [],\n',
    '            "decidedIdempotencyKeys": [],\n            "consumedAt": None,\n            "consumedBy": None,\n',
)
replace_once(
    "capt_runtime/aggregates/human_approval.py",
    '''        if current in APPROVAL_TERMINAL:
            raise IllegalTransition(
                "approval %s is terminal" % state["requestId"], current,
                decision["decision"],
            )

        decision_value = decision["decision"]
''',
    '''        if current != "requested":
            raise IllegalTransition(
                "approval %s cannot be decided from %s" % (state["requestId"], current),
                current,
                decision["decision"],
            )

        decision_value = decision["decision"]
''',
)
replace_once(
    "capt_runtime/aggregates/human_approval.py",
    '''    @staticmethod
    def mark_expired(state: Dict[str, Any]) -> Dict[str, Any]:
        if state["state"] in APPROVAL_TERMINAL:
            return state
        nxt = dict(state)
        nxt["state"] = "expired"
        return nxt
''',
    '''    @staticmethod
    def mark_expired(state: Dict[str, Any]) -> Dict[str, Any]:
        if state["state"] in APPROVAL_TERMINAL:
            return state
        nxt = dict(state)
        nxt["state"] = "expired"
        return nxt

    @staticmethod
    def consume(state: Dict[str, Any], use_id: str, now: str) -> Dict[str, Any]:
        if state.get("state") != "approved":
            raise IllegalTransition(
                "approval %s cannot be consumed from %s"
                % (state["requestId"], state.get("state")),
                str(state.get("state")),
                "consumed",
            )
        if now > state["expiresAt"]:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_EXPIRED")
        remaining = state.get("remainingUses")
        if remaining is None or int(remaining) < 1:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_USE_LIMIT_MISSING")
        nxt = dict(state)
        nxt["remainingUses"] = int(remaining) - 1
        nxt["consumedAt"] = now
        nxt["consumedBy"] = use_id
        if nxt["remainingUses"] == 0:
            nxt["state"] = "consumed"
        return nxt
''',
)

old_services = '''    def request_human_approval(
        self, request: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("HumanApprovalRequest", request)
        require("CommandMetadata", metadata)
        require_authority("request_human_approval", metadata["actor"]["kind"])
        return self._commit(
            [self._append_request_human_approval(request, metadata)], metadata
        )
'''
new_services = '''    def request_human_approval(
        self, request: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        require("HumanApprovalRequest", request)
        require("CommandMetadata", metadata)
        require_authority("request_human_approval", metadata["actor"]["kind"])
        prior = self.store.find_idempotent(metadata["idempotencyKey"])
        if prior is not None:
            return self._commit([], metadata)
        stream = HumanApprovalAggregate.stream_id(request["requestId"])
        if self.store.aggregate_version(stream) != 0:
            raise AuthorityViolation("HUMAN_APPROVAL_REQUEST_ALREADY_EXISTS")
        return self._commit(
            [self._append_request_human_approval(request, metadata)], metadata
        )
'''
replace_once("capt_runtime/services.py", old_services, new_services)
replace_once(
    "capt_runtime/services.py",
    '        expected = self.store.aggregate_version(stream)\n        state = HumanApprovalAggregate.create(request)\n        event = commands.envelope(\n',
    '        expected = 0\n        state = HumanApprovalAggregate.create(request)\n        event = commands.envelope(\n',
)
old_require = '''    def require_approved_prompt_assembly(
        self, request_id: str, prompt_assembly_digest: str, operation: str
    ) -> Dict[str, Any]:
        """Fail closed unless durable human approval binds this exact assembly.

        This read-only RuntimeService check trusts neither a UI boolean nor a
        client-supplied approval state. OFF is no transform, not no governance.
        """
        state = self.store.require_state(HumanApprovalAggregate.stream_id(request_id))
        if state.get("state") != "approved":
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_NOT_APPROVED")
        if state.get("operation") != operation:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_OPERATION_MISMATCH")
        if state.get("promptAssemblyDigest") != prompt_assembly_digest:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH")
        return state
'''
new_require = '''    def require_approved_prompt_assembly(
        self, request_id: str, prompt_assembly_digest: str, operation: str
    ) -> Dict[str, Any]:
        """Compatibility read-check for the prompt portion of a governed approval.

        Consequential model execution MUST use ``admit_approved_model_execution``
        first.  This check remains for the existing runner's later prompt-only
        assertion and therefore accepts the persisted full binding digest or its
        explicitly persisted base prompt-assembly digest.
        """
        state = self.store.require_state(HumanApprovalAggregate.stream_id(request_id))
        if state.get("state") not in ("approved", "consumed"):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_NOT_APPROVED")
        if _now_rfc3339() > state.get("expiresAt", ""):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_EXPIRED")
        if state.get("operation") != operation:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_OPERATION_MISMATCH")
        binding = (state.get("scope") or {}).get("approvalBinding") or {}
        accepted_digests = {
            state.get("promptAssemblyDigest"),
            binding.get("basePromptAssemblyDigest"),
        }
        if prompt_assembly_digest not in accepted_digests:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH")
        return state

    def admit_approved_model_execution(
        self,
        request_id: str,
        prompt_assembly_digest: str,
        operation: str,
        *,
        mission_id: str,
        task_id: str,
        driver_run_id: str,
        resource: str,
        use_id: str,
        now: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Atomically bind and consume one approved model execution admission."""
        require("CommandMetadata", metadata)
        require_authority("consume_human_approval", metadata["actor"]["kind"])
        stream = HumanApprovalAggregate.stream_id(request_id)
        current = self.store.require_state(stream)
        if current.get("operation") != operation:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_OPERATION_MISMATCH")
        if current.get("promptAssemblyDigest") != prompt_assembly_digest:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DIGEST_MISMATCH")
        binding = (current.get("scope") or {}).get("approvalBinding") or {}
        checks = (
            ("missionId", mission_id, "MODEL_PROMPT_APPROVAL_MISSION_MISMATCH"),
            ("taskId", task_id, "MODEL_PROMPT_APPROVAL_TASK_MISMATCH"),
            ("driverRunId", driver_run_id, "MODEL_PROMPT_APPROVAL_DRIVER_RUN_MISMATCH"),
            ("targetRoot", resource, "MODEL_PROMPT_APPROVAL_RESOURCE_MISMATCH"),
        )
        for key, offered, code in checks:
            if str(binding.get(key, "")) != str(offered):
                raise AuthorityViolation(code)
        if str(current.get("resource", "")) != str(resource):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_RESOURCE_MISMATCH")
        if current.get("state") == "consumed":
            if current.get("consumedBy") == use_id:
                return {**current, "status": "idempotent"}
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_CONSUMED")
        if current.get("state") != "approved":
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_NOT_APPROVED")
        if now > current.get("expiresAt", ""):
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_EXPIRED")
        if current.get("remainingUses") != 1:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_ONE_USE_REQUIRED")

        expected = self.store.aggregate_version(stream)
        state = HumanApprovalAggregate.consume(current, use_id, now)
        consumption = {
            "schemaVersion": "1.0.0",
            "requestId": request_id,
            "useId": use_id,
            "consumedAt": now,
            "missionId": mission_id,
            "taskId": task_id,
            "driverRunId": driver_run_id,
            "resource": resource,
            "operation": operation,
            "promptAssemblyDigest": prompt_assembly_digest,
        }
        require("HumanApprovalConsumption", consumption)
        event = commands.envelope(
            event_id=metadata["commandId"] + "-ev1",
            stream_id=stream,
            event_type="HumanApprovalConsumed",
            payload={"eventType": "HumanApprovalConsumed", "consumption": consumption},
            metadata=metadata,
            occurred_at=metadata["issuedAt"],
            mission_id=mission_id,
            task_id=task_id,
        )
        committed = self._commit(
            [AppendRequest(stream, HumanApprovalAggregate.KIND, expected, event, state)],
            metadata,
        )
        return {**state, "status": committed.get("status", "applied")}
'''
replace_once("capt_runtime/services.py", old_require, new_require)

replace_once(
    "desktop/desktop_runtime_client.py",
    '            "correlationId": "corr-" + uuid.uuid4().hex,\n',
    '            "correlationId": "corr-" + hashlib.sha256((op + ":" + idek).encode()).hexdigest()[:24],\n',
)

replace_once(
    "desktop/m1_command_service.py",
    'from capt_runtime.prompt_approval import request_model_prompt_approval\n',
    'from capt_runtime.approval_dispatch import register_expected_prompt_digest\nfrom capt_runtime.model_approval_binding import (\n    build_bound_model_operator_approval,\n    staging_root_for_ledger,\n)\nfrom capt_runtime.prompt_approval import request_model_prompt_approval\n',
)
old_run_block = '''            elif op == "run_approved_hermes_inspection":
                runner = getattr(self, "approved_hermes_runner", None)
                if runner is None:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal_failure",
                        error=self._error_envelope(
                            cmd, "internal_failure", "HERMES_DRIVER_UNAVAILABLE"
                        ),
                    )
                result = runner(cmd)
'''
new_run_block = '''            elif op == "run_approved_hermes_inspection":
                runner = getattr(self, "approved_hermes_runner", None)
                if runner is None:
                    return self._receipt(
                        cmd,
                        status="rejected",
                        classification="internal_failure",
                        error=self._error_envelope(
                            cmd, "internal_failure", "HERMES_DRIVER_UNAVAILABLE"
                        ),
                    )
                p = cmd["payload"]
                approval_request_id = str(p.get("approvalRequestId", ""))
                if not approval_request_id:
                    from capt_runtime.errors import AuthorityViolation
                    raise AuthorityViolation("MODEL_PROMPT_APPROVAL_RECEIPT_REQUIRED")
                mission_id = str(p.get("missionId") or ("m-model-" + cmd["commandId"]))
                task_id = str(p.get("taskId") or (mission_id + "-task-1"))
                driver_run_id = str(p.get("driverRunId") or ("dr-model-" + cmd["commandId"]))
                target_root = str(p.get("targetRoot", ""))
                assembly = build_bound_model_operator_approval(
                    human_prompt=str(p.get("objective", "")),
                    response_mode=str(p.get("responseMode", "SPOCK")),
                    enhancement_engine=str(p.get("promptEnhancement", "OFF")),
                    mission_id=mission_id,
                    task_id=task_id,
                    driver_run_id=driver_run_id,
                    target_root=target_root,
                    provider=str(p.get("provider", "") or ""),
                    model=str(p.get("model", "") or ""),
                    requested_context_budget=int(p.get("requestedContextBudget", 32_000)),
                    human_verification_required=bool(p.get("humanVerificationRequired", True)),
                    executable=str(p.get("executable", "") or ""),
                    staging_root=staging_root_for_ledger(self.store.path, driver_run_id),
                )
                use_meta = commands.command(
                    command_id="cmd-approval-use-" + commands.fingerprint(
                        "approval-use", {"idempotencyKey": cmd["idempotencyKey"]}
                    ).split(":", 1)[1][:24],
                    idempotency_key="idem-approval-use-" + commands.fingerprint(
                        "approval-use", {"idempotencyKey": cmd["idempotencyKey"]}
                    ).split(":", 1)[1][:24],
                    operation_fingerprint=commands.fingerprint(
                        "consume_human_approval",
                        {
                            "requestId": approval_request_id,
                            "promptAssemblyDigest": assembly["promptAssemblyDigest"],
                            "missionId": mission_id,
                            "taskId": task_id,
                            "driverRunId": driver_run_id,
                            "resource": target_root,
                            "useId": cmd["idempotencyKey"],
                        },
                    ),
                    correlation_id=cmd["correlationId"],
                    actor_id="exec-1",
                    actor_kind="execution_plane",
                    issued_at=cmd.get("timestamp") or _now_rfc3339(),
                    replay_policy="never",
                )
                self.svc.admit_approved_model_execution(
                    approval_request_id,
                    assembly["promptAssemblyDigest"],
                    "ModelOperatorInspection",
                    mission_id=mission_id,
                    task_id=task_id,
                    driver_run_id=driver_run_id,
                    resource=target_root,
                    use_id=cmd["idempotencyKey"],
                    now=cmd.get("timestamp") or _now_rfc3339(),
                    metadata=use_meta,
                )
                register_expected_prompt_digest(
                    driver_run_id, assembly["dispatchPromptDigest"]
                )
                result = runner(cmd)
'''
replace_once("desktop/m1_command_service.py", old_run_block, new_run_block)

replace_once(
    "capt_runtime/drivers/hermes.py",
    'from ..contracts import require\n',
    'from ..approval_dispatch import require_expected_prompt_digest\nfrom ..contracts import require\n',
)
replace_once(
    "capt_runtime/drivers/hermes.py",
    '''        prompt = build_prompt(
            ctx, work_order["operations"], objective=resolved.objective if resolved else None
        )
''',
    '''        prompt = build_prompt(
            ctx, work_order["operations"], objective=resolved.objective if resolved else None
        )
        prompt_digest = "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        require_expected_prompt_digest(run_id, prompt_digest)
''',
)
replace_once(
    "capt_runtime/drivers/hermes.py",
    '            "envKeys": sorted(env.keys()),\n',
    '            "envKeys": sorted(env.keys()),\n            "promptDigest": prompt_digest,\n',
)

replace_once(
    "capt_runtime/drivers/provider.py",
    'from typing import Any, Dict\n\nDRIVER_ID = "provider"\n',
    'from typing import Any, Dict\n\nfrom ..approval_dispatch import require_expected_prompt_digest\n\nDRIVER_ID = "provider"\n',
)
replace_once(
    "capt_runtime/drivers/provider.py",
    '        prompt_digest = "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()\n',
    '        prompt_digest = "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()\n        require_expected_prompt_digest(rid, prompt_digest)\n',
)

replace_once(
    "desktop/capt_runtime_service.py",
    '"commandOperations": ["create_mission", "submit_approval_decision", "cancel_task", "cancel_driver_run", "update_memory_trigger_policy", "run_fixed_openharness_inspection", "run_approved_hermes_inspection", "checkpoint_runtime", "shutdown", "resume_runtime"],',
    '"commandOperations": ["create_mission", "request_model_prompt_approval", "submit_approval_decision", "cancel_task", "cancel_driver_run", "update_memory_trigger_policy", "run_fixed_openharness_inspection", "run_approved_hermes_inspection", "checkpoint_runtime", "shutdown", "resume_runtime"],',
)

replace_once(
    "capt_ui/surfaces/tui/app.py",
    '''            "promptEnhancement": engine,
            "responseMode": str(self.query_one("#response-mode", Select).value),
        }
        try:
            request_receipt = self._op.request_prompt_approval(payload)
''',
    '''            "promptEnhancement": engine,
            "responseMode": str(self.query_one("#response-mode", Select).value),
            "requestedContextBudget": int(str(self.query_one("#context-budget", Select).value)),
            "humanVerificationRequired": self.query_one("#human-verification", Checkbox).value,
        }
        try:
            request_receipt = self._op.request_prompt_approval(
                payload, "tui-approval-" + uuid.uuid4().hex
            )
''',
)

print("TERRA_APPROVAL_HARDENING_PATCH_APPLIED")
