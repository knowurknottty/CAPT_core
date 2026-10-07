from __future__ import annotations

import subprocess
import sys
import time

import pytest
from pathlib import Path

from capt_runtime.composition import create_runtime
from capt_runtime.tool_broker import tool_request_fingerprint
from desktop.desktop_runtime_client import RuntimeClient

NOW = "2026-08-19T14:30:00Z"


def _stranded_code_request(root: Path) -> dict:
    marker = root / "recovery-must-not-run.txt"
    code = f"from pathlib import Path; Path({str(marker)!r}).write_text('REDISPATCHED')"
    request = {
        "schemaVersion": "1.0.0",
        "toolRequestId": "req-process-restart",
        "toolId": "code.execution",
        "operation": "code.execute_python",
        "arguments": [
            {"kind": "string", "name": "code", "value": code},
            {"kind": "path", "name": "cwd", "value": str(root)},
        ],
        "consequential": True,
        "grantId": "grant-process-restart",
        "leaseId": "lease-process-restart",
        "reservationId": None,
        "backendId": "local",
        "targetIdentity": str(root),
        "filesystemScope": str(root),
        "idempotencyKey": "tool-process-restart",
        "operationFingerprint": "sha256:" + "0" * 64,
        "replayPolicy": "never",
        "requestedAt": NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _persist_dispatch_boundary(ledger: Path, root: Path) -> tuple[str, Path]:
    runtime = create_runtime(str(ledger))
    try:
        request = _stranded_code_request(root)
        execution = runtime.tool_broker.build_execution(
            request, operator_id="operator-process", session_id="session-process"
        )
        execution_id = execution["toolExecutionId"]
        runtime.service.prepare_tool_execution(
            execution, runtime.tool_broker.metadata(execution_id, "prepared")
        )
        runtime.service.transition_tool_execution(
            execution_id,
            "admitted",
            {"reservationId": "reservation-process-restart"},
            runtime.tool_broker.metadata(execution_id, "admitted"),
        )
        runtime.service.transition_tool_execution(
            execution_id,
            "dispatching",
            {"dispatchBoundary": "started"},
            runtime.tool_broker.metadata(execution_id, "dispatching"),
        )
        return execution_id, root / "recovery-must-not-run.txt"
    finally:
        runtime.close()


def test_real_service_restart_reconciles_without_redispatch(tmp_path: Path) -> None:
    ledger = tmp_path / "runtime.db"
    sock = tmp_path / "runtime.sock"
    token_file = tmp_path / "runtime.token"
    token_file.write_text("restart-test-token", encoding="utf-8")
    execution_id, marker = _persist_dispatch_boundary(ledger, tmp_path)
    assert not marker.exists()

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "desktop.capt_runtime_service",
            "--ledger",
            str(ledger),
            "--sock",
            str(sock),
            "--token-file",
            str(token_file),
        ],
        cwd=str(Path(__file__).resolve().parents[2]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    client = RuntimeClient(str(sock), str(token_file), connect_timeout=1.0)
    try:
        deadline = time.monotonic() + 10.0
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate(timeout=1)
                raise AssertionError(
                    f"runtime exited before acceptance: {proc.returncode}\nstdout={out}\nstderr={err}"
                )
            if sock.exists():
                try:
                    client.connect()
                    break
                except Exception as exc:  # socket may exist just before accept is ready
                    last_error = exc
            time.sleep(0.05)
        else:
            raise AssertionError(f"runtime socket never became usable: {last_error}")

        state = client.get_state("tool_execution-" + execution_id)
        assert state["state"] == "indeterminate"
        assert state["settlementStatus"] == "reconciliation_required"
        assert "no proven adapter reconciliation result" in state["reconciliationReason"]
        assert not marker.exists(), "startup recovery redispatched arbitrary Python"

        capabilities = client.capabilities()
        assert "run_tool" in capabilities["commandOperations"]
        assert capabilities["runtimeComponents"]["toolBroker"] is True
        assert capabilities["runtimeComponents"]["toolRegistry"] is True

        shutdown = client.command("shutdown", {}, "shutdown-process-restart")
        assert shutdown["status"] in {"accepted", "idempotent"}
    finally:
        client.disconnect()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
    assert proc.returncode == 0
    assert not marker.exists()


def test_runtime_restart_preserves_unproven_reserved_sandbox_when_docker_is_unavailable(tmp_path: Path) -> None:
    from capt_runtime import commands
    from capt_runtime.contracts import digest

    ledger = tmp_path / "sandbox-restart.db"
    first = create_runtime(str(ledger))
    try:
        lease = {
            "schemaVersion": "1.0.0",
            "sandboxLeaseId": "sandbox-restart-unproven",
            "profileId": "missing-profile",
            "operatorId": "operator-process",
            "sessionId": "session-process",
            "executionContextId": "ctx-process",
            "creationToolExecutionId": "create-process",
            "profileDigest": digest({"profile": "missing"}),
            "imageId": "sha256:" + "a" * 64,
            "securityProfileDigest": digest({"security": "missing"}),
            "networkPolicyDigest": digest({"network": "missing"}),
            "filesystemScopeDigest": digest({"fs": "missing"}),
            "persistentEntrypointDigest": digest({"entry": "missing"}),
            "daemonIdentityDigest": digest({"daemon": "missing"}),
            "dockerEndpoint": "unix:///definitely/missing/capt-docker.sock",
            "createdAt": NOW,
            "expiresAt": "2030-01-01T00:00:00Z",
            "ttlSeconds": 1800,
            "state": "reserved",
        }
        meta = commands.command(
            command_id="sandbox-restart-reserve",
            idempotency_key="sandbox-restart-reserve",
            operation_fingerprint=commands.fingerprint("sandbox-restart-reserve", {"lease": "sandbox-restart-unproven"}),
            correlation_id="corr-sandbox-restart",
            actor_id="exec-process",
            actor_kind="execution_plane",
            issued_at=NOW,
        )
        first.service.reserve_sandbox_lease(lease, meta)
    finally:
        first.close()

    restarted = create_runtime(str(ledger))
    try:
        state = restarted.store.require_state("sandbox_lease-sandbox-restart-unproven")
        assert state["state"] == "reserved"
        assert restarted.sandbox_reconciliation_report
        item = next(
            row for row in restarted.sandbox_reconciliation_report
            if row.get("sandboxLeaseId") == "sandbox-restart-unproven"
        )
        assert item["status"] == "unproven"
    finally:
        restarted.close()


def test_runtime_state_lock_is_exclusive_and_reusable(tmp_path: Path) -> None:
    from desktop.capt_runtime_service import _acquire_runtime_state_lock

    ledger = tmp_path / "runtime.db"
    first = _acquire_runtime_state_lock(str(ledger))
    try:
        with pytest.raises(RuntimeError, match="already owns state lock"):
            _acquire_runtime_state_lock(str(ledger))
    finally:
        first.close()

    second = _acquire_runtime_state_lock(str(ledger))
    second.close()
