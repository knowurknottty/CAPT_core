"""Focused tests for the Agent Runner continuity-aware recovery subsystem.

Verifies that resume recovery integrates the proven capt_solo.continuity
machinery: builds a ContinuityPack from recovered CAPT state, evaluates it,
produces a divergence-aware resume plan, and appends an append-only,
corruption-detecting recovery receipt. No transcript, no response artifact, no
copied summary is used. Owner CAPT home is never touched (isolated CAPT_SOLO_HOME).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = "/Users/knowurknot/capt-solo-release"


def _seed_workspace_and_mission(root: Path) -> str:
    ws = root / "capt-solo"
    ws.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    (ws / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(ws), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(ws), "-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-qm", "seed"],
        check=True,
    )
    head = subprocess.run(["git", "-C", str(ws), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    from capt_solo.evidence import CheckpointStore, MissionCheckpoint

    CheckpointStore(str(ws)).save(
        MissionCheckpoint(
            mission_id="m-rec",
            project_id="capt-solo",
            objective="Prove continuity-aware recovery",
            current_phase="PHASE_RECOVERY_PROOF",
            latest_verified_state=head,
            next_safe_action="report next justified action",
            decisions_made=["Recovery integrates continuity.evaluate_pack"],
            completed_work=["Seeded recovery test mission"],
        )
    )
    return str(ws)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("CAPT_SOLO_HOME", str(home))
    ws = _seed_workspace_and_mission(tmp_path)
    return ws


def test_evaluate_resume_returns_verdict(isolated):
    from capt_solo.agent.recovery import evaluate_resume

    report, err = evaluate_resume(isolated, "m-rec")
    assert err is None, err
    assert report is not None
    assert report.mission_id == "m-rec"
    assert report.continuity_status in ("PASS", "WARN", "BLOCK")
    # receipt must be verifiable
    assert report.receipt_verified is True
    # no divergence in a fresh seed -> resume plan is plain resume
    assert report.divergence == {}
    assert report.resume_plan.get("status") == "resume"


def test_divergence_regression_after_git_head_change(isolated):
    """Permanent regression for the defect found by ad-hoc verification:

    evaluate_resume previously supplied empty Git identity, so divergence
    detection was inert. After resolving canonical workspace Git state via
    boot.resolve_workspace, a changed HEAD must be detected and the resume plan
    must become resume_with_divergence.
    """
    import subprocess

    from capt_solo.agent.recovery import evaluate_resume

    # 1) same HEAD -> no divergence
    before, err = evaluate_resume(isolated, "m-rec")
    assert err is None, err
    assert before.divergence == {}
    assert before.resume_plan.get("status") == "resume"

    # 2) change the workspace Git HEAD (new commit)
    ws = isolated
    (Path(ws) / "divergence_marker.txt").write_text("changed")
    subprocess.run(["git", "-C", str(ws), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(ws), "-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-qm", "diverge"],
        check=True,
    )

    # 3) changed HEAD -> divergence detected + resume_with_divergence
    after, err2 = evaluate_resume(isolated, "m-rec")
    assert err2 is None, err2
    assert after.divergence, "divergence must be detected after Git HEAD change"
    assert after.resume_plan.get("status") == "resume_with_divergence"


def test_recovery_receipt_is_append_only_and_verifiable(isolated):
    from capt_solo.agent.recovery import (
        append_recovery_receipt,
        evaluate_resume,
        verify_recovery_chain,
    )

    report, _ = evaluate_resume(isolated, "m-rec")
    rid1 = append_recovery_receipt(isolated, "m-rec", report)
    rid2 = append_recovery_receipt(isolated, "m-rec", report)
    assert rid1 is not None and rid2 is not None and rid1 != rid2
    chain = verify_recovery_chain(isolated, "m-rec")
    assert chain["exists"] is True
    assert chain["valid"] is True
    assert chain["entries"] >= 2


def test_resume_report_includes_continuity_block(isolated):
    from capt_solo.agent import resume_report

    rep = resume_report(workspace_path=isolated, mission_id="m-rec")
    assert rep["execution_mode"] == "GOVERNED"
    assert "continuity" in rep
    assert rep["continuity"]["status"] in ("PASS", "WARN", "BLOCK")
    assert rep["continuity"]["receipt_verified"] is True
    assert rep["source"].startswith("CAPT state")
    # receipt chain file exists on disk
    chain_path = Path(isolated) / ".capt" / "continuity" / "m-rec.receipts.jsonl"
    assert chain_path.exists()


def test_continuity_degrades_on_missing_checkpoint(isolated):
    from capt_solo.agent.recovery import evaluate_resume

    report, err = evaluate_resume(isolated, "does-not-exist")
    assert report is None
    assert "checkpoint not found" in (err or "")
