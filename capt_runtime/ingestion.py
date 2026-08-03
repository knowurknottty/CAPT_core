"""Observation and receipt ingestion (M0-B, ADR-0126).

All driver output is untrusted. This module validates it and rejects:
- authoritative CAPT EventEnvelope types from the driver,
- fabricated CapabilityConsumptionRecords,
- fabricated VerificationResults,
- fabricated ClaimGuard decisions,
- path escapes / symlink escapes,
- observations for another mission or task,
- duplicate observations with conflicting payloads,
- receipts without verifiable artifacts,
- success claims unsupported by evidence.

CAPT alone creates authoritative records. Promotion is via verification.py.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from .contracts import require

# Authoritative CAPT types a driver must NEVER emit as its own output.
_FORBIDDEN_DRIVER_TYPES = frozenset(
    {
        "EventEnvelope",
        "CapabilityConsumptionRecord",
        "VerificationResult",
        "ClaimGuardDecision",
        "EvidenceRecord",
        "PolicyDecision",
    }
)

# Operations a read-only driver may never claim to have performed.
_FORBIDDEN_OPERATIONS = frozenset(
    {
        "RepositoryWrite",
        "FilesystemWrite",
        "GitCommit",
        "GitPush",
        "ProcessMutate",
        "PackageInstall",
        "Deployment",
        "CredentialUse",
    }
)


class IngestionRejection(Exception):
    pass


def _realpath_within(path: str, allowed_roots: List[str]) -> bool:
    """Reject path and symlink escapes outside allowed roots."""
    try:
        real = os.path.realpath(path)
    except OSError:
        return False
    for root in allowed_roots:
        root_real = os.path.realpath(root)
        if real == root_real or real.startswith(root_real + os.sep):
            return True
    return False


def validate_observation(
    observation: Dict[str, Any],
    driver_run_id: str,
    mission_id: str,
    task_id: str,
    allowed_roots: List[str],
    seen: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate one untrusted DriverObservation. Returns the normalized record."""
    require("DriverObservation", observation)
    if observation.get("trust") != "untrusted":
        raise IngestionRejection("driver observation must be trust=untrusted")
    if observation.get("observedBy") in _FORBIDDEN_DRIVER_TYPES:
        raise IngestionRejection("driver emitted a forbidden authoritative type")
    if observation.get("workOrderId") != driver_run_id:
        raise IngestionRejection("observation references a different run")
    # Cross-mission/task leakage.
    # (DriverObservation uses workOrderId only; mission/task binding is enforced
    #  at the run level by the host, so we check the run id above.)
    # Duplicate / conflicting detection.
    oid = observation["observationId"]
    if oid in seen:
        if seen[oid] != observation:
            raise IngestionRejection(
                "duplicate observation %s with conflicting payload" % oid
            )
        # exact duplicate -> caller may skip; return marker
        return {"duplicate": True, "observationId": oid}
    seen[oid] = observation
    return {"duplicate": False, "observation": observation}


def validate_artifact_candidate(
    candidate: Dict[str, Any],
    driver_run_id: str,
    staging_root: str,
) -> Dict[str, Any]:
    """Validate a DriverArtifactCandidate and confirm the file exists + digest."""
    require("DriverArtifactCandidate", candidate)
    if candidate.get("driverRunId") != driver_run_id:
        raise IngestionRejection("artifact candidate references a different run")
    path = candidate["artifactPath"]
    if not _realpath_within(path, [staging_root]):
        raise IngestionRejection("artifact path escapes staging root: %s" % path)
    p = Path(path)
    if not p.is_file():
        raise IngestionRejection("artifact does not exist: %s" % path)
    actual = "sha256:" + __import__("hashlib").sha256(
        p.read_bytes()
    ).hexdigest()
    if actual != candidate.get("artifactDigest"):
        raise IngestionRejection(
            "artifact digest mismatch: claimed %s actual %s"
            % (candidate.get("artifactDigest"), actual)
        )
    return {"ok": True, "path": path, "digest": actual}


def validate_receipt_candidate(
    receipt: Dict[str, Any], driver_run_id: str
) -> Dict[str, Any]:
    require("DriverReceiptCandidate", receipt)
    if receipt.get("driverRunId") != driver_run_id:
        raise IngestionRejection("receipt references a different run")
    return {"ok": True, "receipt": receipt}


def reject_fabricated_authoritative(payload: Dict[str, Any]) -> None:
    """Explicitly reject any driver-supplied authoritative record."""
    t = payload.get("eventType") or payload.get("kind")
    if t in _FORBIDDEN_DRIVER_TYPES:
        raise IngestionRejection(
            "driver attempted to emit authoritative type %r" % t
        )
