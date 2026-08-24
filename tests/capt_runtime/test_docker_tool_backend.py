from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from capt_runtime import commands, contracts
from capt_runtime.composition import create_runtime
from capt_runtime.tool_broker import tool_request_fingerprint
from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.docker import (
    DockerMount,
    DockerNetworkPolicy,
    DockerProcessBackend,
    DockerProcessRequest,
    DockerProfile,
    DockerProfileRegistry,
    docker_context_endpoint,
)


def _docker_cli() -> str:
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker CLI unavailable")
    return docker


def _test_image() -> str:
    image = os.environ.get("CAPT_DOCKER_TEST_IMAGE")
    if not image:
        pytest.skip("CAPT_DOCKER_TEST_IMAGE not configured for real daemon acceptance")
    return image


def _daemon_available(context: str = "desktop-linux") -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    completed = subprocess.run(
        [docker, "--context", context, "info", "--format", "{{.ServerVersion}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
        check=False,
    )
    return completed.returncode == 0


def _profile(tmp_path: Path, *, image: str | None = None, mounts=(), network_mode="none") -> DockerProfile:
    work = tmp_path / "host-work"
    work.mkdir(exist_ok=True)
    return DockerProfile(
        profile_id="docker-local-test",
        context_name="desktop-linux",
        image_ref=image or "capt-test-image:missing",
        allowed_host_roots=(work,),
        mounts=tuple(mounts),
        allowed_container_roots=("/workspace",),
        working_dir="/workspace",
        environment_overrides=(("CAPT_PROFILE_ENV", "governed"),),
        cpus=1.0,
        memory_bytes=256 * 1024 * 1024,
        pids_limit=128,
        network_policy=DockerNetworkPolicy(
            mode=network_mode,
            unrestricted_egress=(network_mode == "bridge"),
        ),
        cleanup_policy="always",
        read_only_rootfs=False,
    )


def test_local_unix_context_is_discovered_without_daemon_dependency(tmp_path: Path) -> None:
    docker = _docker_cli()
    context_name = f"capt-unix-context-{os.getpid()}"
    socket_path = tmp_path / "docker.sock"
    try:
        subprocess.run(
            [docker, "context", "create", context_name, "--docker", f"host=unix://{socket_path}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=True,
        )
        endpoint = docker_context_endpoint(context_name)
        assert endpoint == f"unix://{socket_path}"
    finally:
        subprocess.run(
            [docker, "context", "rm", "-f", context_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )


def test_mounts_are_canonical_scoped_and_docker_socket_passthrough_is_denied(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    child = root / "child"
    child.mkdir()
    mount = DockerMount(host_path=child, container_path="/workspace/data", mode="rw")
    profile = DockerProfile(
        profile_id="docker-mount-test",
        context_name="desktop-linux",
        image_ref="example.invalid/image:test",
        allowed_host_roots=(root,),
        mounts=(mount,),
        allowed_container_roots=("/workspace",),
        working_dir="/workspace",
        network_policy=DockerNetworkPolicy(mode="none"),
    )
    assert profile.mounts[0].host_path == child.resolve()

    with pytest.raises(AuthorityViolation, match="Docker socket"):
        DockerMount(
            host_path=Path("/var/run/docker.sock"),
            container_path="/var/run/docker.sock",
            mode="rw",
        )

    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(AuthorityViolation, match="allowed host roots"):
        DockerProfile(
            profile_id="docker-mount-escape",
            context_name="desktop-linux",
            image_ref="example.invalid/image:test",
            allowed_host_roots=(root,),
            mounts=(DockerMount(outside, "/workspace/outside", "ro"),),
            allowed_container_roots=("/workspace",),
            working_dir="/workspace",
            network_policy=DockerNetworkPolicy(mode="none"),
        )


def test_network_policy_is_fail_closed_and_host_mode_is_not_supported() -> None:
    assert DockerNetworkPolicy(mode="none").unrestricted_egress is False
    with pytest.raises(ValueError, match="bridge requires explicitly unrestricted egress"):
        DockerNetworkPolicy(mode="bridge", unrestricted_egress=False)
    with pytest.raises(ValueError, match="network mode"):
        DockerNetworkPolicy(mode="host", unrestricted_egress=True)


def test_profile_requires_bounded_resources_and_always_cleanup(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(ValueError, match="cleanup_policy"):
        DockerProfile(
            profile_id="docker-bad-cleanup",
            context_name="desktop-linux",
            image_ref="image:test",
            allowed_host_roots=(work,),
            allowed_container_roots=("/workspace",),
            working_dir="/workspace",
            network_policy=DockerNetworkPolicy(mode="none"),
            cleanup_policy="preserve",
        )
    with pytest.raises(ValueError, match="memory_bytes"):
        DockerProfile(
            profile_id="docker-bad-memory",
            context_name="desktop-linux",
            image_ref="image:test",
            allowed_host_roots=(work,),
            allowed_container_roots=("/workspace",),
            working_dir="/workspace",
            network_policy=DockerNetworkPolicy(mode="none"),
            memory_bytes=1,
        )


def test_runtime_registers_docker_but_default_readiness_is_truthfully_unavailable(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "runtime.db"))
    try:
        descriptor = runtime.tool_registry.require("terminal.docker")["descriptor"]
        assert descriptor["operationEffects"] == [
            {"operation": "terminal.exec", "effectClass": "durable_local"}
        ]
        assert descriptor["terminalBackends"] == ["docker"]
        assert descriptor["supportsCancellation"] is False
        readiness = runtime.tool_registry.readiness("terminal.docker")
        assert readiness["status"] == "unavailable"
        assert "no named Docker profiles" in readiness["reason"]
    finally:
        runtime.close()


@pytest.mark.skipif(not _daemon_available(), reason="real Docker daemon unavailable")
def test_real_docker_create_observes_identity_before_start_and_cleans_up(tmp_path: Path) -> None:
    image = _test_image()
    work = tmp_path / "host-work"
    work.mkdir()
    mount = DockerMount(work, "/workspace", "rw")
    profile = _profile(tmp_path, image=image, mounts=(mount,))
    backend = DockerProcessBackend(DockerProfileRegistry([profile]))
    observed: list[str] = []
    docker = _docker_cli()

    def observe(identity_json: str) -> None:
        identity = json.loads(identity_json)
        inspected = subprocess.run(
            [docker, "--context", profile.context_name, "inspect", identity["containerId"]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        record = json.loads(inspected.stdout)[0]
        assert record["State"]["Status"] == "created"
        assert record["Image"] == identity["imageId"]
        assert record["HostConfig"]["NetworkMode"] == "none"
        assert record["HostConfig"]["Memory"] == profile.memory_bytes
        assert record["HostConfig"]["PidsLimit"] == profile.pids_limit
        assert any(mount["Destination"] == "/workspace" and mount["RW"] for mount in record["Mounts"])
        observed.append(identity_json)

    request = DockerProcessRequest(
        profile_id=profile.profile_id,
        argv=("/bin/sh", "-c", "printf 'DOCKER_OK\\n'; printf x > /workspace/marker.txt"),
        cwd="/workspace",
        filesystem_root="/workspace",
        timeout_seconds=10,
        stdout_limit_bytes=4096,
        stderr_limit_bytes=4096,
    )
    prepared = backend.preflight(request)
    result = backend.execute(request, prepared=prepared, observe_effect=observe)

    assert len(observed) == 1
    identity = json.loads(observed[0])
    assert identity["containerId"] == result.container_id
    assert identity["imageId"] == prepared.image_id
    assert identity["profileId"] == profile.profile_id
    assert result.exit_code == 0
    assert result.stdout == "DOCKER_OK\n"
    assert result.stderr == ""
    assert result.cleanup_succeeded is True
    assert (work / "marker.txt").read_text() == "x"
    inspect = subprocess.run(
        [docker, "--context", profile.context_name, "inspect", result.container_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    assert inspect.returncode != 0, "cleanup_policy=always left the container behind"


@pytest.mark.skipif(not _daemon_available(), reason="real Docker daemon unavailable")
def test_real_docker_timeout_stops_and_cleans_container(tmp_path: Path) -> None:
    image = _test_image()
    work = tmp_path / "host-work"
    work.mkdir()
    profile = _profile(tmp_path, image=image, mounts=(DockerMount(work, "/workspace", "rw"),))
    backend = DockerProcessBackend(DockerProfileRegistry([profile]))
    observed: list[str] = []
    request = DockerProcessRequest(
        profile_id=profile.profile_id,
        argv=("/bin/sh", "-c", "sleep 30"),
        cwd="/workspace",
        filesystem_root="/workspace",
        timeout_seconds=0.2,
        stdout_limit_bytes=4096,
        stderr_limit_bytes=4096,
    )
    result = backend.execute(request, prepared=backend.preflight(request), observe_effect=observed.append)
    assert result.timed_out is True
    assert result.cleanup_succeeded is True
    assert len(observed) == 1


@pytest.mark.skipif(not _daemon_available(), reason="real Docker daemon unavailable")
def test_real_docker_argv_is_literal_and_parent_secret_is_not_inherited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = _test_image()
    work = tmp_path / "host-work"
    work.mkdir()
    profile = _profile(tmp_path, image=image, mounts=(DockerMount(work, "/workspace", "rw"),))
    backend = DockerProcessBackend(DockerProfileRegistry([profile]))
    monkeypatch.setenv("CAPT_DOCKER_PARENT_SECRET", "must-not-leak")
    marker = work / "shell-must-not-run"
    literal = f"$(touch /workspace/{marker.name})"
    request = DockerProcessRequest(
        profile_id=profile.profile_id,
        argv=("/bin/echo", literal),
        cwd="/workspace",
        filesystem_root="/workspace",
        timeout_seconds=10,
        stdout_limit_bytes=4096,
        stderr_limit_bytes=4096,
    )
    result = backend.execute(
        request,
        prepared=backend.preflight(request),
        observe_effect=lambda _identity: None,
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == literal
    assert not marker.exists()

    secret_request = DockerProcessRequest(
        profile_id=profile.profile_id,
        argv=("/bin/sh", "-c", "printf '%s' \"${CAPT_DOCKER_PARENT_SECRET-unset}\""),
        cwd="/workspace",
        filesystem_root="/workspace",
        timeout_seconds=10,
        stdout_limit_bytes=4096,
        stderr_limit_bytes=4096,
    )
    secret_result = backend.execute(
        secret_request,
        prepared=backend.preflight(secret_request),
        observe_effect=lambda _identity: None,
    )
    assert secret_result.exit_code == 0
    assert secret_result.stdout == "unset"


RUNTIME_NOW = "2026-08-19T17:00:00Z"


def _runtime_meta(step: str, kind: str, actor: str) -> dict:
    return commands.command(
        command_id=f"cmd-docker-{step}",
        idempotency_key=f"idem-docker-{step}",
        operation_fingerprint=commands.fingerprint("docker-" + step, {"step": step}),
        correlation_id="corr-docker-runtime",
        actor_id=actor,
        actor_kind=kind,
        issued_at=RUNTIME_NOW,
        replay_policy="never",
    )


def _seed_docker_authority(runtime, *, suffix: str, max_uses: int = 1) -> tuple[str, str]:
    mission = f"m-docker-{suffix}"
    task = f"t-docker-{suffix}"
    policy = f"pd-docker-{suffix}"
    grant = f"g-docker-{suffix}"
    lease = f"l-docker-{suffix}"
    scope = {"kind": "filesystem", "rootPath": "/workspace", "recursive": True}
    policy_digest = contracts.digest({"policy": "docker-runtime", "suffix": suffix})
    runtime.service.create_mission(
        {
            "schemaVersion": "1.0.0",
            "missionId": mission,
            "rawRequest": "governed Docker acceptance",
            "normalizedRequest": "governed Docker acceptance",
            "objectives": [{"objectiveId": "obj-docker", "statement": "run governed Docker", "priority": 1}],
            "constraints": [{
                "kind": "resource_boundary",
                "constraintId": "con-docker",
                "origin": "explicit_user",
                "scope": scope,
            }],
            "successCriteria": [{
                "criterionId": "sc-docker", "statement": "container result recorded", "requiresVerification": True
            }],
            "terminationCriteria": [{
                "criterionId": "tc-docker", "statement": "authority failure", "terminalState": "failed"
            }],
            "unresolvedAmbiguities": [],
            "taskGraphId": None,
            "createdAt": RUNTIME_NOW,
        },
        _runtime_meta("mission-" + suffix, "human", "operator-docker"),
    )
    runtime.service.evaluate_policy(
        {
            "schemaVersion": "1.0.0",
            "policyDecisionId": policy,
            "policyBundleDigest": policy_digest,
            "effect": "allow",
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "missionId": mission,
            "taskId": task,
            "requestedOperations": ["terminal.exec"],
            "requestedScope": scope,
            "conditions": [],
            "rationale": "bounded local Docker profile acceptance",
            "decidedBy": {"actorId": "gk-docker", "kind": "governance_kernel"},
            "decidedAt": RUNTIME_NOW,
        },
        _runtime_meta("policy-" + suffix, "governance_kernel", "gk-docker"),
    )
    runtime.service.issue_grant(
        {
            "schemaVersion": "1.0.0",
            "grantId": grant,
            "subject": {"actorId": "tool-broker", "kind": "execution_plane"},
            "capabilityId": "cap.terminal.exec.docker",
            "operations": ["terminal.exec"],
            "scope": scope,
            "policyDecisionId": policy,
            "policyBundleDigest": policy_digest,
            "conditions": [],
            "maxUses": max_uses,
            "validFrom": "2026-08-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "issuedBy": {"actorId": "gk-docker", "kind": "governance_kernel"},
            "issuedAt": RUNTIME_NOW,
        },
        _runtime_meta("grant-" + suffix, "governance_kernel", "gk-docker"),
    )
    runtime.service.activate_lease(
        {
            "schemaVersion": "1.0.0",
            "leaseId": lease,
            "grantId": grant,
            "missionId": mission,
            "taskId": task,
            "executionContextId": "ec-docker-" + suffix,
            "operations": ["terminal.exec"],
            "scope": scope,
            "maxUses": max_uses,
            "validFrom": "2026-08-01T00:00:00Z",
            "validUntil": "2030-01-01T00:00:00Z",
            "activatedAt": RUNTIME_NOW,
        },
        _runtime_meta("lease-" + suffix, "governance_kernel", "gk-docker"),
    )
    return grant, lease


def _governed_docker_request(
    profile: DockerProfile,
    argv: list[str],
    grant: str,
    lease: str,
    *,
    idem: str,
) -> dict:
    request = {
        "schemaVersion": "1.0.0",
        "toolRequestId": "req-" + idem,
        "toolId": "terminal.docker",
        "operation": "terminal.exec",
        "arguments": [
            {"kind": "string", "name": "argv", "value": json.dumps(argv)},
            {"kind": "path", "name": "cwd", "value": "/workspace"},
        ],
        "consequential": True,
        "grantId": grant,
        "leaseId": lease,
        "reservationId": None,
        "backendId": "docker",
        "targetIdentity": profile.profile_id,
        "filesystemScope": "/workspace",
        "idempotencyKey": idem,
        "operationFingerprint": "sha256:" + "0" * 64,
        "replayPolicy": "never",
        "requestedAt": RUNTIME_NOW,
    }
    request["operationFingerprint"] = tool_request_fingerprint(request)
    return request


def _docker_envelope(request: dict, *, command_id: str = "cmd-run-docker") -> dict:
    return {
        "commandId": command_id,
        "operatorId": "operator-docker",
        "sessionId": "sess-docker",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-run-docker",
        "idempotencyKey": request["idempotencyKey"],
        "timestamp": RUNTIME_NOW,
        "op": "run_tool",
        "payload": request,
    }


@pytest.mark.skipif(not _daemon_available(), reason="real Docker daemon unavailable")
def test_authenticated_runtime_executes_real_docker_and_replays_without_second_effect(tmp_path: Path) -> None:
    image = _test_image()
    work = tmp_path / "host-work"
    work.mkdir()
    profile = _profile(
        tmp_path,
        image=image,
        mounts=(DockerMount(work, "/workspace", "rw"),),
    )
    runtime = create_runtime(str(tmp_path / "runtime.db"), docker_profiles=[profile])
    try:
        assert runtime.tool_registry.readiness("terminal.docker")["status"] == "available"
        grant, lease = _seed_docker_authority(runtime, suffix="exec", max_uses=1)
        code = "printf x >> /workspace/runtime-count.txt"
        request = _governed_docker_request(
            profile,
            ["/bin/sh", "-c", code],
            grant,
            lease,
            idem="docker-runtime-exec",
        )
        relay = runtime.command_service("operator-docker", "sess-docker")
        first = relay.execute(_docker_envelope(request, command_id="cmd-docker-first"))
        second = relay.execute(_docker_envelope(request, command_id="cmd-docker-first"))

        assert first["status"] == "accepted"
        assert first["result"]["status"] == "succeeded"
        assert second["status"] == "idempotent"
        assert second["result"]["replayed"] is True
        assert (work / "runtime-count.txt").read_text() == "x"
        execution = runtime.store.require_state(
            "tool_execution-" + first["result"]["toolExecutionId"]
        )
        assert execution["effectClass"] == "durable_local"
        identity = json.loads(execution["sideEffectIdentity"])
        assert identity["profileId"] == profile.profile_id
        assert identity["imageId"].startswith("sha256:")
        assert len(identity["containerId"]) == 64
        capability = runtime.store.require_state("capability-" + grant)
        assert capability["usesConsumed"] == 1
        assert len(capability["consumptions"]) == 1
        docker = _docker_cli()
        removed = subprocess.run(
            [docker, "--context", profile.context_name, "inspect", identity["containerId"]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        assert removed.returncode != 0
    finally:
        runtime.close()


@pytest.mark.skipif(not _daemon_available(), reason="real Docker daemon unavailable")
def test_runtime_docker_missing_image_preflight_consumes_no_capability_use(tmp_path: Path) -> None:
    profile = _profile(tmp_path, image="capt/definitely-missing-release-image:never")
    runtime = create_runtime(str(tmp_path / "runtime.db"), docker_profiles=[profile])
    try:
        assert runtime.tool_registry.readiness("terminal.docker")["status"] == "available"
        grant, lease = _seed_docker_authority(runtime, suffix="deny", max_uses=1)
        request = _governed_docker_request(
            profile,
            ["/bin/echo", "must-not-run"],
            grant,
            lease,
            idem="docker-runtime-deny",
        )
        receipt = runtime.command_service("operator-docker", "sess-docker").execute(
            _docker_envelope(request)
        )
        assert receipt["status"] == "accepted"
        assert receipt["result"]["status"] == "denied"
        execution = runtime.store.require_state(
            "tool_execution-" + receipt["result"]["toolExecutionId"]
        )
        assert execution["state"] == "failed"
        assert execution["dispatchBoundary"] == "not_started"
        assert execution["reservationId"] is None
        capability = runtime.store.require_state("capability-" + grant)
        assert capability["usesConsumed"] == 0
        assert capability["reservations"] == []
        assert capability["consumptions"] == []
    finally:
        runtime.close()
