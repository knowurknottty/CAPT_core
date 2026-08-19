from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from capt_runtime.verification_baseline import (
    VerificationBaselineError,
    capture_verification_baseline,
    load_verified_baseline,
)


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "tracked.txt").write_text("baseline\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=test",
         "commit", "-qm", "init"],
        cwd=repo,
        check=True,
    )
    return repo

def test_baseline_round_trip_is_content_addressed(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    staging = tmp_path / "staging"
    rec = capture_verification_baseline(
        str(repo), staging, "m1", "t1", "dr1", "2026-08-19T12:00:00Z"
    )
    path = Path(rec["artifactPath"])
    assert path == (staging / "verification-baseline.json").resolve()
    assert rec["artifactDigest"].startswith("sha256:")
    assert json.loads(path.read_text())["kind"] == "verification_baseline"

    loaded = load_verified_baseline(
        str(path), rec["artifactDigest"], staging, "m1", "t1", "dr1", str(repo)
    )
    assert loaded["beforeDigest"].startswith("sha256:")
    assert loaded["beforeGitStatus"] == ""
    assert loaded["targetRoot"] == str(repo.resolve())


def test_load_rejects_tampered_baseline(tmp_path: Path) -> None:
    repo, staging = _git_repo(tmp_path), tmp_path / "staging"
    rec = capture_verification_baseline(
        str(repo), staging, "m1", "t1", "dr1", "2026-08-19T12:00:00Z"
    )
    Path(rec["artifactPath"]).write_text("{}")
    with pytest.raises(VerificationBaselineError, match="digest"):
        load_verified_baseline(
            rec["artifactPath"], rec["artifactDigest"], staging,
            "m1", "t1", "dr1", str(repo),
        )

@pytest.mark.parametrize(
    ("field", "value"),
    [("missionId", "m2"), ("taskId", "t2"), ("driverRunId", "dr2")],
)
def test_load_rejects_identity_mismatch(tmp_path: Path, field: str, value: str) -> None:
    repo, staging = _git_repo(tmp_path), tmp_path / "staging"
    rec = capture_verification_baseline(
        str(repo), staging, "m1", "t1", "dr1", "2026-08-19T12:00:00Z"
    )
    args = {"missionId": "m1", "taskId": "t1", "driverRunId": "dr1"}
    args[field] = value
    with pytest.raises(VerificationBaselineError, match="identity"):
        load_verified_baseline(
            rec["artifactPath"], rec["artifactDigest"], staging,
            args["missionId"], args["taskId"], args["driverRunId"], str(repo),
        )


def test_load_rejects_staging_path_escape(tmp_path: Path) -> None:
    repo, staging = _git_repo(tmp_path), tmp_path / "staging"
    rec = capture_verification_baseline(
        str(repo), staging, "m1", "t1", "dr1", "2026-08-19T12:00:00Z"
    )
    outside = tmp_path / "outside.json"
    outside.write_bytes(Path(rec["artifactPath"]).read_bytes())
    digest = "sha256:" + __import__("hashlib").sha256(outside.read_bytes()).hexdigest()
    with pytest.raises(VerificationBaselineError, match="staging"):
        load_verified_baseline(
            str(outside), digest, staging, "m1", "t1", "dr1", str(repo)
        )


def test_load_rejects_target_root_mismatch(tmp_path: Path) -> None:
    repo, staging = _git_repo(tmp_path), tmp_path / "staging"
    other = tmp_path / "other"; other.mkdir()
    rec = capture_verification_baseline(
        str(repo), staging, "m1", "t1", "dr1", "2026-08-19T12:00:00Z"
    )
    with pytest.raises(VerificationBaselineError, match="target root"):
        load_verified_baseline(
            rec["artifactPath"], rec["artifactDigest"], staging,
            "m1", "t1", "dr1", str(other),
        )
