"""Artifact / Workspace Plane (ADR-DT-PLANE-CONV, Gate 8).

Thin lifecycle mechanics for driver-produced artifacts. Drivers may NOT
directly create authoritative artifacts. The governed lifecycle is:

    driver output
    -> artifact candidate
    -> isolated staging (workspace lease)
    -> validation (path containment, fabricated-authoritative rejection)
    -> verification
    -> separate RuntimeService promotion authorization
    -> atomic adoption or discard

This module owns filesystem mechanics and validation. It does NOT own
verification, ClaimGuard, capability issuance, promotion authorization, or
canonical CAPT state transitions.
"""

from __future__ import annotations

import hashlib
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
    """Reject path traversal / symlink escape / write outside the lease."""
    if not _realpath_within(path, allowed_roots):
        raise IntegrityViolation(
            "path %r escapes workspace allowed roots %r" % (path, allowed_roots)
        )
    return os.path.realpath(path)


def stage_candidate(
    candidate: Dict[str, Any],
    workspace: Dict[str, Any],
    now_iso: str,
) -> Dict[str, Any]:
    """Validate a driver-produced artifact candidate against the workspace lease.

    Returns a staged record. Does NOT authorize or promote.
    """
    validate_artifact_candidate(candidate)
    validate_workspace_descriptor(workspace)
    scope = workspace["pathScope"]
    allowed = [scope["rootPath"]] + list(scope["allowedPaths"])
    assert_within_workspace(candidate["path"], allowed)
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
    """Legacy non-authoritative decision helper.

    This function validates a proposed ArtifactRecord shape only. It must not be
    treated as RuntimeService promotion authorization. CAPT-UPG-009 authoritative
    promotion is owned by the composed RuntimeService transaction stream.
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


def file_digest(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def atomic_adopt_verified_artifact(
    source_path: str,
    destination_path: str,
    expected_digest: str,
) -> Dict[str, Any]:
    """Mechanically adopt exact bytes with atomic destination replacement.

    This function performs no authorization. The composed RuntimeService must
    bind source/destination/digest and authorize the transaction first.

    Recovery rule: if the destination already exists with the exact authorized
    digest, return a reconciliation receipt without requiring the staged source.
    This safely handles process death after ``os.replace`` but before the
    EventStore adoption event is committed.
    """
    destination = Path(destination_path).expanduser().resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and destination.is_file():
        existing_digest = file_digest(str(destination))
        if existing_digest == expected_digest:
            return {
                "destinationPath": str(destination),
                "contentDigest": expected_digest,
                "operation": "already_present_reconciled",
                "atomicReplace": True,
            }

    source = Path(source_path).expanduser().resolve(strict=False)
    if not source.exists() or not source.is_file():
        raise IntegrityViolation("authorized promotion source is unavailable")
    if file_digest(str(source)) != expected_digest:
        raise IntegrityViolation("authorized promotion source digest changed")

    temp = destination.parent / (".%s.capt-promote-%d" % (destination.name, os.getpid()))
    try:
        with open(str(source), "rb") as src, open(str(temp), "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        if file_digest(str(temp)) != expected_digest:
            raise IntegrityViolation("promotion temporary copy digest mismatch")
        os.replace(str(temp), str(destination))
        # Best-effort directory durability on platforms that permit directory fd fsync.
        try:
            fd = os.open(str(destination.parent), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass

    if file_digest(str(destination)) != expected_digest:
        raise IntegrityViolation("adopted destination digest mismatch")
    return {
        "destinationPath": str(destination),
        "contentDigest": expected_digest,
        "operation": "atomic_replace",
        "atomicReplace": True,
    }


def promote_artifact_to_destination(
    staged: Dict[str, Any],
    decision: Dict[str, Any],
    destination_path: str,
    *,
    verified: bool,
    expected_digest: Optional[str] = None,
) -> Dict[str, Any]:
    """Deprecated helper retained for compatibility; NOT authoritative adoption.

    New governed callers must use the composed RuntimeService artifact-promotion
    lifecycle. This helper intentionally refuses consequential promotion so a
    legacy direct caller cannot bypass the authoritative transaction.
    """
    record = decide_promotion(staged, decision, verified=verified, expected_digest=expected_digest)
    if decision.get("decision") == "promote":
        raise IntegrityViolation(
            "direct artifact promotion helper is disabled; use RuntimeService promotion lifecycle"
        )
    return record
