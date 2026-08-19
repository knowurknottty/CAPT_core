from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .contracts import canonical_json
from .driver_host import tree_digest
from .verification import capture_git_status


class VerificationBaselineError(ValueError):
    """The persisted verification baseline is missing, altered, or mis-bound."""


_KEYS = frozenset({
    "schemaVersion", "kind", "missionId", "taskId", "driverRunId",
    "targetRoot", "beforeDigest", "beforeGitStatus", "capturedAt",
})


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _resolved_directory(path: str | Path, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise VerificationBaselineError(f"{label} is not a directory: {resolved}")
    return resolved


def _require_inside(path: Path, root: Path, label: str) -> None:
    if path != root and root not in path.parents:
        raise VerificationBaselineError(f"{label} is outside CAPT staging root")


def capture_verification_baseline(
    target_root: str,
    staging_root: str | Path,
    mission_id: str,
    task_id: str,
    driver_run_id: str,
    captured_at: str,
) -> dict[str, Any]:
    root = _resolved_directory(target_root, "target root")
    staging = Path(staging_root).expanduser()
    staging.mkdir(parents=True, exist_ok=True)
    staging = _resolved_directory(staging, "staging root")
    manifest = {
        "schemaVersion": "1.0.0",
        "kind": "verification_baseline",
        "missionId": str(mission_id),
        "taskId": str(task_id),
        "driverRunId": str(driver_run_id),
        "targetRoot": str(root),
        "beforeDigest": tree_digest(str(root)),
        "beforeGitStatus": capture_git_status(str(root)),
        "capturedAt": str(captured_at),
    }
    raw = canonical_json(manifest).encode("utf-8")
    digest = _sha256(raw)
    fd, temp_name = tempfile.mkstemp(prefix=".verification-baseline-", dir=str(staging))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        final_path = staging / "verification-baseline.json"
        os.replace(temp_name, final_path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    final_resolved = final_path.resolve(strict=True)
    _require_inside(final_resolved, staging, "verification baseline")
    return {
        "artifactPath": str(final_resolved),
        "artifactDigest": digest,
        "manifest": dict(manifest),
    }


def load_verified_baseline(
    path: str | Path,
    expected_digest: str,
    staging_root: str | Path,
    mission_id: str,
    task_id: str,
    driver_run_id: str,
    target_root: str,
) -> dict[str, Any]:
    staging = _resolved_directory(staging_root, "staging root")
    candidate = Path(path).expanduser().resolve(strict=True)
    _require_inside(candidate, staging, "verification baseline")
    raw = candidate.read_bytes()
    actual_digest = _sha256(raw)
    if not hmac.compare_digest(actual_digest, str(expected_digest)):
        raise VerificationBaselineError("verification baseline digest mismatch")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationBaselineError("verification baseline is not valid JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != _KEYS:
        raise VerificationBaselineError("verification baseline schema mismatch")
    if canonical_json(manifest).encode("utf-8") != raw:
        raise VerificationBaselineError("verification baseline is not canonical JSON")
    if manifest.get("schemaVersion") != "1.0.0" or manifest.get("kind") != "verification_baseline":
        raise VerificationBaselineError("verification baseline kind/schema mismatch")

    expected_identity = (str(mission_id), str(task_id), str(driver_run_id))
    actual_identity = (
        str(manifest.get("missionId")), str(manifest.get("taskId")),
        str(manifest.get("driverRunId")),
    )
    if actual_identity != expected_identity:
        raise VerificationBaselineError("verification baseline identity mismatch")
    expected_root = _resolved_directory(target_root, "target root")
    manifest_root = Path(str(manifest.get("targetRoot"))).expanduser().resolve()
    if manifest_root != expected_root:
        raise VerificationBaselineError("verification baseline target root mismatch")
    before_digest = manifest.get("beforeDigest")
    if not isinstance(before_digest, str) or not before_digest.startswith("sha256:"):
        raise VerificationBaselineError("verification baseline before digest is invalid")
    before_git = manifest.get("beforeGitStatus")
    if before_git is not None and not isinstance(before_git, str):
        raise VerificationBaselineError("verification baseline git status is invalid")
    if not isinstance(manifest.get("capturedAt"), str) or not manifest["capturedAt"]:
        raise VerificationBaselineError("verification baseline capture time is invalid")
    return dict(manifest)
