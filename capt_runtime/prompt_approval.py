"""Runtime-owned planning for exact model-prompt human approval.

The operator surface submits intent. This module builds the exact model-visible
PromptAssembly identity and the HumanApprovalRequest. Mutation still occurs
only through RuntimeService; UI state is never accepted as approval authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from . import commands
from .contracts import require
from .errors import AuthorityViolation
from .operator_provenance import build_model_operator_prompt_assembly


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


def request_model_prompt_approval(
    service: Any,
    intent: Dict[str, Any],
    operator_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Plan and persist one bounded approval request for an exact prompt assembly.

    The authenticated outer command must be human-authored. The resulting
    HumanApprovalRequest is authored by the execution plane, as required by the
    existing runtime authority matrix. Planned run IDs are stable for an exact
    command envelope retry and distinct for a new operator approval attempt.
    """
    require("CommandMetadata", operator_metadata)
    actor_kind = operator_metadata.get("actor", {}).get("kind")
    if actor_kind != "human":
        raise AuthorityViolation("MODEL_PROMPT_APPROVAL_MUST_BE_HUMAN_AUTHORED")

    objective = str(intent.get("objective", "")).strip()
    target_root = str(intent.get("targetRoot", "")).strip()
    if not objective or not target_root:
        raise AuthorityViolation("MODEL_PROMPT_APPROVAL_OBJECTIVE_OR_TARGET_MISSING")

    response_mode = str(intent.get("responseMode", "SPOCK"))
    enhancement_engine = str(intent.get("promptEnhancement", "OFF"))
    provider = str(intent.get("provider", "")).strip() or "unspecified"
    model = str(intent.get("model", "")).strip() or "unspecified"
    assembly = build_model_operator_prompt_assembly(
        human_prompt=objective,
        response_mode=response_mode,
        enhancement_engine=enhancement_engine,
    )

    # RuntimeClient gives every operator command envelope a fresh correlation
    # id. Exact envelope retries retain it; a deliberate new approval attempt
    # gets a new one even when the prompt payload is unchanged.
    suffix = operator_metadata["correlationId"]
    request_id = str(intent.get("requestId") or ("approval-model-" + suffix))
    mission_id = str(intent.get("missionId") or ("m-model-" + suffix))
    task_id = str(intent.get("taskId") or (mission_id + "-task-1"))
    driver_run_id = str(intent.get("driverRunId") or ("dr-model-" + suffix))

    request = {
        "schemaVersion": "1.0.0",
        "requestId": request_id,
        "missionId": mission_id,
        "taskId": task_id,
        "requestedCapability": "cap.fs.read",
        "resource": target_root,
        "operation": "ModelOperatorInspection",
        "scope": {"kind": "filesystem", "rootPath": target_root, "recursive": True},
        "riskClassification": "low",
        "policyReason": (
            "Approve exact model-visible assembly for %s/%s read-only inspection."
            % (provider, model)
        ),
        "requestedBy": {"actorId": "exec-1", "kind": "execution_plane"},
        "expiresAt": str(intent.get("expiresAt") or _expiry_from(operator_metadata["issuedAt"])),
        "correlationId": operator_metadata["correlationId"],
        "createdAt": operator_metadata["issuedAt"],
        "promptAssemblyDigest": assembly["promptAssemblyDigest"],
    }
    inner_metadata = commands.command(
        command_id=(operator_metadata["commandId"] + ":" + suffix + ":approval"),
        idempotency_key=(operator_metadata["idempotencyKey"] + ":" + suffix + ":approval"),
        operation_fingerprint=commands.fingerprint("request_human_approval", request),
        correlation_id=operator_metadata["correlationId"],
        actor_id="exec-1",
        actor_kind="execution_plane",
        issued_at=operator_metadata["issuedAt"],
        replay_policy="never",
    )
    result = service.request_human_approval(request, inner_metadata)
    return {
        "status": result.get("status", "applied"),
        "requestId": request_id,
        "missionId": mission_id,
        "taskId": task_id,
        "driverRunId": driver_run_id,
        "promptAssemblyDigest": assembly["promptAssemblyDigest"],
        "modelVisiblePromptDigest": assembly["modelVisiblePromptDigest"],
        "expiresAt": request["expiresAt"],
    }
