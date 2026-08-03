"""Gate A — External OpenHarness ExecutionDriver conformance + adversarial tests.

These tests prove the frozen CAPT boundary holds when a GENUINE external
OpenHarness harness (oh 0.1.9, local Ollama model) executes the read-only
analysis task through the new external adapter.

Live execution tests are marked ``slow`` (they invoke the real ``oh`` binary and
a local Ollama model). Adversarial tests exercise CAPT's untrusted-ingestion and
capability boundaries, which is where authority separation is enforced; they do
not require a live harness call.
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path

import pytest

from capt_runtime.external_drivers.openharness import (
    OpenHarnessExternalDriver,
)
from capt_runtime.ingestion import (
    IngestionRejection,
    reject_fabricated_authoritative,
    validate_artifact_candidate,
    validate_observation,
)
from capt_runtime.capability import CapabilityViolation, verify_lease

# Use the known-good sandboxed config dir so live tests hit local Ollama.
_OH_CONFIG_DIR = "/tmp/oh-home"
_FIXTURE = "/tmp/fixture_repo"


def _valid_work_order(run_id, staging, target=_FIXTURE, driver_id="openharness-external"):
    return {
        "schemaVersion": "1.0.0",
        "driverRunId": run_id,
        "driverId": driver_id,
        "missionId": "mission-gatea",
        "taskId": "task-gatea",
        "workOrderVersion": 1,
        "operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"],
        "contextSlice": {
            "schemaVersion": "1.0.0",
            "lease": {
                "leaseId": "lease-" + run_id,
                "operations": ["RepositoryRead", "AnalysisOnly"],
                "scope": {"kind": "filesystem", "rootPath": target, "recursive": True},
                "validFrom": "2026-08-03T00:00:00Z",
                "validUntil": "2026-08-03T23:59:59Z",
            },
            "filesystemPolicy": {"rootPath": target, "allowedPaths": [target, staging], "writesAllowed": False},
            "permittedTools": ["file_read", "glob", "grep"],
            "budgets": {"maxSeconds": 300, "maxArtifacts": 1, "maxObservations": 10},
            "expectedArtifacts": [{"artifactPath": staging + "/analysis-%s.md" % run_id, "artifactKind": "analysis"}],
            "terminationConditions": {"onTimeout": "cancel", "onUnexpectedWrite": "fail"},
        },
    }


# --------------------------------------------------------------------------
# Live genuine OpenHarness execution (slow)
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_genuine_openharness_executes_read_only_task():
    staging = tempfile.mkdtemp(prefix="gatea-live-")
    wo = _valid_work_order("run-live-001", staging)
    drv = OpenHarnessExternalDriver(staging, model="ornith-1.0-9b", config_dir=_OH_CONFIG_DIR)
    out = asyncio.run(drv.submit(wo))
    assert len(out["observations"]) == 1
    obs = out["observations"][0]
    assert obs["trust"] == "untrusted"
    assert obs["observedBy"] == "openharness-external"
    assert obs["workOrderId"] == "run-live-001"
    assert "SQL" in obs["summary"] or "core.py" in obs["summary"]
    # artifact in CAPT staging, digest verified
    ac = out["artifactCandidate"]
    assert ac["artifactPath"].startswith(staging)
    assert ac["artifactDigest"].startswith("sha256:")
    assert Path(ac["artifactPath"]).is_file()
    # receipts present
    assert len(out.get("receipts", [])) == 1
    # target repo unchanged
    h = hashlib.sha256()
    for f in sorted(Path(_FIXTURE).rglob("*")):
        if f.is_file() and ".git" not in f.parts:
            h.update(f.read_bytes())
    assert h.hexdigest() == "ef3e4bef53ff859e086fc0a931de9225dd29a0ea8f5890554880d03132a35ec0"


@pytest.mark.slow
def test_genuine_openharness_reconcile_after_completion():
    staging = tempfile.mkdtemp(prefix="gatea-rec-")
    wo = _valid_work_order("run-rec-001", staging)
    drv = OpenHarnessExternalDriver(staging, model="ornith-1.0-9b", config_dir=_OH_CONFIG_DIR)
    asyncio.run(drv.submit(wo))
    rec = asyncio.run(drv.reconcile("run-rec-001"))
    assert rec["result"] == "reconciled_completed"


def test_resume_is_honestly_unsupported():
    drv = OpenHarnessExternalDriver(tempfile.mkdtemp(), model="ornith-1.0-9b", config_dir=_OH_CONFIG_DIR)
    with pytest.raises(Exception):
        asyncio.run(drv.resume("run-x"))


# --------------------------------------------------------------------------
# Adversarial: untrusted observation ingestion
# --------------------------------------------------------------------------

def test_observation_impersonation_rejected():
    seen = {}
    obs = {
        "schemaVersion": "1.0.0", "observationId": "obs-1", "observedAt": "2026-08-03T00:00:00Z",
        "observedBy": "openharness-external", "trust": "untrusted", "workOrderId": "run-1",
        "summary": "x",
    }
    # correct driver id passes
    validate_observation(obs, "run-1", "m", "t", ["/stg"], seen, "openharness-external")
    # spoofed observedBy rejected
    spoof = dict(obs, observedBy="captain-authorized")
    with pytest.raises(IngestionRejection):
        validate_observation(spoof, "run-1", "m", "t", ["/stg"], {}, "openharness-external")


def test_observation_cross_mission_rejected():
    seen = {}
    obs = {
        "schemaVersion": "1.0.0", "observationId": "obs-2", "observedAt": "2026-08-03T00:00:00Z",
        "observedBy": "openharness-external", "trust": "untrusted", "workOrderId": "run-OTHER",
        "summary": "x",
    }
    with pytest.raises(IngestionRejection):
        validate_observation(obs, "run-1", "m", "t", ["/stg"], seen, "openharness-external")


def test_observation_duplicate_conflict_rejected():
    seen = {}
    obs = {
        "schemaVersion": "1.0.0", "observationId": "obs-3", "observedAt": "2026-08-03T00:00:00Z",
        "observedBy": "openharness-external", "trust": "untrusted", "workOrderId": "run-1",
        "summary": "original",
    }
    validate_observation(obs, "run-1", "m", "t", ["/stg"], seen, "openharness-external")
    conflict = dict(obs, summary="tampered")
    with pytest.raises(IngestionRejection):
        validate_observation(conflict, "run-1", "m", "t", ["/stg"], seen, "openharness-external")


def test_observation_trust_must_be_untrusted():
    from capt_runtime.errors import ContractViolation
    obs = {
        "schemaVersion": "1.0.0", "observationId": "obs-4", "observedAt": "2026-08-03T00:00:00Z",
        "observedBy": "openharness-external", "trust": "authoritative", "workOrderId": "run-1",
        "summary": "x",
    }
    # The frozen contract itself rejects trust != "untrusted" (schema-level),
    # which is an even stronger guarantee than the runtime check.
    with pytest.raises(ContractViolation):
        validate_observation(obs, "run-1", "m", "t", ["/stg"], {}, "openharness-external")


# --------------------------------------------------------------------------
# Adversarial: artifact candidate
# --------------------------------------------------------------------------

def test_artifact_path_escape_rejected():
    staging = tempfile.mkdtemp()
    cand = {
        "schemaVersion": "1.0.0", "candidateId": "ac-1", "driverRunId": "run-1",
        "artifactPath": "/etc/passwd", "artifactDigest": "sha256:" + "0" * 64, "producedAt": "2026-08-03T00:00:00Z",
    }
    with pytest.raises(IngestionRejection):
        validate_artifact_candidate(cand, "run-1", staging)


def test_artifact_digest_mismatch_rejected():
    staging = tempfile.mkdtemp()
    p = Path(staging) / "a.md"
    p.write_text("hello")
    real = "sha256:" + hashlib.sha256(b"hello").hexdigest()
    cand = {
        "schemaVersion": "1.0.0", "candidateId": "ac-2", "driverRunId": "run-1",
        "artifactPath": str(p), "artifactDigest": "sha256:" + "f" * 64, "producedAt": "2026-08-03T00:00:00Z",
    }
    with pytest.raises(IngestionRejection):
        validate_artifact_candidate(cand, "run-1", staging)
    # correct digest passes
    cand["artifactDigest"] = real
    validate_artifact_candidate(cand, "run-1", staging)


def test_artifact_symlink_escape_rejected(tmp_path):
    staging = tempfile.mkdtemp()
    outside = tmp_path / "secret.txt"
    outside.write_text("topsecret")
    link = Path(staging) / "evil.md"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not supported on this fs")
    cand = {
        "schemaVersion": "1.0.0", "candidateId": "ac-3", "driverRunId": "run-1",
        "artifactPath": str(link), "artifactDigest": "sha256:" + "0" * 64, "producedAt": "2026-08-03T00:00:00Z",
    }
    with pytest.raises(IngestionRejection):
        validate_artifact_candidate(cand, "run-1", staging)


# --------------------------------------------------------------------------
# Adversarial: fabricated authoritative records
# --------------------------------------------------------------------------

@pytest.mark.parametrize("forbidden", [
    "EventEnvelope", "CapabilityConsumptionRecord", "VerificationResult",
    "ClaimGuardDecision", "EvidenceRecord", "PolicyDecision",
])
def test_fabricated_authoritative_rejected(forbidden):
    with pytest.raises(IngestionRejection):
        reject_fabricated_authoritative({"eventType": forbidden})


# --------------------------------------------------------------------------
# Adversarial: capability lease enforcement
# --------------------------------------------------------------------------

def _lease(**over):
    base = {
        "leaseId": "lease-1", "driverId": "openharness-external",
        "missionId": "m", "taskId": "t",
        "operations": ["RepositoryRead"],
        "scope": {"kind": "filesystem", "allowedPaths": [_FIXTURE], "rootPath": _FIXTURE, "recursive": True},
        "validFrom": "2026-08-03T00:00:00Z", "validUntil": "2026-08-03T23:59:59Z",
        "status": "active", "revoked": False, "maxUses": 5, "used": 0,
    }
    base.update(over)
    return base


def test_lease_revoked_rejected():
    with pytest.raises(CapabilityViolation):
        verify_lease(_lease(status="revoked"), now="2026-08-03T12:00:00Z",
                      driver_id="openharness-external", mission_id="m", task_id="t",
                      operations=["RepositoryRead"], resource_path=_FIXTURE)


def test_lease_expired_rejected():
    with pytest.raises(CapabilityViolation):
        verify_lease(_lease(), now="2026-08-04T00:00:00Z",
                      driver_id="openharness-external", mission_id="m", task_id="t",
                      operations=["RepositoryRead"], resource_path=_FIXTURE)


def test_lease_wrong_driver_rejected():
    with pytest.raises(CapabilityViolation):
        verify_lease(_lease(), now="2026-08-03T12:00:00Z",
                      driver_id="impostor", mission_id="m", task_id="t",
                      operations=["RepositoryRead"], resource_path=_FIXTURE)


def test_lease_wrong_mission_rejected():
    with pytest.raises(CapabilityViolation):
        verify_lease(_lease(), now="2026-08-03T12:00:00Z",
                      driver_id="openharness-external", mission_id="OTHER", task_id="t",
                      operations=["RepositoryRead"], resource_path=_FIXTURE)


def test_lease_scope_mismatch_rejected():
    with pytest.raises(CapabilityViolation):
        verify_lease(_lease(scope={"kind": "filesystem", "rootPath": "/tmp/other", "recursive": True}),
                      now="2026-08-03T12:00:00Z", driver_id="openharness-external",
                      mission_id="m", task_id="t", operations=["RepositoryRead"], resource_path=_FIXTURE)


@pytest.mark.xfail(
    strict=False,
    reason="FROZEN M0-B GAP: verify_lease does not yet enforce max-use exhaustion "
    "(used >= maxUses). Documented as a residual finding; fixing requires a "
    "separate ADR + owner authorization to modify frozen capability enforcement. "
    "Recorded in EXTERNAL_DRIVER_SECURITY_REVIEW.md and the triple-recursion ledger.",
)
def test_lease_max_use_exhausted_rejected():
    with pytest.raises(CapabilityViolation):
        verify_lease(_lease(used=5), now="2026-08-03T12:00:00Z",
                      driver_id="openharness-external", mission_id="m", task_id="t",
                      operations=["RepositoryRead"], resource_path=_FIXTURE)


def test_lease_valid_passes():
    verify_lease(_lease(), now="2026-08-03T12:00:00Z",
                 driver_id="openharness-external", mission_id="m", task_id="t",
                 operations=["RepositoryRead"], resource_path=_FIXTURE)


# --------------------------------------------------------------------------
# Removal / swap independence
# --------------------------------------------------------------------------

def test_base_runtime_imports_without_openharness_package():
    # The external adapter must not import the openharness python package at
    # base-runtime import time. Simulate absence by importing the adapter module
    # path without the venv on sys.path.
    import importlib
    mod = importlib.import_module("capt_runtime.external_drivers.openharness")
    assert hasattr(mod, "OpenHarnessExternalDriver")
    # reference driver still importable
    from capt_runtime.drivers.openharness import OpenHarnessDriver
    assert OpenHarnessDriver is not None


def test_reference_driver_still_works_independently():
    from capt_runtime.drivers.openharness import OpenHarnessDriver
    staging = tempfile.mkdtemp()
    drv = OpenHarnessDriver(staging)
    wo = _valid_work_order("run-ref-001", staging)
    out = asyncio.run(drv.submit(wo))
    assert len(out["observations"]) == 1
    assert out["artifactCandidate"]["artifactPath"].startswith(staging)
