from __future__ import annotations

import json
import os
from pathlib import Path

from capt_solo.ctp.journal import CTPRuntime
from capt_solo.deployment import (
    DeploymentRequest,
    GovernedDeploymentExecutor,
    LocalScriptDeploymentAdapter,
)


def _python() -> str:
    return os.environ.get("PYTHON", os.sys.executable)


def test_dry_run_commits_with_evidence(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("payload", encoding="utf-8")
    ctp = CTPRuntime(journal_path=tmp_path / "journal.jsonl")
    adapter = LocalScriptDeploymentAdapter([_python()])
    request = DeploymentRequest(
        adapter="local-script",
        target="fixture",
        artifact=str(artifact),
        command=[_python(), "-c", "print('deploy')"],
        verify_command=[_python(), "-c", "print('verify')"],
        rollback_command=[_python(), "-c", "print('rollback')"],
        working_directory=str(tmp_path),
        dry_run=True,
        actor="test-suite",
        reason="validate governed deployment dry-run",
        idempotency_key="deployment-test-dry-run",
    )

    result = GovernedDeploymentExecutor(ctp).run(adapter, request)

    assert result.status == "dry_run"
    assert result.receipt.status == "committed"
    assert result.production_proven is False
    assert [item.phase for item in result.evidence] == ["execute", "verify"]
    assert all(item.returncode is None for item in result.evidence)
    assert ctp.integrity_check()
    ctp.close()


def test_failed_verification_aborts_and_rolls_back(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("payload", encoding="utf-8")
    ctp = CTPRuntime(journal_path=tmp_path / "journal.jsonl")
    adapter = LocalScriptDeploymentAdapter([_python()])
    request = DeploymentRequest(
        adapter="local-script",
        target="fixture",
        artifact=str(artifact),
        command=[_python(), "-c", "print('deploy')"],
        verify_command=[_python(), "-c", "raise SystemExit(3)"],
        rollback_command=[_python(), "-c", "print('rollback')"],
        working_directory=str(tmp_path),
        dry_run=False,
        actor="test-suite",
        reason="exercise rollback path",
    )

    result = GovernedDeploymentExecutor(ctp).run(adapter, request)

    assert result.status == "aborted"
    assert result.receipt.status == "aborted"
    assert result.rollback_attempted is True
    assert result.rollback_succeeded is True
    assert [item.phase for item in result.evidence] == ["execute", "verify", "rollback"]
    trail = ctp.audit_trail(result.tx_id)
    assert any(event["type"] == "abort" for event in trail)
    assert any("deployment_error" in event.get("note", "") for event in trail)
    ctp.close()


def test_missing_artifact_fails_preflight(tmp_path: Path) -> None:
    ctp = CTPRuntime(journal_path=tmp_path / "journal.jsonl")
    adapter = LocalScriptDeploymentAdapter([_python()])
    request = DeploymentRequest(
        adapter="local-script",
        target="fixture",
        artifact=str(tmp_path / "missing.txt"),
        command=[_python(), "-c", "print('deploy')"],
        working_directory=str(tmp_path),
        dry_run=True,
        actor="test-suite",
        reason="exercise preflight failure",
    )

    result = GovernedDeploymentExecutor(ctp).run(adapter, request)

    assert result.status == "aborted"
    assert result.evidence == []
    notes = [event.get("note", "") for event in ctp.audit_trail(result.tx_id)]
    preflight = json.loads(next(note for note in notes if '"phase": "preflight"' in note))
    assert preflight["artifact_exists"] is False
    ctp.close()
