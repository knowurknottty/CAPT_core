from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.inversion_guardian import (
    GuardianProtocolError,
    destination_allowed,
    parse_request_head,
    policy_digest,
)
from capt_runtime.tools.backends.inversion_sandbox import (
    DEFAULT_PLATFORM_DENY,
    InversionSandboxNetworkPolicy,
    InversionSandboxProfile,
)


def _policy(*allow: str, deny: tuple[str, ...] = DEFAULT_PLATFORM_DENY) -> dict[str, object]:
    return InversionSandboxNetworkPolicy(
        mode="allowlist", allow=allow, platform_deny=deny
    ).canonical()


def test_destination_allowlist_supports_exact_wildcard_and_cidr() -> None:
    assert destination_allowed(_policy("example.com"), "example.com", ["203.0.113.10"])
    assert destination_allowed(_policy("*.example.com"), "api.example.com", ["203.0.113.10"])
    assert not destination_allowed(_policy("*.example.com"), "example.com", ["203.0.113.10"])
    assert destination_allowed(_policy("203.0.113.0/24"), "203.0.113.8", ["203.0.113.8"])


def test_platform_deny_precedes_domain_allow_and_blocks_dns_rebinding() -> None:
    policy = _policy("example.com")
    assert not destination_allowed(policy, "example.com", ["127.0.0.1"])
    assert not destination_allowed(policy, "example.com", ["93.184.216.34", "169.254.169.254"])
    assert not destination_allowed(policy, "example.com", ["10.1.2.3"])
    assert not destination_allowed(policy, "example.com", ["192.168.1.20"])


def test_unrestricted_still_honors_platform_deny() -> None:
    policy = InversionSandboxNetworkPolicy(mode="unrestricted").canonical()
    assert destination_allowed(policy, "example.com", ["93.184.216.34"])
    assert not destination_allowed(policy, "metadata.internal", ["169.254.169.254"])


def test_policy_digest_matches_canonical_profile_policy() -> None:
    network = InversionSandboxNetworkPolicy(
        mode="allowlist", allow=("example.com", "*.openai.com")
    )
    assert policy_digest(network.canonical()) == network.digest()
    encoded = base64.b64encode(
        json.dumps(network.canonical(), sort_keys=True, separators=(",", ":")).encode()
    ).decode()
    assert encoded


def test_proxy_request_parser_accepts_connect_and_absolute_http() -> None:
    connect = parse_request_head(
        b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n"
    )
    assert connect.method == "CONNECT"
    assert connect.host == "example.com"
    assert connect.port == 443
    http = parse_request_head(
        b"GET http://example.com:8080/a?q=1 HTTP/1.1\r\nHost: example.com:8080\r\n\r\n"
    )
    assert http.method == "GET"
    assert http.host == "example.com"
    assert http.port == 8080
    assert http.forward_target == "/a?q=1"


def test_proxy_request_parser_rejects_malformed_or_oversized_heads() -> None:
    with pytest.raises(GuardianProtocolError):
        parse_request_head(b"CONNECT example.com HTTP/1.1\r\n\r\n")
    with pytest.raises(GuardianProtocolError):
        parse_request_head(b"GET /relative HTTP/1.1\r\nHost: example.com\r\n\r\n")
    with pytest.raises(GuardianProtocolError):
        parse_request_head(b"GET ftp://example.com/x HTTP/1.1\r\n\r\n")
    with pytest.raises(GuardianProtocolError):
        parse_request_head(b"GET http://example.com/ HTTP/1.1\r\nX-A: " + b"x" * 65536 + b"\r\n\r\n")


def test_allowlist_profile_requires_explicit_guardian_image(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(AuthorityViolation, match="guardian image"):
        InversionSandboxProfile(
            profile_id="allowlist-no-guardian",
            context_name="desktop-linux",
            image_ref="example.invalid/workload:test",
            allowed_host_roots=(work,),
            network_policy=InversionSandboxNetworkPolicy(
                mode="allowlist", allow=("example.com",)
            ),
        )


def test_guardian_image_is_not_required_for_no_network_profile(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    profile = InversionSandboxProfile(
        profile_id="none-no-guardian",
        context_name="desktop-linux",
        image_ref="example.invalid/workload:test",
        allowed_host_roots=(work,),
    )
    assert profile.guardian_image_ref is None


def _allowlist_profile(tmp_path: Path) -> InversionSandboxProfile:
    work = tmp_path / "allow-work"
    work.mkdir(exist_ok=True)
    return InversionSandboxProfile(
        profile_id="allowlist-runtime",
        context_name="desktop-linux",
        image_ref="example.invalid/workload:test",
        guardian_image_ref="example.invalid/guardian:test",
        allowed_host_roots=(work,),
        network_policy=InversionSandboxNetworkPolicy(
            mode="allowlist", allow=("example.com",)
        ),
    )


def test_allowlist_workload_profile_injects_guardian_proxy_without_bridge(tmp_path: Path) -> None:
    profile = _allowlist_profile(tmp_path)
    docker = profile.docker_profile()
    assert docker.network_policy.mode == "none"
    env = dict(docker.environment_overrides)
    proxy = "http://capt-guardian:18080"
    assert env["HTTP_PROXY"] == proxy
    assert env["HTTPS_PROXY"] == proxy
    assert env["http_proxy"] == proxy
    assert env["https_proxy"] == proxy
    assert "ALL_PROXY" not in env


def test_docker_private_network_override_is_narrow_and_prefix_bound(tmp_path: Path) -> None:
    import capt_runtime.tools.backends.docker as docker_backend

    profile = _allowlist_profile(tmp_path).docker_profile()
    prepared = docker_backend.DockerPreparedTarget(
        profile, "unix:///tmp/docker.sock", "sha256:" + "a" * 64, None
    )
    args = docker_backend._docker_create_args(
        profile,
        prepared,
        "/workspace",
        ("/bin/true",),
        network_mode_override="capt_inv_0123456789ab",
    )
    network_index = args.index("--network")
    assert args[network_index + 1] == "capt_inv_0123456789ab"
    with pytest.raises(AuthorityViolation, match="internal network override"):
        docker_backend._docker_create_args(
            profile,
            prepared,
            "/workspace",
            ("/bin/true",),
            network_mode_override="bridge",
        )


def _command_result(stdout: str = "", stderr: str = "", exit_code: int = 0, timed_out: bool = False):
    from types import SimpleNamespace

    return SimpleNamespace(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=timed_out,
        stdout_total_bytes=len(stdout.encode()),
        stderr_total_bytes=len(stderr.encode()),
        stdout_truncated=False,
        stderr_truncated=False,
    )


def _docker_result(profile, container_id: str):
    from capt_runtime.tools.backends.docker import DockerProcessResult

    return DockerProcessResult(
        exit_code=0,
        stdout="ok\n",
        stderr="",
        stdout_total_bytes=3,
        stderr_total_bytes=0,
        stdout_truncated=False,
        stderr_truncated=False,
        timed_out=False,
        profile_id=profile.profile_id,
        image_id="sha256:" + "a" * 64,
        repo_digest=None,
        container_id=container_id,
        container_cwd="/workspace",
        cleanup_succeeded=True,
    )


def test_allowlist_orchestration_observes_before_guardian_start_and_workload_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import capt_runtime.tools.backends.inversion_sandbox as sandbox_mod
    from capt_runtime.tools.backends.docker import (
        DockerPreparedTarget,
        DockerProcessRequest,
    )

    profile = _allowlist_profile(tmp_path)
    backend = sandbox_mod.InversionSandboxProcessBackend(
        sandbox_mod.InversionSandboxProfileRegistry((profile,))
    )
    workload_id = "1" * 64
    guardian_id = "2" * 64
    guardian_image_id = "sha256:" + "3" * 64
    prepared = sandbox_mod.InversionSandboxPreparedTarget(
        profile,
        DockerPreparedTarget(profile.docker_profile(), "unix:///tmp/docker.sock", "sha256:" + "a" * 64, None),
    )
    events: list[str] = []
    network_name_box: list[str] = []

    def run_endpoint(_endpoint, args, **_kwargs):
        args = tuple(args)
        if args[:2] == ("image", "inspect"):
            return _command_result(json.dumps([{"Id": guardian_image_id, "RepoDigests": []}]))
        if args[:3] == ("network", "create", "--internal"):
            network_name_box.append(args[-1])
            events.append("network-created")
            return _command_result("4" * 64 + "\n")
        if args and args[0] == "create":
            events.append("guardian-created")
            return _command_result(guardian_id + "\n")
        if args[:2] == ("network", "connect"):
            events.append("guardian-connected")
            return _command_result()
        if args[:2] == ("inspect", guardian_id):
            return _command_result(json.dumps([{"Id": guardian_id, "Image": guardian_image_id, "State": {"Status": "created"}, "Config": {"User": f"{profile.uid}:{profile.gid}"}, "HostConfig": {"ReadonlyRootfs": True, "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true"], "Privileged": False, "Devices": [], "NetworkMode": "bridge"}}]))
        if args[:2] == ("inspect", workload_id):
            record = _created_record(profile, prepared.docker.image_id, workload_id)
            record["HostConfig"]["NetworkMode"] = network_name_box[0]
            record["NetworkSettings"]["Networks"] = {network_name_box[0]: {}}
            return _command_result(json.dumps([record]))
        if args[:2] == ("start", guardian_id):
            events.append("guardian-start")
            return _command_result()
        if args[:2] == ("logs", guardian_id):
            events.append("guardian-ready")
            return _command_result(f"CAPT_GUARDIAN_READY {profile.network_policy.digest()}\n")
        if args[:3] == ("rm", "-f", guardian_id):
            events.append("guardian-removed")
            return _command_result()
        if args[:2] == ("network", "rm"):
            events.append("network-removed")
            return _command_result()
        raise AssertionError(f"unexpected docker control command: {args}")

    monkeypatch.setattr(backend.docker_backend, "_run_endpoint", run_endpoint)

    def execute_workload(request, *, prepared, observe_effect, network_mode_override=None):
        assert network_mode_override == network_name_box[0]
        base_identity = json.dumps({
            "backend": "docker", "profileId": profile.profile_id,
            "contextEndpoint": prepared.context_endpoint, "containerId": workload_id,
            "imageId": prepared.image_id, "repoDigest": None, "containerCwd": "/workspace",
        }, sort_keys=True, separators=(",", ":"))
        observe_effect(base_identity)
        events.append("workload-start")
        return _docker_result(profile, workload_id)

    monkeypatch.setattr(backend.docker_backend, "execute", execute_workload)
    observed: list[str] = []
    request = DockerProcessRequest(profile.profile_id, ("/bin/true",), "/workspace", "/workspace")
    result = backend.execute(request, prepared=prepared, observe_effect=lambda identity: (events.append("effect-observed"), observed.append(identity)))
    assert result.docker.exit_code == 0
    assert len(observed) == 1
    assert events.index("effect-observed") < events.index("guardian-start") < events.index("guardian-ready") < events.index("workload-start")
    assert events[-2:] == ["guardian-removed", "network-removed"]


def test_allowlist_guardian_failure_after_observation_cleans_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import capt_runtime.tools.backends.inversion_sandbox as sandbox_mod
    from capt_runtime.tools.backends.docker import (
        DockerPreparedTarget,
        DockerProcessRequest,
    )

    profile = _allowlist_profile(tmp_path)
    backend = sandbox_mod.InversionSandboxProcessBackend(sandbox_mod.InversionSandboxProfileRegistry((profile,)))
    prepared = sandbox_mod.InversionSandboxPreparedTarget(
        profile, DockerPreparedTarget(profile.docker_profile(), "unix:///tmp/docker.sock", "sha256:" + "a" * 64, None)
    )
    workload_id, guardian_id = "5" * 64, "6" * 64
    guardian_image_id = "sha256:" + "7" * 64
    events: list[str] = []
    network_name: list[str] = []

    def run_endpoint(_endpoint, args, **_kwargs):
        args = tuple(args)
        if args[:2] == ("image", "inspect"):
            return _command_result(json.dumps([{"Id": guardian_image_id, "RepoDigests": []}]))
        if args[:3] == ("network", "create", "--internal"):
            network_name.append(args[-1]); return _command_result("8" * 64 + "\n")
        if args and args[0] == "create": return _command_result(guardian_id + "\n")
        if args[:2] == ("network", "connect"): return _command_result()
        if args[:2] == ("inspect", guardian_id):
            return _command_result(json.dumps([{"Id": guardian_id, "Image": guardian_image_id, "State": {"Status": "created"}, "Config": {"User": f"{profile.uid}:{profile.gid}"}, "HostConfig": {"ReadonlyRootfs": True, "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true"], "Privileged": False, "Devices": [], "NetworkMode": "bridge"}}]))
        if args[:2] == ("inspect", workload_id):
            record = _created_record(profile, prepared.docker.image_id, workload_id)
            record["HostConfig"]["NetworkMode"] = network_name[0]
            record["NetworkSettings"]["Networks"] = {network_name[0]: {}}
            return _command_result(json.dumps([record]))
        if args[:2] == ("start", guardian_id): events.append("guardian-start"); return _command_result(stderr="boom", exit_code=1)
        if args[:3] == ("rm", "-f", guardian_id): events.append("guardian-removed"); return _command_result()
        if args[:2] == ("network", "rm"): events.append("network-removed"); return _command_result()
        if args[:3] == ("rm", "-f", workload_id): events.append("workload-removed"); return _command_result()
        raise AssertionError(args)

    monkeypatch.setattr(backend.docker_backend, "_run_endpoint", run_endpoint)

    def execute_workload(_request, *, prepared, observe_effect, network_mode_override=None):
        observe_effect(json.dumps({"containerId": workload_id, "containerCwd": "/workspace"}))
        raise AssertionError("docker backend must not reach workload start after guardian failure")

    monkeypatch.setattr(backend.docker_backend, "execute", execute_workload)
    request = DockerProcessRequest(profile.profile_id, ("/bin/true",), "/workspace", "/workspace")
    with pytest.raises(RuntimeError, match="guardian start"):
        backend.execute(request, prepared=prepared, observe_effect=lambda _identity: events.append("effect-observed"))
    assert "effect-observed" in events
    assert "workload-removed" in events
    assert events[-2:] == ["guardian-removed", "network-removed"]


def _created_record(profile, image_id: str, container_id: str) -> dict:
    return {
        "Id": container_id,
        "Image": image_id,
        "State": {"Status": "created"},
        "Config": {"User": f"{profile.uid}:{profile.gid}"},
        "HostConfig": {
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "Memory": profile.memory_bytes,
            "NanoCpus": int(profile.cpus * 1_000_000_000),
            "PidsLimit": profile.pids_limit,
            "NetworkMode": "none",
            "Tmpfs": {
                "/tmp": f"rw,nosuid,nodev,noexec,size={profile.tmpfs_bytes}",
                "/run": f"rw,nosuid,nodev,noexec,size={profile.tmpfs_bytes}",
            },
            "Privileged": False,
            "Devices": [],
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "",
        },
        "Mounts": [],
        "NetworkSettings": {"Networks": {}},
    }
