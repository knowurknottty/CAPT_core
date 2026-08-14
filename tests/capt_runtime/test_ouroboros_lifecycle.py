"""Regression coverage for the governed post-driver lifecycle boundary."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from capt_runtime.contracts import require
from capt_runtime.driver_host import tree_digest
from capt_runtime.verification import (
    VerificationFailure,
    build_verification_result,
    capture_git_status,
)
from desktop.desktop_runtime_client import (
    RuntimeClient,
    project_authoritative_state,
    project_evidence,
)


def _start_runtime(tmp: Path):
    tmp.mkdir(parents=True, exist_ok=True)
    ledger, token = tmp / "runtime.db", tmp / "token"
    sock = Path("/tmp") / ("capt-ouro-%s-%s.sock" % (os.getpid(), time.time_ns()))
    root = Path(__file__).resolve().parents[2]
    proc = __import__("subprocess").Popen(
        [os.environ.get("CAPT_TEST_PYTHON", sys.executable), "-c",
         "import runpy; runpy.run_path('desktop/capt_runtime_service.py', run_name='__main__')",
         "--ledger", str(ledger), "--sock", str(sock), "--token-file", str(token)],
        cwd=root, stdout=__import__("subprocess").PIPE, stderr=__import__("subprocess").PIPE,
    )
    for _ in range(100):
        if sock.exists():
            break
        if proc.poll() is not None:
            raise AssertionError(proc.stderr.read().decode())
        time.sleep(0.05)
    assert sock.exists(), "runtime service did not start"
    client = RuntimeClient(str(sock), str(token))
    client.connect()
    return client, ledger, proc


def _stop_runtime(client: RuntimeClient, proc) -> None:
    client.disconnect()
    proc.terminate()
    proc.wait(timeout=5)


def _git_repo(tmp: Path, *, dirty: bool = False) -> Path:
    repo = tmp / "target"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "README.md").write_text("# target\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=test", "commit", "-qm", "init"],
        cwd=repo,
        check=True,
    )
    if dirty:
        (repo / "preexisting-untracked.txt").write_text("operator dirt\n")
    return repo


def _fake_hermes(tmp: Path, *, mutate: bool = False, fail: bool = False) -> Path:
    exe = tmp / ("fake-hermes-fail" if fail else ("fake-hermes-mutate" if mutate else "fake-hermes"))
    body = "#!/bin/sh\n"
    if mutate:
        body += "printf driver-created > driver-created.txt\n"
    if fail:
        body += "exit 1\n"
    body += "printf 'OBSERVATION: bounded inspection completed\\n'\n"
    exe.write_text(body)
    exe.chmod(0o755)
    return exe


def _payload(repo: Path, executable: Path, suffix: str) -> dict:
    return {
        "objective": "Inspect the bounded repository.",
        "targetRoot": str(repo),
        "executable": str(executable),
        "missionId": "m-ouro-" + suffix,
        "taskId": "t-ouro-" + suffix,
        "driverRunId": "dr-ouro-" + suffix,
        "grantId": "g-ouro-" + suffix,
        "leaseId": "l-ouro-" + suffix,
        "claimId": "cl-ouro-" + suffix,
        "policyDecisionId": "pd-ouro-" + suffix,
    }


def _state(client: RuntimeClient, prefix: str, suffix: str) -> dict:
    stream_prefix = {"driverrun": "driverrun-dr", "t": "task-t", "cl": "claim-cl"}.get(prefix, prefix)
    return client.get_state(stream_prefix + "-ouro-" + suffix)


def test_git_baseline_allows_preexisting_dirt_and_detects_new_mutation(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path, dirty=True)
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("artifact")
    artifact_digest = "sha256:" + __import__("hashlib").sha256(b"artifact").hexdigest()
    before_tree, before_git = tree_digest(str(repo)), capture_git_status(str(repo))
    result = build_verification_result(
        str(repo), before_tree, str(artifact), artifact_digest, "test",
        claim_id="cl-git", supporting_evidence_ids=["ev-real"], before_git_status=before_git,
    )
    assert result["_view"]["checks"]["noGitMutation"] is True
    (repo / "new-driver-file.txt").write_text("new")
    with pytest.raises(VerificationFailure, match="no_git=False"):
        build_verification_result(
            str(repo), before_tree, str(artifact), artifact_digest, "test",
            claim_id="cl-git", supporting_evidence_ids=["ev-real"], before_git_status=before_git,
        )


def test_happy_driver_lifecycle_is_terminal_and_consumed(tmp_path: Path) -> None:
    repo, exe, suffix = _git_repo(tmp_path, dirty=True), _fake_hermes(tmp_path), "happy"
    client, _ledger, proc = _start_runtime(tmp_path / "runtime")
    try:
        receipt = client.command("run_approved_hermes_inspection", _payload(repo, exe, suffix), "idem-ouro-happy")
        assert receipt["status"] == "accepted", receipt
        assert _state(client, "driverrun", suffix)["state"] == "completed"
        assert _state(client, "t", suffix)["state"] == "succeeded"
        claim = _state(client, "cl", suffix)
        assert claim["promotionState"] == "accepted"
        lease = _state(client, "capability-g", suffix)
        assert lease["usesConsumed"] == 1
        assert lease["grantState"] == "consumed"
        assert lease["lease"]["state"] == "exhausted"
        assert project_evidence(client, "m-ouro-" + suffix)[0]["evidenceId"] in claim["evidenceIds"]
        assert client.claimguard_disposition(claim["statement"], claim["claimId"])["committed"] is True
        assert client.verification(claim["claimId"])["committed"] is True
    finally:
        _stop_runtime(client, proc)


def test_post_driver_mutation_persists_negative_state_and_consumes_lease(tmp_path: Path) -> None:
    repo, exe, suffix = _git_repo(tmp_path), _fake_hermes(tmp_path, mutate=True), "failure"
    client, _ledger, proc = _start_runtime(tmp_path / "runtime")
    try:
        receipt = client.command("run_approved_hermes_inspection", _payload(repo, exe, suffix), "idem-ouro-failure")
        assert receipt["status"] == "accepted", receipt
        assert receipt["result"]["outcome"] == "verification_rejected"
        assert _state(client, "driverrun", suffix)["state"] == "completed"
        assert _state(client, "t", suffix)["state"] == "failed"
        claim = _state(client, "cl", suffix)
        assert claim["promotionState"] == "rejected"
        assert claim["verificationStatus"] == "contradicted"
        verification = client.verification(claim["claimId"])
        assert verification["committed"] is True
        assert verification["status"]["kind"] == "contradicted"
        lease = _state(client, "capability-g", suffix)
        assert lease["usesConsumed"] == 1
        assert lease["lease"]["state"] == "exhausted"
    finally:
        _stop_runtime(client, proc)


def test_unavailable_driver_before_dispatch_does_not_consume_lease(tmp_path: Path) -> None:
    repo, suffix = _git_repo(tmp_path), "nodispatch"
    client, _ledger, proc = _start_runtime(tmp_path / "runtime")
    try:
        missing = tmp_path / "not-an-executable"
        receipt = client.command("run_approved_hermes_inspection", _payload(repo, missing, suffix), "idem-ouro-nodispatch")
        assert receipt["status"] == "rejected", receipt
        lease = _state(client, "capability-g", suffix)
        assert lease["usesConsumed"] == 0
        assert lease["lease"]["state"] == "active"
    finally:
        _stop_runtime(client, proc)


def test_restart_does_not_repeat_completed_external_work(tmp_path: Path) -> None:
    repo, exe, suffix = _git_repo(tmp_path), _fake_hermes(tmp_path), "restart"
    root = tmp_path / "runtime"
    client, ledger, proc = _start_runtime(root)
    payload = _payload(repo, exe, suffix)
    try:
        first = client.command("run_approved_hermes_inspection", payload, "idem-ouro-restart")
        assert first["status"] == "accepted", first
    finally:
        _stop_runtime(client, proc)
    client, _ledger, proc = _start_runtime(root)
    try:
        second = client.command("run_approved_hermes_inspection", payload, "idem-ouro-restart")
        assert second["status"] == "idempotent", second
        assert second["result"]["driverRunId"] == "dr-ouro-" + suffix
        assert _state(client, "driverrun", suffix)["state"] == "completed"
        assert _state(client, "capability-g", suffix)["usesConsumed"] == 1
    finally:
        _stop_runtime(client, proc)


def test_full_digest_ids_are_contract_valid_and_noncolliding(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    artifact.write_text("x")
    digest = "sha256:" + __import__("hashlib").sha256(b"x").hexdigest()
    one = build_verification_result(str(tmp_path), tree_digest(str(tmp_path)), str(artifact), digest, "test", claim_id="cl-a", supporting_evidence_ids=["ev-a"])
    two = build_verification_result(str(tmp_path), tree_digest(str(tmp_path)), str(artifact), digest, "test", claim_id="cl-b", supporting_evidence_ids=["ev-b"])
    require("VerificationResult", {k: v for k, v in one.items() if k != "_view"})
    assert one["verificationId"] != two["verificationId"]
    assert len(one["verificationId"]) > 32


def test_global_projection_preserves_committed_contradiction(tmp_path: Path) -> None:
    repo, exe, suffix = _git_repo(tmp_path), _fake_hermes(tmp_path, mutate=True), "projection"
    client, _ledger, proc = _start_runtime(tmp_path / "runtime")
    try:
        client.command("run_approved_hermes_inspection", _payload(repo, exe, suffix), "idem-ouro-projection")
        view = project_authoritative_state(client)
        verification = view["verificationsByClaim"]["cl-ouro-" + suffix]
        assert verification["committed"] is True
        assert verification["status"]["kind"] == "contradicted"
    finally:
        _stop_runtime(client, proc)


def test_indeterminate_dispatch_is_lost_suspended_and_consumed(tmp_path: Path) -> None:
    repo, exe, suffix = _git_repo(tmp_path), _fake_hermes(tmp_path, fail=True), "indeterminate"
    client, _ledger, proc = _start_runtime(tmp_path / "runtime")
    try:
        receipt = client.command("run_approved_hermes_inspection", _payload(repo, exe, suffix), "idem-ouro-indeterminate")
        assert receipt["status"] == "rejected", receipt
        assert _state(client, "driverrun", suffix)["state"] == "lost"
        assert _state(client, "driverrun", suffix)["reconciliationStatus"] == "required"
        assert _state(client, "t", suffix)["state"] == "suspended"
        lease = _state(client, "capability-g", suffix)
        assert lease["usesConsumed"] == 1
        assert lease["reservations"][0]["state"] == "awaiting_reconciliation"
        # Existing Core governed operator path gives suspended work a durable,
        # explicit terminal disposition without reviving the consumed lease.
        cancelled = client.command("cancel_task", {"taskId": "t-ouro-" + suffix, "reason": "operator reconciled indeterminate boundary"}, "idem-ouro-indeterminate-cancel")
        assert cancelled["status"] == "accepted"
        assert _state(client, "t", suffix)["state"] == "cancelled"
        assert _state(client, "capability-g", suffix)["usesConsumed"] == 1
    finally:
        _stop_runtime(client, proc)

def test_same_key_replays_durably_and_rejects_different_payload(tmp_path: Path) -> None:
    repo, exe, suffix = _git_repo(tmp_path), _fake_hermes(tmp_path), "idem"
    client, _ledger, proc = _start_runtime(tmp_path / "runtime")
    try:
        payload = _payload(repo, exe, suffix)
        first = client.command("run_approved_hermes_inspection", payload, "idem-ouro-durable")
        replay = client.command("run_approved_hermes_inspection", payload, "idem-ouro-durable")
        assert first["status"] == "accepted"
        assert replay["status"] == "idempotent"
        states = client.get_stream_events("driverrun-dr-ouro-" + suffix)
        assert [event["payload"]["toState"] for event in states if event["eventType"] == "DriverRunStateChanged"].count("running") == 1
        changed = dict(payload)
        changed["objective"] = "A different bounded objective."
        conflict = client.command("run_approved_hermes_inspection", changed, "idem-ouro-durable")
        assert conflict["status"] == "rejected"
        assert conflict["classification"] == "idempotency"
    finally:
        _stop_runtime(client, proc)
