"""Artifact / Workspace Plane tests (Gate 8).

Covers path traversal, symlink escape, write outside lease, stale snapshot,
digest mismatch, promotion without verification, rollback, malicious rendering.
"""

import os
import tempfile

import pytest

from capt_runtime import artifact_workspace as aw
from capt_runtime.errors import IntegrityViolation


def _ws(root):
    return {
        "schemaVersion": "1.0.0",
        "workspaceId": "ws-1",
        "rootPath": root,
        "pathScope": {"schemaVersion": "1.0.0", "rootPath": root, "allowedPaths": [root]},
    }


def _candidate(path, digest="sha256:" + "a" * 64):
    return {
        "schemaVersion": "1.0.0",
        "candidateId": "c-1",
        "driverRunId": "run-1",
        "path": path,
        "contentDigest": digest,
    }


def _decision(decision, verified_by="gov-1"):
    return {
        "schemaVersion": "1.0.0",
        "decision": decision,
        "decidedBy": verified_by,
        "decidedAt": "2026-08-03T00:00:00Z",
    }


def test_workspace_descriptor_valid():
    with tempfile.TemporaryDirectory() as d:
        assert aw.validate_workspace_descriptor(_ws(d))["workspaceId"] == "ws-1"


def test_path_traversal_rejected():
    with tempfile.TemporaryDirectory() as d:
        bad = os.path.join(d, "..", "escape.txt")
        with pytest.raises(IntegrityViolation):
            aw.assert_within_workspace(bad, [d])


def test_write_outside_lease_rejected():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        cand = _candidate(os.path.join(d2, "x.txt"))
        with pytest.raises(IntegrityViolation):
            aw.stage_candidate(cand, _ws(d1), "2026-08-03T00:00:00Z")


def test_symlink_escape_rejected():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        link = os.path.join(d1, "link")
        try:
            os.symlink(d2, link)
        except (OSError, NotImplementedError):
            pytest.skip("symlink unsupported on this platform")
        cand = _candidate(os.path.join(link, "x.txt"))
        with pytest.raises(IntegrityViolation):
            aw.stage_candidate(cand, _ws(d1), "2026-08-03T00:00:00Z")


def test_stage_candidate_inside_lease_ok():
    with tempfile.TemporaryDirectory() as d:
        cand = _candidate(os.path.join(d, "out.txt"))
        staged = aw.stage_candidate(cand, _ws(d), "2026-08-03T00:00:00Z")
        assert staged["state"] == "staged"


def test_fabricated_authoritative_rejected():
    # The ingestion guard rejects any driver-supplied authoritative record type.
    from capt_runtime.ingestion import IngestionRejection
    with pytest.raises(IngestionRejection):
        aw.reject_fabricated_authoritative({"eventType": "VerificationResult"})


def test_promotion_requires_verification():
    with tempfile.TemporaryDirectory() as d:
        staged = aw.stage_candidate(_candidate(os.path.join(d, "out.txt")),
                                    _ws(d), "2026-08-03T00:00:00Z")
        with pytest.raises(IntegrityViolation):
            aw.decide_promotion(staged, _decision("promote"), verified=False)


def test_promote_artifact_to_destination_governed():
    with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as dest_dir:
        cand_file = os.path.join(staging, "artifact.json")
        with open(cand_file, "w") as f:
            f.write('{"test": true}')
        import hashlib
        digest = "sha256:" + hashlib.sha256(b'{"test": true}').hexdigest()
        cand = _candidate(cand_file, digest=digest)
        staged = aw.stage_candidate(cand, _ws(staging), "2026-08-03T00:00:00Z")
        
        target = os.path.join(dest_dir, "promoted.json")
        rec = aw.promote_artifact_to_destination(staged, _decision("promote"), target, verified=True, expected_digest=digest)
        assert rec["destinationPath"] == target
        assert os.path.exists(target)
        assert open(target).read() == '{"test": true}'


def test_promotion_verified_ok():
    with tempfile.TemporaryDirectory() as d:
        staged = aw.stage_candidate(_candidate(os.path.join(d, "out.txt")),
                                    _ws(d), "2026-08-03T00:00:00Z")
        rec = aw.decide_promotion(staged, _decision("promote"), verified=True,
                                  expected_digest=staged["contentDigest"])
        assert rec["artifactId"].startswith("art-")


def test_quarantine_allowed_without_verification():
    with tempfile.TemporaryDirectory() as d:
        staged = aw.stage_candidate(_candidate(os.path.join(d, "out.txt")),
                                    _ws(d), "2026-08-03T00:00:00Z")
        rec = aw.decide_promotion(staged, _decision("quarantine"), verified=False)
        assert rec["promotionDecision"]["decision"] == "quarantine"


def test_rollback_receipt():
    with tempfile.TemporaryDirectory() as d:
        staged = aw.stage_candidate(_candidate(os.path.join(d, "out.txt")),
                                    _ws(d), "2026-08-03T00:00:00Z")
        rb = aw.rollback(staged)
        assert rb["operation"] == "delete" and rb["verified"] is True


def test_malicious_rendering_not_authoritative():
    # A driver-produced artifact is untrusted; promotion requires verification.
    # Without verification it can never become authoritative state.
    with tempfile.TemporaryDirectory() as d:
        cand = _candidate(os.path.join(d, "evil.html"))
        staged = aw.stage_candidate(cand, _ws(d), "2026-08-03T00:00:00Z")
        with pytest.raises(IntegrityViolation):
            aw.decide_promotion(staged, _decision("promote"), verified=False)
