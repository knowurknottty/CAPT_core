"""Runtime-owned planning for bounded model-execution human approval.

The operator surface submits intent.  CAPT binds the model-visible prompt to
provider/model selection, requested context policy, verification preference,
resource/run identity, requested Hermes executable selector, and the exact
outbound driver prompt digest.  Mutation still occurs only through
RuntimeService; UI state is never accepted as approval authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from . import commands
from .authored_skills import prepare_runtime_skill_context, summarize_skill_context
from .contracts import require
from .errors import AuthorityViolation
from .model_approval_binding import (
    build_bound_model_operator_approval,
    staging_root_for_ledger,
)
from .continuation_context import select_continuation_context


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
    explicit_mission = bool(str(intent.get("missionId") or "").strip())
    mission_id = str(intent.get("missionId") or ("m-model-" + suffix))
    task_id = str(intent.get("taskId") or (
        mission_id + "-task-" + suffix if explicit_mission else mission_id + "-task-1"
    ))
    driver_run_id = str(intent.get("driverRunId") or ("dr-model-" + suffix))
    response_mode = str(intent.get("responseMode", "SPOCK"))
    enhancement_engine = str(intent.get("promptEnhancement", "OFF"))
    provider = str(intent.get("provider", "")).strip()
    model = str(intent.get("model", "")).strip()
    requested_context_budget = int(intent.get("requestedContextBudget", 32_000))
    human_verification_required = bool(intent.get("humanVerificationRequired", True))
    executable = str(intent.get("executable", "") or "")
    # Explicit authored-skill selection is verified before approval state exists.
    # The resulting exact bytes are included in the approved model-visible prompt.
    skill_context, skill_names = prepare_runtime_skill_context(
        intent, state_root=Path(service.store.path).parent
    )
    # Governed continuation context selection: the approval binding must be
    # computed against the SAME prior-evidence selection the run will use, so
    # the approval digest and the prepared/dispatch digest stay consistent
    # (context selected before approval == context shown to the model).
    ledger_dir = str(Path(service.store.path).parent)
    continuation = select_continuation_context(
        service.store, mission_id, task_id,
        exclude_run_id=driver_run_id, ledger_dir=ledger_dir,
    )
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
        context_pack_digest=continuation["contextPackDigest"],
        continuation_context=continuation["records"],
        authored_skill_context=skill_context,
        proposal_binding={
            key: intent[key] for key in (
                "proposalId", "proposalRevision", "proposalSnapshotDigest",
                "originalHumanPromptDigest", "selectedPromptKind", "selectedPromptDigest",
            ) if key in intent
        } or None,
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
        operation_fingerprint=commands.fingerprint(
            "request_human_approval",
            {
                "requestId": request_id,
                "promptAssemblyDigest": assembly["promptAssemblyDigest"],
                "approvalAttemptId": suffix,
            },
        ),
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
        "authoredSkills": summarize_skill_context(skill_context),
        "skillNames": skill_names,
        "expiresAt": authoritative["expiresAt"],
    }
