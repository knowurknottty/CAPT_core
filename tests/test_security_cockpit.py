"""CAPT-UPG-019 tests for truthful Security Closure Cockpit semantics."""

from capt_ui.operator.security_cockpit import project_security_cockpit, render_security_summary


def _result():
    return {
        "profile": "desktop-release",
        "sourceSha": "abc123",
        "decision": "BLOCKED",
        "blockingControls": ["C-FAIL", "C-UNKNOWN"],
        "results": [
            {
                "control_id": "C-PASS",
                "title": "Passed control",
                "status": "pass",
                "severity": "high",
                "release_blocking": True,
                "reason": "verified at exact source SHA",
                "evidence_refs": ["ev-pass"],
            },
            {
                "control_id": "C-FAIL",
                "title": "Failed control",
                "status": "fail",
                "severity": "critical",
                "release_blocking": True,
                "reason": "negative test failed",
                "evidence_refs": ["ev-fail"],
            },
            {
                "control_id": "C-UNKNOWN",
                "title": "Missing evidence",
                "status": "not_verified",
                "severity": "high",
                "release_blocking": True,
                "reason": "applicable control has no current verification evidence",
                "evidence_refs": [],
            },
            {
                "control_id": "C-STALE",
                "title": "Stale evidence",
                "status": "not_verified",
                "severity": "medium",
                "release_blocking": False,
                "reason": "evidence is stale: old != abc123",
                "evidence_refs": ["ev-old"],
            },
            {
                "control_id": "C-NA",
                "title": "Not applicable",
                "status": "not_applicable",
                "severity": "low",
                "release_blocking": True,
                "reason": "profile capabilities do not expose this control surface",
                "evidence_refs": [],
            },
        ],
    }


def test_projection_preserves_pass_fail_unknown_stale_and_na_distinctions():
    cockpit = project_security_cockpit(_result())
    by_id = {row["controlId"]: row for row in cockpit["controls"]}

    assert by_id["C-PASS"]["isPass"] is True
    assert by_id["C-FAIL"]["isPass"] is False
    assert by_id["C-UNKNOWN"]["isPass"] is False
    assert by_id["C-UNKNOWN"]["evidenceMissing"] is True
    assert by_id["C-STALE"]["evidenceStale"] is True
    assert by_id["C-NA"]["isNotApplicable"] is True
    assert by_id["C-NA"]["isPass"] is False
    assert cockpit["globalSecurityVerdict"] is None
    assert cockpit["releaseAuthorized"] is False


def test_projection_recomputes_counts_and_preserves_blockers():
    cockpit = project_security_cockpit(_result())
    assert cockpit["counts"] == {
        "pass": 1,
        "fail": 1,
        "not_verified": 2,
        "not_applicable": 1,
    }
    assert cockpit["blockingControls"] == ["C-FAIL", "C-UNKNOWN"]
    assert cockpit["gateDecision"] == "BLOCKED"


def test_inconsistent_pass_decision_with_blockers_is_forced_back_to_blocked():
    raw = _result()
    raw["decision"] = "PASS"
    cockpit = project_security_cockpit(raw)
    assert cockpit["gateDecision"] == "BLOCKED"
    assert cockpit["globalSecurityVerdict"] is None


def test_summary_never_emits_universal_security_claim():
    text = render_security_summary(project_security_cockpit(_result()))
    assert "No universal 'CAPT is secure' verdict" in text
    assert "C-FAIL" in text
    assert "C-UNKNOWN" in text


def test_missing_or_noncanonical_source_sha_cannot_render_as_verified_pass():
    raw = _result()
    raw["sourceSha"] = ""
    cockpit = project_security_cockpit(raw)
    by_id = {row["controlId"]: row for row in cockpit["controls"]}
    assert by_id["C-PASS"]["status"] == "not_verified"
    assert by_id["C-PASS"]["isPass"] is False
    assert cockpit["gateDecision"] == "BLOCKED"
    assert "source SHA" in by_id["C-PASS"]["reason"]


def test_pass_without_evidence_reference_cannot_render_as_verified_pass():
    raw = _result()
    raw["results"][0]["evidence_refs"] = []
    cockpit = project_security_cockpit(raw)
    row = next(r for r in cockpit["controls"] if r["controlId"] == "C-PASS")
    assert row["status"] == "not_verified"
    assert row["evidenceMissing"] is True
    assert row["isPass"] is False
    assert cockpit["gateDecision"] == "BLOCKED"
