"""Regression tests for approval-frozen managed skills at execution admission."""

from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.authored_skills import (
    AuthoredSkillRequestViolation,
    prepare_approved_runtime_skill_context,
    prepare_runtime_skill_context,
    summarize_skill_context,
)
from capt_runtime.managed_skills import import_managed_skill_pack
from capt_runtime.model_approval_binding import (
    build_bound_model_operator_approval,
    staging_root_for_ledger,
)
from capt_runtime.prompt_approval import request_model_prompt_approval
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def _managed_pack(tmp_path):
    source = tmp_path / "source"
    for name, hint in (
        ("inversion-execute-now", "Use when the user says proceed, continue, apply it, approved, or ship it."),
        ("inversion-release-closure", "Use when work is ready, mergeable, shippable, or release-candidate."),
    ):
        target = source / "skills" / name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"---\nname: {name}\ndescription: {hint}\n"
            "version: 1.0.0\n---\n\n# Scope\nApproved evidence only.\n"
        )
    import_managed_skill_pack(source, tmp_path / "skills" / "ultimate")
    return source


def _approved(tmp_path, *, auto=None):
    _managed_pack(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    store = EventStore(str(tmp_path / "ledger.db"))
    label = f"approved-managed-{auto}"
    metadata = commands.command(
        command_id="cmd-" + label,
        idempotency_key="idem-" + label,
        operation_fingerprint=commands.fingerprint("approval", {"label": label}),
        correlation_id="corr-" + label,
        actor_id="human-operator",
        actor_kind="human",
        issued_at="2026-10-17T08:49:00Z",
        replay_policy="never",
    )
    intent = {
        "objective": "Proceed and ship this release candidate once mergeable",
        "targetRoot": str(project), "provider": "ollama",
        "model": "qwen3.5-defiant-fable:latest",
    }
    if auto is not None:
        intent["autoSelectSkills"] = auto
    receipt = request_model_prompt_approval(RuntimeService(store), intent, metadata)
    approval = store.require_state("human_approval-" + receipt["requestId"])
    return store, intent, receipt, approval


def _rebound(store, intent, receipt, binding, context):
    return build_bound_model_operator_approval(
        human_prompt=intent["objective"],
        response_mode="SPOCK",
        enhancement_engine="OFF",
        mission_id=receipt["missionId"],
        task_id=receipt["taskId"],
        driver_run_id=receipt["driverRunId"],
        target_root=intent["targetRoot"],
        provider=intent["provider"],
        model=intent["model"],
        requested_context_budget=32000,
        requested_execution_seconds=600,
        human_verification_required=True,
        executable="",
        staging_root=staging_root_for_ledger(store.path, receipt["driverRunId"]),
        context_pack_digest=binding["contextPackDigest"],
        continuation_context=binding["continuationContext"],
        authored_skill_context=context,
        authority_profile=binding["authorityProfile"],
    )


def test_proposal_auto_skill_selection_replays_exact_approved_digest(tmp_path):
    store, intent, receipt, approval = _approved(tmp_path)
    try:
        binding = approval["scope"]["approvalBinding"]
        assert binding["authoredSkills"]["skills"]
        execution = {**intent, "autoSelectSkills": False}

        # The former execution path dropped approved skills and changed the
        # prompt digest; no model execution was authorized by that difference.
        old_context, _ = prepare_runtime_skill_context(
            execution, state_root=tmp_path
        )
        assert old_context is None
        assert _rebound(store, intent, receipt, binding, old_context)[
            "promptAssemblyDigest"
        ] != approval["promptAssemblyDigest"]

        context, names = prepare_approved_runtime_skill_context(
            execution, state_root=tmp_path, approval_binding=binding
        )
        assert names == [skill["name"] for skill in binding["authoredSkills"]["skills"]]
        assert summarize_skill_context(context) == binding["authoredSkills"]
        assert _rebound(store, intent, receipt, binding, context)[
            "promptAssemblyDigest"
        ] == approval["promptAssemblyDigest"]
    finally:
        store.close()


def test_execution_cannot_substitute_different_managed_skills(tmp_path):
    store, intent, _, approval = _approved(tmp_path)
    try:
        binding = approval["scope"]["approvalBinding"]
        approved = {item["name"] for item in binding["authoredSkills"]["skills"]}
        other = list({"inversion-execute-now", "inversion-release-closure"} - approved)
        # If both are selected, an empty explicit list is also a divergence.
        names = other if other else []
        with pytest.raises(AuthoredSkillRequestViolation, match="APPROVED_SKILL_CONTEXT_MISMATCH"):
            prepare_approved_runtime_skill_context(
                {**intent, "managedSkillNames": names},
                state_root=tmp_path, approval_binding=binding
            )
    finally:
        store.close()


def test_execution_without_approved_skills_does_not_auto_select_new_pack(tmp_path):
    store, intent, _, approval = _approved(tmp_path, auto=False)
    try:
        binding = approval["scope"]["approvalBinding"]
        assert "authoredSkills" not in binding
        context, names = prepare_approved_runtime_skill_context(
            {k: v for k, v in intent.items() if k != "autoSelectSkills"},
            state_root=tmp_path, approval_binding=binding
        )
        assert context is None
        assert names == []
    finally:
        store.close()


def test_execution_rejects_malformed_approved_managed_selection(tmp_path):
    _managed_pack(tmp_path)
    with pytest.raises(AuthoredSkillRequestViolation, match="APPROVED_SKILL_SELECTION_INVALID"):
        prepare_approved_runtime_skill_context(
            {"objective": "Run", "autoSelectSkills": False},
            state_root=tmp_path,
            approval_binding={"authoredSkills": {"trust": "managed_local", "skills": [{"notName": "bad"}]}},
        )
