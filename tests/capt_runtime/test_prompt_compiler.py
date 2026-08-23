from __future__ import annotations

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.prompt_compiler import (
    BoundedPromptCompilerRunner,
    CompilerProvider,
    PromptCompileRequest,
    PromptCompiler,
    PromptStageName,
    StructuredStageResult,
    route_stages,
)


def _request(**overrides):
    values = {
        "original_prompt": "Write a concise incident report for the failed provider run.",
        "target_root": "/workspace/project",
        "requested_engine": "AUTO",
        "mode": "normal",
        "requested_capabilities": ("cap.fs.read",),
    }
    values.update(overrides)
    return PromptCompileRequest(**values)


def test_auto_routes_substantive_work_through_omni_then_meta():
    route = route_stages(_request())

    assert isinstance(route, tuple)
    assert route.stage_chain == (PromptStageName.OMNI, PromptStageName.META)
    assert "substantive" in route.rationale.lower()


def test_underspecified_request_requires_clarification_without_inventing_intent():
    proposal = PromptCompiler().compile(_request(original_prompt="help"))

    assert proposal.status == "clarification_required"
    assert proposal.proposed_prompt == "help"
    assert proposal.unresolved_questions
    assert proposal.requested_capabilities == ()


def test_software_routing_includes_specialists_but_execution_is_disabled():
    proposal = PromptCompiler().compile(_request(
        original_prompt="Implement a tested fix for the provider run failure.",
        mode="software-development",
    ))

    assert proposal.stage_chain == (
        PromptStageName.OMNI,
        PromptStageName.META,
        PromptStageName.FORGE,
        PromptStageName.SIGMA,
    )
    assert all(
        record.execution_enabled is False
        for record in proposal.stage_records
        if record.stage in (PromptStageName.FORGE, PromptStageName.SIGMA)
    )


def test_off_is_a_no_rewrite_proposal():
    proposal = PromptCompiler().compile(_request(requested_engine="OFF"))

    assert proposal.proposed_prompt == proposal.original_prompt
    assert proposal.proposed_prompt_digest == proposal.original_prompt_digest
    assert proposal.stage_chain == ()


def test_no_permitted_model_fallback_is_a_no_op_and_never_remote_dispatches():
    proposal = PromptCompiler().compile(_request())

    assert proposal.status == "compiler_unavailable"
    assert proposal.proposed_prompt == proposal.original_prompt
    assert proposal.proposed_prompt_digest == proposal.original_prompt_digest


def test_structured_stage_contract_is_closed_and_rejects_invalid_stage_names():
    with pytest.raises(ValueError, match="unknown keys"):
        StructuredStageResult.from_model_output({
            "stage": "OMNI",
            "outcome": "report",
            "scope": "provider failure",
            "inputs": [],
            "outputs": ["report"],
            "constraints": [],
            "successCriteria": ["clear"],
            "ambiguities": [],
            "surprise": True,
        })
    with pytest.raises(ValueError, match="unknown prompt stage"):
        StructuredStageResult.from_model_output({
            "stage": "NOT_A_STAGE",
            "outcome": "report",
            "scope": "provider failure",
            "inputs": [],
            "outputs": ["report"],
            "constraints": [],
            "successCriteria": ["clear"],
            "ambiguities": [],
        })


def test_stage_cannot_add_capabilities_outside_intent_and_mode_policy():
    compiler = PromptCompiler()
    request = _request(requested_capabilities=("cap.fs.read",))
    result = StructuredStageResult.from_model_output({
        "stage": "OMNI",
        "outcome": "report",
        "scope": "provider failure",
        "inputs": [],
        "outputs": ["report"],
        "constraints": [],
        "successCriteria": ["clear"],
        "ambiguities": [],
        "requestedCapabilities": ["cap.fs.write"],
    })

    with pytest.raises(AuthorityViolation, match="capability escalation"):
        compiler.admit_stage_result(request, result)


def test_local_runner_receives_analysis_only_closed_context_and_records_provider():
    seen = []

    def transport(payload):
        seen.append(payload)
        return {
            "stage": payload["stage"], "outcome": "incident report",
            "scope": "provider run", "inputs": ["prompt"],
            "outputs": ["report"], "constraints": ["preserve objective"],
            "successCriteria": ["evidence included"], "ambiguities": [],
            "requestedCapabilities": [],
        }

    proposal = PromptCompiler(
        runner=BoundedPromptCompilerRunner(transport),
        provider=CompilerProvider("ollama", "local-model", "local"),
    ).compile(_request())

    assert proposal.status == "ready_for_approval"
    assert proposal.proposed_prompt != proposal.original_prompt
    assert [payload["stage"] for payload in seen] == ["OMNI", "META"]
    assert all(payload["analysisOnly"] is True for payload in seen)
    assert all(payload["allowedCapabilities"] == ["cap.fs.read"] for payload in seen)
    assert all(record.provider_id == "ollama" for record in proposal.stage_records)
