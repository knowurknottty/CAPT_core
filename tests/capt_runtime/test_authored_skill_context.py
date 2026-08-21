"""Driver-boundary tests for governed authored skill context."""

from __future__ import annotations

from copy import deepcopy

import pytest

from capt_runtime.context_slice import build_context_slice
from capt_runtime.drivers.hermes import build_prompt
from capt_runtime.model_approval_binding import raw_text_digest


def _skill_context():
    return {
        "packName": "CAPT_Skills",
        "packVersion": "0.1.0",
        "sourceRepository": "https://github.com/knowurknottty/CAPT_Skills.git",
        "sourceRef": "v0.1.0",
        "sourceCommit": "0" * 40,
        "sourceTree": "1" * 40,
        "manifestDigest": "sha256:" + "2" * 64,
        "trust": "pinned_external",
        "skills": [{
            "name": "inversion-interface-craft",
            "version": "0.1.0",
            "contentDigest": "sha256:" + "3" * 64,
            "content": "Primary owner: impeccable. UNKNOWN stays UNKNOWN.",
        }],
    }


def _context(skill_context=None):
    return build_context_slice(
        lease={
            "leaseId": "l-1", "operations": ["RepositoryRead"],
            "scope": {"kind": "filesystem", "rootPath": "/tmp", "recursive": True},
            "validFrom": "2026-01-01T00:00:00Z", "validUntil": "2030-01-01T00:00:00Z",
        },
        filesystem_policy={
            "rootPath": "/tmp", "allowedPaths": ["/tmp"], "writesAllowed": False,
        },
        permitted_tools=[],
        budgets={"maxSeconds": 60},
        expected_artifacts=[],
        termination_conditions={"onUnexpectedWrite": "fail"},
        network_policy={"egressAllowed": False, "allowedHosts": []},
        skill_context=skill_context,
    )


def test_context_slice_carries_only_explicit_skill_context():
    without = _context()
    assert "skillContext" not in without
    with_skill = _context(_skill_context())
    assert with_skill["skillContext"]["skills"][0]["name"] == "inversion-interface-craft"


def test_hermes_prompt_includes_governed_skill_context_and_provenance():
    prompt = build_prompt(_context(_skill_context()), ["RepositoryRead"], objective="Review UI")
    assert "Authorized authored skill context" in prompt
    assert "context-only" in prompt
    assert "CAPT_Skills" in prompt
    assert "inversion-interface-craft" in prompt
    assert "sha256:" + "3" * 64 in prompt
    assert "UNKNOWN stays UNKNOWN" in prompt


def test_hermes_prompt_never_reads_disk_skills_implicitly(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    leaked = fake_home / ".hermes/skills/leak/SKILL.md"
    leaked.parent.mkdir(parents=True)
    leaked.write_text("SHOULD_NOT_LEAK_FROM_DISK")
    monkeypatch.setenv("HOME", str(fake_home))
    prompt = build_prompt(_context(), ["RepositoryRead"], objective="Review UI")
    assert "SHOULD_NOT_LEAK_FROM_DISK" not in prompt
    assert "Authorized authored skill context" not in prompt


def test_context_slice_rejects_malformed_skill_digest():
    bad = _skill_context()
    bad["skills"][0]["contentDigest"] = "not-a-digest"
    with pytest.raises(Exception):
        _context(bad)


def _bound(skill_context, *, provider: str):
    from capt_runtime.model_approval_binding import build_bound_model_operator_approval

    return build_bound_model_operator_approval(
        human_prompt="Review UI", response_mode="SPOCK", enhancement_engine="OFF",
        mission_id="m-skill", task_id="t-skill", driver_run_id="dr-skill",
        target_root="/tmp/project", provider=provider,
        model="qwen" if provider else "", requested_context_budget=32_000,
        human_verification_required=True, executable="",
        staging_root="/tmp/staging", authored_skill_context=skill_context,
    )


def test_exact_approval_dispatch_includes_authored_skill_bytes_for_all_drivers():
    context = _skill_context()
    for provider in ("", "local-openai"):
        bound = _bound(context, provider=provider)
        assert "Authorized authored skill context" in bound["dispatchPrompt"]
        assert "UNKNOWN stays UNKNOWN" in bound["dispatchPrompt"]
        summary = bound["executionBinding"]["authoredSkills"]
        assert summary["manifestDigest"] == context["manifestDigest"]
        assert "content" not in summary["skills"][0]


def test_authored_skill_bytes_change_approval_and_dispatch_identity():
    original = _skill_context()
    changed = deepcopy(original)
    changed["skills"][0]["content"] += "\nAdditional governed guidance."
    changed["skills"][0]["contentDigest"] = raw_text_digest(
        changed["skills"][0]["content"]
    )

    first = _bound(original, provider="local-openai")
    second = _bound(changed, provider="local-openai")
    assert first["promptAssemblyDigest"] != second["promptAssemblyDigest"]
    assert first["dispatchPromptDigest"] != second["dispatchPromptDigest"]
    assert first["executionBinding"]["authoredSkills"] != second["executionBinding"]["authoredSkills"]
