import pytest

from capt_runtime.security_gate import (
    CONTROLS, CONTROL_BY_ID, EvidenceStatus, ResultStatus,
    SecurityEvidence, SecurityProfile, evaluate_security_gate,
)

CAPT_CORE_CAPS = frozenset({
    "local_runtime", "ipc", "database", "local_state", "ai",
    "prompt_processing", "cli", "record_store",
})


def _profile():
    return SecurityProfile("capt-core", CAPT_CORE_CAPS)


def _pass_evidence(profile, sha="sha-current"):
    return [
        SecurityEvidence(
            c.control_id, EvidenceStatus.PASS, sha,
            ("test:%s" % c.control_id,), "pytest", "verified"
        )
        for c in CONTROLS if c.applies(profile.capabilities)
    ]


def test_catalog_preserves_all_40_screenshot_controls_and_supplements():
    assert len([c for c in CONTROLS if c.control_id.startswith("VIBE1-")]) == 20
    assert len([c for c in CONTROLS if c.control_id.startswith("VIBE2-")]) == 20
    assert len(CONTROLS) == 46
    assert len(CONTROL_BY_ID) == len(CONTROLS)
    assert CONTROL_BY_ID["VIBE1-01"].title == "Hide API keys"
    assert CONTROL_BY_ID["VIBE2-20"].title == "Restrict database permissions"


def test_capt_core_applicability_is_explicit_not_silent_pass():
    result = evaluate_security_gate(_profile(), [], source_sha="abc")
    assert result.decision == "BLOCKED"
    assert result.counts["not_verified"] == 20
    assert result.counts["not_applicable"] == 26
    assert "VIBE1-04" not in result.blocking_controls
    assert "VIBE2-09" in result.blocking_controls
    assert "VIBE2-11" in result.blocking_controls


def test_stale_pass_evidence_is_downgraded_not_inherited():
    evidence = [
        SecurityEvidence(
            "VIBE1-20", EvidenceStatus.PASS, "old-sha",
            ("pip-audit:old-sha",), "pip-audit", "dependency closure clean"
        )
    ]
    result = evaluate_security_gate(_profile(), evidence, source_sha="new-sha")
    row = next(r for r in result.results if r.control_id == "VIBE1-20")
    assert row.status == ResultStatus.NOT_VERIFIED
    assert "stale" in row.reason
    assert result.decision == "BLOCKED"


def test_exact_sha_complete_evidence_is_required_for_release_pass():
    profile = _profile()
    result = evaluate_security_gate(
        profile, _pass_evidence(profile), source_sha="sha-current"
    )
    assert result.decision == "PASS"
    assert result.blocking_controls == ()
    assert result.counts["pass"] == 20
    assert result.counts["not_applicable"] == 26


def test_failed_applicable_control_blocks_release_even_with_other_passes():
    profile = _profile()
    evidence = _pass_evidence(profile)
    evidence = [
        SecurityEvidence(
            item.control_id,
            EvidenceStatus.FAIL if item.control_id == "VIBE2-09" else item.status,
            item.source_sha,
            item.refs,
            item.verifier,
            "prompt-injection regression reproduced" if item.control_id == "VIBE2-09" else item.detail,
        )
        for item in evidence
    ]
    result = evaluate_security_gate(profile, evidence, source_sha="sha-current")
    row = next(r for r in result.results if r.control_id == "VIBE2-09")
    assert row.status == ResultStatus.FAIL
    assert result.decision == "BLOCKED"


def test_pass_or_fail_evidence_requires_sha_ref_and_verifier():
    with pytest.raises(ValueError, match="SECURITY_EVIDENCE_SHA_REQUIRED"):
        SecurityEvidence.from_mapping({
            "controlId": "VIBE1-01", "status": "pass",
            "refs": ["gitleaks"], "verifier": "gitleaks",
        })
    with pytest.raises(ValueError, match="SECURITY_EVIDENCE_REF_REQUIRED"):
        SecurityEvidence.from_mapping({
            "controlId": "VIBE1-01", "status": "pass",
            "sourceSha": "abc", "refs": [], "verifier": "gitleaks",
        })


def test_duplicate_or_unknown_evidence_fails_closed():
    item = SecurityEvidence(
        "VIBE1-20", EvidenceStatus.PASS, "abc",
        ("pip-audit",), "pip-audit",
    )
    with pytest.raises(ValueError, match="SECURITY_EVIDENCE_DUPLICATE"):
        evaluate_security_gate(_profile(), [item, item], source_sha="abc")
    unknown = SecurityEvidence(
        "NOPE", EvidenceStatus.NOT_VERIFIED, "", (), "",
    )
    with pytest.raises(ValueError, match="SECURITY_EVIDENCE_UNKNOWN_CONTROL"):
        evaluate_security_gate(_profile(), [unknown], source_sha="abc")
