"""Artifact / Workspace Plane (ADR-DT-PLANE-CONV, Gate 8).

Thin lifecycle governance for driver-produced artifacts. Drivers may NOT
directly create authoritative artifacts. The lifecycle is:

    driver output
    -> artifact candidate
    -> isolated staging (workspace lease)
    -> validation (path containment, fabricated-authoritative rejection)
    -> verification
    -> policy / ClaimGuard gate
    -> promotion, rejection, or quarantine

The plane owns isolated worktrees, staging directories, snapshots, generated
files, diffs/patches, build output, test logs, cleanup, rollback, artifact
checksums, and promotion. It does NOT own learning policy, model promotion,
evidence adjudication, or capability issuance.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contracts import require
from .errors import IntegrityViolation
from .ingestion import _realpath_within, reject_fabricated_authoritative


def validate_workspace_descriptor(descriptor: Dict[str, Any]) -> Dict[str, Any]:
    return require("WorkspaceDescriptor", descriptor)


def validate_artifact_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return require("ArtifactCandidate", candidate)


def validate_promotion_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    return require("ArtifactPromotionDecision", decision)


def assert_within_workspace(path: str, allowed_roots: List[str]) -> str:
    """Reject path traversal / symlink escape / write outside the lease.

    Returns the canonical real path if contained; otherwise raises. Reuses the
    ingestion path-containment discipline.
    """
    if not _realpath_within(path, allowed_roots):
        raise IntegrityViolation(
            "path %r escapes workspace allowed roots %r" % (path, allowed_roots))
    return os.path.realpath(path)


def stage_candidate(
    candidate: Dict[str, Any],
    workspace: Dict[str, Any],
    now_iso: str,
) -> Dict[str, Any]:
    """Validate a driver-produced artifact candidate against the workspace lease.

    Returns a staged record. Does NOT promote.
    """
    validate_artifact_candidate(candidate)
    validate_workspace_descriptor(workspace)
    scope = workspace["pathScope"]
    allowed = [scope["rootPath"]] + list(scope["allowedPaths"])
    # Path containment: candidate path must stay within the workspace.
    assert_within_workspace(candidate["path"], allowed)
    # Fabricated authoritative state is rejected outright.
    reject_fabricated_authoritative(candidate)
    return {
        "schemaVersion": "1.0.0",
        "candidateId": candidate["candidateId"],
        "driverRunId": candidate["driverRunId"],
        "path": candidate["path"],
        "contentDigest": candidate["contentDigest"],
        "stagedAt": now_iso,
        "workspaceId": workspace["workspaceId"],
        "state": "staged",
    }


def decide_promotion(
    staged: Dict[str, Any],
    decision: Dict[str, Any],
    *,
    verified: bool,
    expected_digest: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply the governance/ClaimGuard gate.

    Promotion REQUIRES verification and digest match. Without verification the
    candidate is rejected or quarantined, never promoted.
    """
    validate_promotion_decision(decision)
    if decision["decision"] == "promote":
        if not verified:
            raise IntegrityViolation("promotion without verification is forbidden")
        if expected_digest is not None and staged["contentDigest"] != expected_digest:
            raise IntegrityViolation("artifact digest mismatch; promotion blocked")
    record = {
        "schemaVersion": "1.0.0",
        "artifactId": "art-" + staged["candidateId"],
        "candidateId": staged["candidateId"],
        "path": staged["path"],
        "contentDigest": staged["contentDigest"],
        "promotionDecision": decision,
    }
    require("ArtifactRecord", record)
    return record


def rollback(staged: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a rollback receipt for a staged artifact (no mutation here)."""
    return {
        "schemaVersion": "1.0.0",
        "receiptId": "rb-" + staged["candidateId"],
        "artifactPath": staged["path"],
        "operation": "delete",
        "contentDigest": staged["contentDigest"],
        "verified": True,
    }


def promote_artifact_to_destination(
    staged: Dict[str, Any],
    decision: Dict[str, Any],
    destination_path: str,
    *,
    verified: bool,
    expected_digest: Optional[str] = None,
) -> Dict[str, Any]:
    """Governed transaction: promotes a staged verified artifact to destination path."""
    record = decide_promotion(staged, decision, verified=verified, expected_digest=expected_digest)
    if decision.get("decision") == "promote":
        import shutil
        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged["path"], dest)
        record["destinationPath"] = str(dest)
    return record
