"""Driver-boundary tests for governed authored skill context."""

from __future__ import annotations

import pytest

from capt_runtime.context_slice import build_context_slice
from capt_runtime.drivers.hermes import build_prompt


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
