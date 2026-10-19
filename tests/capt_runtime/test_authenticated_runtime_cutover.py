"""Slow, isolated real-venv cutover proof; NEVER touches ~/.capt service.

Requires explicitly supplied source venv paths and creates a fresh temporary
RuntimeService, token, ledger and socket. No model providers are dispatched.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import base64
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

from desktop.desktop_runtime_client import RuntimeClient
from capt_runtime.checkpoint import verify_checkpoint

SCRIPT = Path(__file__).resolve().parents[2] / "capt_ui/surfaces/desktop_swift/script/reversible_runtime_switch.py"
SWITCH = runpy.run_path(str(SCRIPT))["switch_runtime"]
OLD = "9906bf5fd71ec61a8feb3ea078dd26857703acb1"
NEW = "0fee6655a33cd7d69162a4d8404cd332485d1e29"
PRODUCTION_STATE = Path("/Users/knowurknot/.capt")


def run_cli(active: Path, root: Path, action: str, *, seed: bool = False):
    env = {"HOME": str(root), "CAPT_STATE_DIR": str(root),
           "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "LANG": "en_US.UTF-8",
           # This is a synthetic *test-only* encryption key. Never access
           # the user's macOS Keychain or production CAPT state key.
           "CAPT_STATE_KEY_B64": base64.b64encode(b"\x42" * 32).decode("ascii")}
    cmd = [str(active / "bin/python"), "-I", "-m", "capt_cli", "--json", action,
           "--state-dir", str(root)]
    if seed:
        cmd.append("--seed")
    p = subprocess.run(cmd, cwd=str(root), env=env, capture_output=True,
                       text=True, timeout=55)
    if p.returncode != 0:
        log_path = root / "start.log"
        startup_log = log_path.read_text(errors="replace")[-1800:] if log_path.is_file() else "missing"
        raise AssertionError((action, p.stdout[-300:], p.stderr[-500:], startup_log))
    return p


def connect(root: Path):
    c = RuntimeClient(str(root / "runtime.sock"), str(root / "runtime.token"))
    identity = c.connect()
    assert identity["integrity"] == "ok"
    assert identity["ledgerPath"] == str(root / "runtime.db")
    return c, identity


def wait_stopped(root: Path):
    from capt_runtime.cli_ramp import is_running
    for _ in range(100):
        if not (root / "runtime.sock").exists() or not is_running(root / "runtime.sock"):
            return
        time.sleep(0.1)
    raise AssertionError("isolated RuntimeService did not stop")


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS venv proof")
def test_real_authenticated_runtime_directory_cutover():
    old = PRODUCTION_STATE / "runtime-venv"
    candidates = list((PRODUCTION_STATE / "runtime-releases").glob(NEW + "-*"))
    if not old.is_dir() or len(candidates) != 1:
        pytest.skip("verified local source wheel not available")
    candidate_source = candidates[0]
    assert (old / "CAPT_SOURCE_HEAD").read_text().strip() == OLD
    assert (candidate_source / "CAPT_SOURCE_HEAD").read_text().strip() == NEW

    with tempfile.TemporaryDirectory(prefix="capt-isolated-cutover-", dir="/tmp") as td:
        root = Path(td)
        active = root / "runtime-venv"
        candidate = root / "releases" / "candidate"
        shutil.copytree(old, active, symlinks=True)
        shutil.copytree(candidate_source, candidate, symlinks=True)
        before_sha = hashlib.sha256((candidate / "lib/python3.14/site-packages/capt_runtime/checkpoint.py").read_bytes()).hexdigest()

        try:
            run_cli(active, root, "start", seed=True)
            client, identity_before = connect(root)
            try:
                receipt = client.command("checkpoint_runtime", {},
                                         "isolated-release-cp-20261019")
                assert receipt["status"] == "accepted"
                checkpoint = receipt["result"]
                verify_checkpoint(checkpoint)
                assert checkpoint["recoveryState"]["kind"] == "clean"
                baseline_seq = checkpoint["ledgerPosition"]["globalSequence"]
                baseline_digest = checkpoint["ledgerDigest"]
                assert baseline_seq > 0
                assert identity_before["headSequence"] == baseline_seq
                assert identity_before["ledgerChainDigest"] == baseline_digest
                stop = client.command("shutdown", {}, "isolated-release-stop-20261019")
                assert stop["status"] == "accepted"
            finally:
                client.disconnect()
            wait_stopped(root)

            def preflight():
                return {
                    "authenticatedRuntimeService": True, "quiescent": True,
                    "checkpointVerified": True, "runtimeStopped": True,
                    "stateRoot": str(root),
                    "checkpointHeadSequence": baseline_seq,
                    "checkpointChainDigest": baseline_digest,
                }

            def postcheck():
                run_cli(active, root, "start")
                client, ident = connect(root)
                try:
                    newest = client._query({"op": "checkpoints"})["result"]["checkpoints"][0]
                    assert ident["headSequence"] >= baseline_seq
                    assert ident["integrity"] == "ok"
                    # Legitimate startup recovery may append events. Verify
                    # the *original checkpoint's chain prefix* was preserved.
                    cdb = sqlite3.connect(
                        "file:" + str(root / "runtime.db") + "?mode=ro", uri=True
                    )
                    try:
                        pinned = cdb.execute(
                            "select chain_digest from events where global_sequence=?",
                            (baseline_seq,),
                        ).fetchone()
                    finally:
                        cdb.close()
                    assert pinned == (baseline_digest,)
                    assert newest["integrityVerified"] is True
                    assert newest["globalSequence"] == baseline_seq
                    assert newest["recoveryState"] == "clean"
                    assert (active / "CAPT_SOURCE_HEAD").read_text().strip() == NEW
                    after_sha = hashlib.sha256(
                        (active / "lib/python3.14/site-packages/capt_runtime/checkpoint.py").read_bytes()
                    ).hexdigest()
                    assert after_sha == before_sha
                    return {
                        "authenticatedRuntimeService": True,
                        "sourceDigestsVerified": True,
                        "eventStoreContinuityVerified": True,
                        "processHealthy": True, "sourceSha": NEW,
                        "stateRoot": str(root),
                    }
                finally:
                    client.disconnect()

            def stop_failed():
                from capt_runtime.cli_ramp import is_running
                if is_running(root / "runtime.sock"):
                    run_cli(active, root, "stop")
                    wait_stopped(root)
                return True

            backup = SWITCH(
                active, candidate, root / "backups", NEW,
                preflight, postcheck, stop_failed,
            )
            assert (active / "CAPT_SOURCE_HEAD").read_text().strip() == NEW
            assert (backup / "CAPT_SOURCE_HEAD").read_text().strip() == OLD
            assert (root / "runtime.db").exists()
        finally:
            try:
                from capt_runtime.cli_ramp import is_running
                if (root / "runtime.sock").exists() and is_running(root / "runtime.sock"):
                    run_cli(active, root, "stop")
                    wait_stopped(root)
            except (OSError, AssertionError, subprocess.TimeoutExpired):
                pass


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS venv proof")
def test_real_authenticated_recovery_after_switch_process_death():
    """Kill the switch controller mid-rename, restore and authenticate old RuntimeService."""
    old = PRODUCTION_STATE / "runtime-venv"
    choices = list((PRODUCTION_STATE / "runtime-releases").glob(NEW + "-*"))
    if not old.is_dir() or len(choices) != 1:
        pytest.skip("verified local source wheel not available")
    with tempfile.TemporaryDirectory(prefix="capt-isolated-crash-", dir="/tmp") as td:
        root = Path(td)
        active = root / "runtime-venv"
        candidate = root / "releases" / "candidate"
        backups = root / "backups"
        shutil.copytree(old, active, symlinks=True)
        shutil.copytree(choices[0], candidate, symlinks=True)
        try:
            run_cli(active, root, "start", seed=True)
            client, before = connect(root)
            try:
                receipt = client.command("checkpoint_runtime", {},
                                         "isolated-crash-cp-20261019")
                assert receipt["status"] == "accepted"
                ck = receipt["result"]
                verify_checkpoint(ck)
                assert ck["recoveryState"]["kind"] == "clean"
                seq = ck["ledgerPosition"]["globalSequence"]
                digest = ck["ledgerDigest"]
                assert before["headSequence"] == seq
                assert before["ledgerChainDigest"] == digest
                assert client.command(
                    "shutdown", {}, "isolated-crash-stop-20261019"
                )["status"] == "accepted"
            finally:
                client.disconnect()
            wait_stopped(root)

            gate = dict(authenticatedRuntimeService=True, quiescent=True,
                        checkpointVerified=True, runtimeStopped=True,
                        stateRoot=str(root), checkpointHeadSequence=seq,
                        checkpointChainDigest=digest)
            # The child performs real directory moves, then dies before
            # persisting the candidate-activated journal transition.
            child_code = r"""
import os,runpy,sys,json
from pathlib import Path
lib=runpy.run_path(sys.argv[1])
a,c,b=map(Path,sys.argv[2:5])
gate=json.loads(sys.argv[5])
original=os.replace
def crash(src,dst):
    out=original(src,dst)
    if Path(src)==c and Path(dst)==a:os._exit(79)
    return out
os.replace=crash
lib["switch_runtime"](a,c,b,"0fee6655a33cd7d69162a4d8404cd332485d1e29",
                      lambda:gate,lambda:{},lambda:True)
"""
            child = subprocess.run(
                [sys.executable, "-c", child_code, str(SCRIPT), str(active),
                 str(candidate), str(backups), json.dumps(gate)],
                capture_output=True, text=True, timeout=25
            )
            assert child.returncode == 79, child.stderr
            assert (active / "CAPT_SOURCE_HEAD").read_text().strip() == NEW

            def authenticated_restored_old():
                run_cli(active, root, "start")
                client, identity = connect(root)
                try:
                    assert identity["headSequence"] >= seq
                    db = sqlite3.connect(
                        "file:" + str(root / "runtime.db") + "?mode=ro", uri=True
                    )
                    try:
                        pinned = db.execute(
                            "select chain_digest from events where global_sequence=?",
                            (seq,),
                        ).fetchone()
                    finally:
                        db.close()
                    assert pinned == (digest,)
                    assert (active / "CAPT_SOURCE_HEAD").read_text().strip() == OLD
                    return dict(authenticatedRuntimeService=True,
                                sourceDigestsVerified=True,
                                eventStoreContinuityVerified=True,
                                processHealthy=True, sourceSha=OLD,
                                stateRoot=str(root))
                finally:
                    client.disconnect()

            recover = runpy.run_path(str(SCRIPT))["recover_interrupted_switch"]
            result = recover(
                active, candidate, backups, lambda: gate,
                authenticated_restored_old,
            )
            assert result["status"] == "rolled_back"
            assert (active / "CAPT_SOURCE_HEAD").read_text().strip() == OLD
            assert (candidate / "CAPT_SOURCE_HEAD").read_text().strip() == NEW
        finally:
            try:
                from capt_runtime.cli_ramp import is_running
                if (root / "runtime.sock").exists() and is_running(root / "runtime.sock"):
                    run_cli(active, root, "stop")
                    wait_stopped(root)
            except (OSError, AssertionError, subprocess.TimeoutExpired):
                pass
