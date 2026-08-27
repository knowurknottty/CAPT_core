"""Durable PromptProposal planning and exact HumanApproval selection."""
from __future__ import annotations

from typing import Any, Dict

from . import commands
from .aggregates.prompt_proposal import PromptProposalAggregate
from .contracts import digest, require
from .errors import AuthorityViolation
from .prompt_approval import request_model_prompt_approval
from .prompt_compiler import PromptCompileRequest, PromptCompiler
from .store import AppendRequest


def _suffix(key: str) -> str:
    value = commands.fingerprint("prompt_proposal_attempt", {"idempotencyKey": key})
    return value.split(":", 1)[1][:24]


def _require_human(metadata: Dict[str, Any]) -> None:
    require("CommandMetadata", metadata)
    if metadata.get("actor", {}).get("kind") != "human":
        raise AuthorityViolation("PROMPT_PROPOSAL_MUST_BE_HUMAN_AUTHORED")


def _stage_record(record: Any, proposal: Any) -> Dict[str, Any]:
    provenance = {"stage": record.stage.value, "version": record.version,
                  "inputDigest": record.input_digest, "outputDigest": record.output_digest,
                  "provider": record.provider_id, "model": record.model,
                  "endpointClass": record.endpoint_class,
                  "executionEnabled": record.execution_enabled}
    return {
        "stage": record.stage.value, "version": record.version,
        "proposedPromptDigest": record.output_digest,
        "rationale": proposal.rationale or "Bounded prompt-intelligence stage.",
        "assumptions": [], "unresolvedQuestions": list(proposal.unresolved_questions),
        "constraintsAdded": [],
        "acceptanceCriteriaAdded": list(proposal.verification_contract.acceptance_criteria),
        "confidence": 1.0 if record.execution_enabled else 0.0,
        "limitations": ["Advisory compilation only; no execution or verification authority."],
        "provenanceDigest": digest(provenance),
        "provider": record.provider_id or None, "model": record.model or None,
        "endpointClass": record.endpoint_class or None,
        "executionEnabled": bool(record.execution_enabled),
        "inputDigest": record.input_digest,
    }


def compile_prompt_proposal(service: Any, compiler: PromptCompiler,
                            intent: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    _require_human(metadata)
    proposal_id = str(intent.get("proposalId") or ("pp-" + _suffix(metadata["idempotencyKey"])))
    stream = PromptProposalAggregate.stream_id(proposal_id)
    if service.store.find_idempotent(metadata["idempotencyKey"]) is not None:
        return {"status": "idempotent", **service.store.require_state(stream)}
    if service.store.aggregate_version(stream) != 0:
        raise AuthorityViolation("PROMPT_PROPOSAL_ALREADY_EXISTS")
    original = str(intent.get("originalPrompt", "")).strip()
    target_root = str(intent.get("targetRoot", "")).strip()
    if not original or not target_root:
        raise AuthorityViolation("PROMPT_PROPOSAL_PROMPT_OR_TARGET_MISSING")
    request = PromptCompileRequest(
        original_prompt=original,
        target_root=target_root,
        requested_engine=str(intent.get("promptIntelligence", "AUTO")),
        mode=str(intent.get("mode", "normal")),
        requested_capabilities=tuple(intent.get("requestedCapabilities") or ()),
        execution_provider=str(intent.get("provider", "")),
        execution_model=str(intent.get("model", "")),
        requested_context_budget=int(intent.get("requestedContextBudget", 32_000)),
        remote_compilation_authorized=bool(intent.get("remoteCompilationAuthorized", False)),
    )
    compiled = compiler.compile(request)
    snapshot = PromptProposalAggregate.create({
        "proposalId": proposal_id,
        "originalPrompt": compiled.original_prompt,
        "proposedPrompt": compiled.proposed_prompt,
        "mode": request.mode,
        "stageChain": [stage.value for stage in compiled.stage_chain],
        "stageRecords": [_stage_record(record, compiled) for record in compiled.stage_records],
        "targetRoot": target_root,
        "provider": request.execution_provider or None,
        "model": request.execution_model or None,
        "requestedContextBudget": request.requested_context_budget,
        "effectiveContextBudget": request.requested_context_budget,
        "capabilityRequests": [{"capability": cap, "resource": target_root,
                                "rationale": "Operator requested; stages cannot widen it."}
                               for cap in request.requested_capabilities],
        "verificationContract": {
            "acceptanceCriteria": list(compiled.verification_contract.acceptance_criteria)
        },
    })
    require("PromptProposalSnapshot", snapshot)
    event = commands.envelope(
        event_id=metadata["commandId"] + "-proposal",
        stream_id=stream,
        event_type="PromptProposalCreated",
        payload={"eventType": "PromptProposalCreated", "proposal": snapshot},
        metadata=metadata,
        occurred_at=metadata["issuedAt"],
    )
    service._commit(
        [AppendRequest(stream, PromptProposalAggregate.KIND, 0, event, snapshot)], metadata
    )
    return {
        "status": compiled.status,
        **snapshot,
        "rationale": compiled.rationale,
        "unresolvedQuestions": list(compiled.unresolved_questions),
    }


def revise_prompt_proposal(service: Any, intent: Dict[str, Any],
                           metadata: Dict[str, Any]) -> Dict[str, Any]:
    _require_human(metadata)
    proposal_id = str(intent.get("proposalId", ""))
    stream = PromptProposalAggregate.stream_id(proposal_id)
    if service.store.find_idempotent(metadata["idempotencyKey"]) is not None:
        return {"status": "idempotent", **service.store.require_state(stream)}
    current = service.store.require_state(stream)
    revision = {
        "proposedPrompt": str(intent.get("proposedPrompt", "")).strip(),
        "stageChain": list(current["stageChain"]),
        "stageRecords": list(current["stageRecords"]),
        "provider": current.get("provider"),
        "model": current.get("model"),
        "requestedContextBudget": current["requestedContextBudget"],
        "effectiveContextBudget": current["effectiveContextBudget"],
        "capabilityRequests": list(current["capabilityRequests"]),
        "verificationContract": dict(current["verificationContract"]),
    }
    state = PromptProposalAggregate.revise(current, revision)
    require("PromptProposalSnapshot", state)
    event = commands.envelope(
        event_id=metadata["commandId"] + "-proposal",
        stream_id=stream,
        event_type="PromptProposalRevised",
        payload={"eventType": "PromptProposalRevised", "revision": revision},
        metadata=metadata,
        occurred_at=metadata["issuedAt"],
    )
    service._commit([
        AppendRequest(stream, PromptProposalAggregate.KIND,
                      service.store.aggregate_version(stream), event, state)
    ], metadata)
    return {"status": "applied", **state}


def cancel_prompt_proposal(service: Any, intent: Dict[str, Any],
                           metadata: Dict[str, Any]) -> Dict[str, Any]:
    _require_human(metadata)
    proposal_id = str(intent.get("proposalId", ""))
    stream = PromptProposalAggregate.stream_id(proposal_id)
    if service.store.find_idempotent(metadata["idempotencyKey"]) is not None:
        return {"status": "idempotent", **service.store.require_state(stream)}
    current = service.store.require_state(stream)
    reason = str(intent.get("reason") or "Operator cancelled prompt proposal.")
    state = PromptProposalAggregate.cancel(current, reason)
    cancellation = {"proposalId": proposal_id, "reason": reason}
    event = commands.envelope(
        event_id=metadata["commandId"] + "-proposal",
        stream_id=stream,
        event_type="PromptProposalCancelled",
        payload={"eventType": "PromptProposalCancelled", "cancellation": cancellation},
        metadata=metadata,
        occurred_at=metadata["issuedAt"],
    )
    service._commit([
        AppendRequest(stream, PromptProposalAggregate.KIND,
                      service.store.aggregate_version(stream), event, state)
    ], metadata)
    return {"status": "applied", **state}


def authoritative_proposal_binding_for_execution(
    store: Any, approval_request_id: str, objective: str
) -> Dict[str, Any] | None:
    """Recover proposal identity only from authoritative HumanApproval state."""
    approval = store.require_state("human_approval-" + str(approval_request_id))
    scope = approval.get("scope") if isinstance(approval, dict) else None
    binding = scope.get("approvalBinding") if isinstance(scope, dict) else None
    if not isinstance(binding, dict) or not binding.get("proposalId"):
        return None
    keys = (
        "proposalId", "proposalRevision", "proposalSnapshotDigest",
        "originalHumanPromptDigest", "selectedPromptKind", "selectedPromptDigest",
    )
    if any(key not in binding for key in keys):
        raise AuthorityViolation("PROMPT_PROPOSAL_APPROVAL_BINDING_INCOMPLETE")
    if str(binding["selectedPromptDigest"]) != digest(str(objective)):
        raise AuthorityViolation("PROMPT_PROPOSAL_SELECTED_PROMPT_MISMATCH_AT_EXECUTION")
    proposal = store.require_state(PromptProposalAggregate.stream_id(str(binding["proposalId"])))
    if proposal.get("state") != "active":
        raise AuthorityViolation("PROMPT_PROPOSAL_NOT_ACTIVE_AT_EXECUTION")
    if int(binding["proposalRevision"]) != int(proposal.get("revision", -1)):
        raise AuthorityViolation("PROMPT_PROPOSAL_REVISION_MISMATCH_AT_EXECUTION")
    if str(binding["originalHumanPromptDigest"]) != str(proposal.get("originalPromptDigest")):
        raise AuthorityViolation("PROMPT_PROPOSAL_ORIGINAL_DIGEST_MISMATCH_AT_EXECUTION")
    if str(binding["proposalSnapshotDigest"]) != digest(proposal):
        raise AuthorityViolation("PROMPT_PROPOSAL_SNAPSHOT_MISMATCH_AT_EXECUTION")
    return {key: binding[key] for key in keys}


def request_prompt_proposal_approval(service: Any, intent: Dict[str, Any],
                                     metadata: Dict[str, Any]) -> Dict[str, Any]:
    _require_human(metadata)
    proposal_id = str(intent.get("proposalId", ""))
    proposal = service.store.require_state(PromptProposalAggregate.stream_id(proposal_id))
    if proposal.get("state") != "active":
        raise AuthorityViolation("PROMPT_PROPOSAL_NOT_ACTIVE")
    offered_revision = int(intent.get("proposalRevision", -1))
    if offered_revision != int(proposal["revision"]):
        raise AuthorityViolation("PROMPT_PROPOSAL_REVISION_MISMATCH")
    selection = str(intent.get("selection", "")).lower()
    if selection == "upgrade":
        selected = str(proposal["proposedPrompt"])
    elif selection == "original":
        selected = str(proposal["originalPrompt"])
    elif selection == "edited":
        selected = str(intent.get("editedPrompt", "")).strip()
        if not selected:
            raise AuthorityViolation("PROMPT_PROPOSAL_EDITED_PROMPT_MISSING")
    else:
        raise AuthorityViolation("PROMPT_PROPOSAL_SELECTION_INVALID")
    selected_digest = digest(selected)
    approval_intent = {
        "objective": selected,
        "targetRoot": proposal["targetRoot"],
        "provider": proposal.get("provider") or "",
        "model": proposal.get("model") or "",
        "responseMode": str(intent.get("responseMode", "SPOCK")),
        "promptEnhancement": "OFF",
        "requestedContextBudget": int(proposal.get("requestedContextBudget", 32_000)),
        "humanVerificationRequired": bool(intent.get("humanVerificationRequired", True)),
        "executable": str(intent.get("executable", "") or ""),
    }
    for key in ("requestId", "missionId", "taskId", "driverRunId"):
        value = intent.get(key)
        if value:
            approval_intent[key] = value
    proposal_binding = {
        "proposalId": proposal_id,
        "proposalRevision": int(proposal["revision"]),
        "proposalSnapshotDigest": digest(proposal),
        "originalHumanPromptDigest": proposal["originalPromptDigest"],
        "selectedPromptKind": selection,
        "selectedPromptDigest": selected_digest,
    }
    approval_intent.update(proposal_binding)
    result = request_model_prompt_approval(service, approval_intent, metadata)
    return {
        **result,
        **proposal_binding,
    }
