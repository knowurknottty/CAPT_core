import pytest

from capt_runtime.security_evidence import build_bundle


def test_ephemeral_bundle_binds_every_attestation_to_execution_sha():
    bundle = build_bundle(
        source_sha="abc123",
        passed=["VIBE1-01=gitleaks:history", "VIBE1-20=pip-audit:closure"],
        failed=["VIBE2-11=pytest:test_oversize_frame_rejected"],
        verifier="release-security-ci",
    )
    assert bundle["ephemeral"] is True
    assert bundle["sourceSha"] == "abc123"
    assert [row["controlId"] for row in bundle["evidence"]] == [
        "VIBE1-01", "VIBE1-20", "VIBE2-11"
    ]
    assert {row["sourceSha"] for row in bundle["evidence"]} == {"abc123"}
    assert {row["verifier"] for row in bundle["evidence"]} == {"release-security-ci"}


def test_duplicate_pass_fail_attestation_fails_closed():
    with pytest.raises(ValueError, match="SECURITY_ATTESTATION_DUPLICATE"):
        build_bundle(
            source_sha="abc",
            passed=["VIBE1-20=pip-audit"],
            failed=["VIBE1-20=pip-audit-failed"],
        )


def test_unknown_or_malformed_attestation_is_rejected():
    with pytest.raises(ValueError, match="SECURITY_ATTESTATION_UNKNOWN_CONTROL"):
        build_bundle(source_sha="abc", passed=["NOPE=x"])
    with pytest.raises(ValueError, match="SECURITY_ATTESTATION_FORMAT"):
        build_bundle(source_sha="abc", passed=["VIBE1-20"])


def test_empty_source_sha_cannot_produce_evidence():
    with pytest.raises(ValueError, match="SECURITY_SOURCE_SHA_REQUIRED"):
        build_bundle(source_sha="", passed=["VIBE1-20=pip-audit"])
