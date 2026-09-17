from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from capt_runtime.aggregates import CapabilityAggregate, SandboxLeaseAggregate
from capt_runtime.errors import AuthorityViolation
from capt_runtime.sandbox_reconciliation import SandboxLeaseReconciler
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.tool_broker import ToolBroker, tool_request_fingerprint
from capt_runtime.tools.adapters.inversion_sandbox_lifecycle import (
    InversionSandboxLifecycleToolAdapter,
)
from capt_runtime.tools.adapters.inversion_sandbox_terminal import (
    InversionSandboxTerminalToolAdapter,
)
from capt_runtime.tools.backends.docker import DockerMount, DockerProcessRequest
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxProcessBackend,
    InversionSandboxProfile,
    InversionSandboxProfileRegistry,
)
from capt_runtime.tools.builtins import (
    SANDBOX_INVERSION_DESCRIPTOR,
    TERMINAL_INVERSION_SANDBOX_DESCRIPTOR,
)
from capt_runtime.tools.registry import ToolRegistry
from tests.capt_runtime.test_inversion_sandbox_lifecycle_tool import NOW
from tests.capt_runtime.test_inversion_sandbox_lifecycle_tool import (
    _meta as lifecycle_meta,
)
from tests.capt_runtime.test_inversion_sandbox_lifecycle_tool import (
    _request as lifecycle_request,
)
from tests.capt_runtime.test_inversion_sandbox_lifecycle_tool import (
    _seed_capability as seed_lifecycle,
)
from tests.capt_runtime.test_inversion_sandbox_persistent_exec import (
    _seed_capability as seed_exec,
)

CONTEXT = "desktop-linux"

def _docker() -> str:
    value = shutil.which("docker")
    if not value:
        pytest.skip("Docker CLI unavailable")
    return value


def _image() -> str:
    value = os.environ.get("CAPT_DOCKER_TEST_IMAGE")
    if not value:
        pytest.skip("CAPT_DOCKER_TEST_IMAGE not configured")
    checked = subprocess.run(
        [_docker(), "--context", CONTEXT, "image", "inspect", value],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if checked.returncode != 0:
        pytest.skip("CAPT_DOCKER_TEST_IMAGE is not already local")
    return value


def _profile(tmp_path: Path) -> InversionSandboxProfile:
    work = tmp_path / "work"
    work.mkdir()
    work.chmod(0o777)
    return InversionSandboxProfile(
        profile_id="persistent-life", context_name=CONTEXT, image_ref=_image(),
        allowed_host_roots=(work,), mounts=(DockerMount(work, "/workspace", "rw"),),
        persistent_entrypoint_argv=("/usr/local/bin/python3", "-c", "import time; time.sleep(3600)"),
        default_ttl_seconds=600, max_ttl_seconds=1200,
    )

def _setup(tmp_path: Path):
    store = EventStore(str(tmp_path / "runtime.db"))
    service = RuntimeService(store)
    profile = _profile(tmp_path)
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    lifecycle = InversionSandboxLifecycleToolAdapter(backend, store)
    terminal = InversionSandboxTerminalToolAdapter(
        backend,
        lease_resolver=lambda lease_id: store.load_state(SandboxLeaseAggregate.stream_id(lease_id)),
        now=lambda: NOW,
    )
    registry = ToolRegistry()
    ready = lambda tool_id: lambda: {
        "schemaVersion": "1.0.0", "toolId": tool_id,
        "status": "available", "reason": "real Docker test", "checkedAt": NOW,
    }
    registry.register(SANDBOX_INVERSION_DESCRIPTOR, lifecycle, ready("sandbox.inversion"))
    registry.register(
        TERMINAL_INVERSION_SANDBOX_DESCRIPTOR,
        terminal,
        ready("terminal.inversion_sandbox"),
    )
    broker = ToolBroker(service, registry, now=lambda: NOW)
    return store, service, backend, broker, profile


def _exec_request(profile, grant: str, lease: str, idem: str, argv: list[str], timeout_ms: int = 10_000) -> dict:
    request = {
        "schemaVersion": "1.0.0", "toolRequestId": "req-" + idem,
        "toolId": "terminal.inversion_sandbox", "operation": "terminal.exec",
        "arguments": [
            {"kind": "string", "name": "argv", "value": json.dumps(argv)},
            {"kind": "path", "name": "cwd", "value": "/workspace"},
            {"kind": "integer", "name": "timeout_ms", "value": timeout_ms},
            {"kind": "string", "name": "sandbox_lease_id", "value": "sandbox-life-1"},
        ],
        "consequential": True, "grantId": grant, "leaseId": lease,
        "reservationId": None, "backendId": "inversion_sandbox",
        "targetIdentity": profile.profile_id, "filesystemScope": "/workspace",
        "idempotencyKey": idem, "operationFingerprint": "sha256:" + "0" * 64,
        "replayPolicy": "never", "requestedAt": NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _exists(container_id: str) -> bool:
    return subprocess.run(
        [_docker(), "--context", CONTEXT, "inspect", container_id],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0




def _lease_container_ids(sandbox_lease_id: str) -> list[str]:
    result = subprocess.run(
        [
            _docker(), "--context", CONTEXT, "ps", "-a", "--no-trunc", "--quiet",
            "--filter", f"label=capt.sandboxLeaseId={sandbox_lease_id}",
        ],
        capture_output=True, text=True, timeout=10, check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def _cleanup(container_id: str | None) -> None:
    if container_id and _exists(container_id):
        subprocess.run(
            [_docker(), "--context", CONTEXT, "rm", "-f", container_id],
            capture_output=True, check=False,
        )

def test_real_governed_lifetime_persists_tmpfs_and_preserves_host_mount(tmp_path: Path, monkeypatch) -> None:
    store, service, _backend, broker, profile = _setup(tmp_path)
    container_id = None
    monkeypatch.setenv("CAPT_REAL_PARENT_SECRET", "must-not-leak")
    try:
        create_grant, create_lease = seed_lifecycle(store, service, ["sandbox.create"])
        created = broker.execute(
            lifecycle_request("sandbox.create", create_grant, create_lease, idem="real-create", ttl=900),
            operator_id="operator-1", session_id="session-1",
        )
        assert created["status"] == "succeeded"
        resource = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-life-1"))
        assert resource["state"] == "running"
        container_id = resource["containerId"]
        assert _exists(container_id)

        exec_grant, exec_lease = seed_exec(store, service)
        first = broker.execute(
            _exec_request(
                profile, exec_grant, exec_lease, "real-exec-1",
                ["/usr/local/bin/python3", "-c", "import os; open('/tmp/capt-state','w').write('first'); open('/workspace/host-state','w').write('keep'); print(os.getuid(), os.environ.get('CAPT_REAL_PARENT_SECRET','unset'))"],
            ),
            operator_id="operator-1", session_id="session-1",
        )
        assert first["status"] == "succeeded"
        stdout = next(item["value"] for item in first["result"]["output"] if item["name"] == "stdout")
        assert stdout.strip() == "65532 unset"
        second = broker.execute(
            _exec_request(
                profile, exec_grant, exec_lease, "real-exec-2",
                ["/usr/local/bin/python3", "-c", "from pathlib import Path; print(Path('/tmp/capt-state').read_text()); p=Path('/workspace/host-state'); p.write_text(p.read_text()+'-more')"],
            ),
            operator_id="operator-1", session_id="session-1",
        )
        assert second["status"] == "succeeded"
        stdout = next(item["value"] for item in second["result"]["output"] if item["name"] == "stdout")
        assert stdout.strip() == "first"
        assert (tmp_path / "work" / "host-state").read_text() == "keep-more"
        assert first["toolExecutionId"] != second["toolExecutionId"]
        capability = store.require_state(CapabilityAggregate.stream_id(exec_grant))
        assert capability["usesConsumed"] == 2
        assert len(capability["consumptions"]) == 2

        with pytest.raises(AuthorityViolation, match="OWNER"):
            broker.execute(
                _exec_request(profile, exec_grant, exec_lease, "real-wrong-owner", ["/bin/true"]),
                operator_id="operator-2", session_id="session-1",
            )

        widened = _exec_request(profile, exec_grant, exec_lease, "real-widen", ["/bin/true"])
        widened["arguments"].append({"kind": "string", "name": "network_mode", "value": "host"})
        widened["operationFingerprint"] = tool_request_fingerprint(widened)
        with pytest.raises(ValueError, match="unknown argument"):
            broker.execute(widened, operator_id="operator-1", session_id="session-1")
        close_grant, close_lease = seed_lifecycle(store, service, ["sandbox.close"])
        closed = broker.execute(
            lifecycle_request("sandbox.close", close_grant, close_lease, idem="real-close"),
            operator_id="operator-1", session_id="session-1",
        )
        assert closed["status"] == "succeeded"
        assert store.require_state(SandboxLeaseAggregate.stream_id("sandbox-life-1"))["state"] == "closed"
        assert not _exists(container_id)
        assert _lease_container_ids("sandbox-life-1") == []
        assert (tmp_path / "work" / "host-state").read_text() == "keep-more"
    finally:
        _cleanup(container_id)
        store.close()


def test_real_timeout_quarantines_and_requires_explicit_close(tmp_path: Path) -> None:
    store, service, _backend, broker, profile = _setup(tmp_path)
    container_id = None
    try:
        create_grant, create_lease = seed_lifecycle(store, service, ["sandbox.create"])
        created = broker.execute(
            lifecycle_request("sandbox.create", create_grant, create_lease, idem="real-timeout-create"),
            operator_id="operator-1", session_id="session-1",
        )
        assert created["status"] == "succeeded"
        resource = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-life-1"))
        container_id = resource["containerId"]

        exec_grant, exec_lease = seed_exec(store, service)
        timed = broker.execute(
            _exec_request(
                profile, exec_grant, exec_lease, "real-timeout",
                ["/usr/local/bin/python3", "-c", "import time; time.sleep(30)"], timeout_ms=100,
            ),
            operator_id="operator-1", session_id="session-1",
        )
        assert timed["status"] == "indeterminate"
        quarantined = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-life-1"))
        assert quarantined["state"] == "indeterminate"
        assert quarantined["reconciliationReason"] == "exec_termination_unknown"

        from capt_runtime.sandbox_reconciliation import SandboxLeaseReconciler
        reconciler = SandboxLeaseReconciler(service, broker.registry.adapter("sandbox.inversion").backend, now=lambda: NOW)
        report = reconciler.reconcile_one("sandbox-life-1")
        assert report["status"] == "close_required"

        close_grant, close_lease = seed_lifecycle(store, service, ["sandbox.close"])
        closed = broker.execute(
            lifecycle_request("sandbox.close", close_grant, close_lease, idem="real-timeout-close"),
            operator_id="operator-1", session_id="session-1",
        )
        assert closed["status"] == "succeeded"
        assert not _exists(container_id)
        assert _lease_container_ids("sandbox-life-1") == []
    finally:
        _cleanup(container_id)
        store.close()


def test_real_reserved_create_crash_is_rediscovered_by_known_lease_label(tmp_path: Path) -> None:
    store, service, backend, _broker, profile = _setup(tmp_path)
    identity = None
    try:
        process = DockerProcessRequest(
            profile_id=profile.profile_id, argv=profile.persistent_entrypoint_argv or (),
            cwd="/workspace", filesystem_root="/workspace", timeout_seconds=10,
            stdout_limit_bytes=4096, stderr_limit_bytes=4096,
        )
        prepared = backend.preflight(process)
        record = {
            "schemaVersion": "1.0.0", "sandboxLeaseId": "sandbox-crash-real",
            "profileId": profile.profile_id, "operatorId": "operator-1", "sessionId": "session-1",
            "executionContextId": "ctx-crash-real", "creationToolExecutionId": "create-crash-real",
            "profileDigest": profile.profile_digest(), "imageId": prepared.docker.image_id,
            "securityProfileDigest": "sha256:" + profile.security_profile_digest(),
            "networkPolicyDigest": "sha256:" + profile.network_policy.digest(),
            "filesystemScopeDigest": "sha256:" + profile.filesystem_scope_digest(),
            "persistentEntrypointDigest": profile.persistent_entrypoint_digest(),
            "daemonIdentityDigest": backend._daemon_identity_digest(prepared.docker.context_endpoint),
            "dockerEndpoint": prepared.docker.context_endpoint, "createdAt": NOW,
            "expiresAt": "2026-09-09T12:20:00Z", "ttlSeconds": 1200, "state": "reserved",
        }
        service.reserve_sandbox_lease(record, lifecycle_meta("reserve-real-crash", "execution_plane"))
        identity = backend.create_persistent_stopped("sandbox-crash-real", process, prepared=prepared)
        assert _exists(identity.workload_container_id)
        reconciler = SandboxLeaseReconciler(service, backend, now=lambda: NOW)
        result = reconciler.reconcile_one("sandbox-crash-real")
        assert result["status"] == "recovered_created"
        durable = store.require_state(SandboxLeaseAggregate.stream_id("sandbox-crash-real"))
        assert durable["state"] == "created"
        assert durable["containerId"] == identity.workload_container_id
    finally:
        if identity is not None:
            _cleanup(identity.workload_container_id)
        store.close()
