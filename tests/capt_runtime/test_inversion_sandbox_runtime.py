from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from capt_runtime.composition import create_runtime
from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.docker import DockerPreparedTarget


def _sandbox_module():
    return importlib.import_module("capt_runtime.tools.backends.inversion_sandbox")


def _adapter_module():
    return importlib.import_module("capt_runtime.tools.adapters.inversion_sandbox_terminal")


def _profile(tmp_path: Path):
    mod = _sandbox_module()
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    return mod.InversionSandboxProfile(
        profile_id="inv-runtime-test",
        context_name="desktop-linux",
        image_ref="example.invalid/image:test",
        allowed_host_roots=(work,),
        allowed_container_roots=("/workspace",),
        working_dir="/workspace",
    )

def test_runtime_registers_inversion_sandbox_independently(tmp_path: Path) -> None:
    runtime = create_runtime(str(tmp_path / "rt.db"))
    try:
        registration = runtime.tool_registry.require("terminal.inversion_sandbox")
        assert registration["descriptor"]["terminalBackends"] == ["inversion_sandbox"]
        assert registration["adapter"] is not runtime.tool_registry.adapter("terminal.docker")
        readiness = runtime.tool_registry.readiness("terminal.inversion_sandbox")
        assert readiness["status"] == "unavailable"
        assert "no named InversionSandbox profiles" in readiness["reason"]
    finally:
        runtime.close()


def test_inversion_profile_registry_is_not_docker_registry(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    runtime = create_runtime(
        str(tmp_path / "rt.db"), inversion_sandbox_profiles=(profile,)
    )
    try:
        assert runtime.inversion_sandbox_profile_registry.require(profile.profile_id) is profile
        with pytest.raises(AuthorityViolation, match="Docker profile"):
            runtime.docker_profile_registry.require(profile.profile_id)
    finally:
        runtime.close()

def test_effect_identity_binds_all_security_digests(tmp_path: Path) -> None:
    mod = _sandbox_module()
    profile = _profile(tmp_path)
    prepared = DockerPreparedTarget(
        profile.docker_profile(), "unix:///tmp/docker.sock", "sha256:" + "a" * 64, None
    )
    attestation = mod.InversionSandboxAttestation(
        digest="b" * 64,
        security_profile_digest="c" * 64,
        network_policy_digest="d" * 64,
        filesystem_scope_digest="e" * 64,
        canonical_json="{}",
    )
    backend = mod.InversionSandboxProcessBackend(mod.InversionSandboxProfileRegistry((profile,)))
    identity = json.loads(backend.effect_identity(prepared, profile, "f" * 64, "/workspace", attestation))
    assert identity["backend"] == "inversion_sandbox"
    assert identity["securityProfileDigest"] == "c" * 64
    assert identity["networkPolicyDigest"] == "d" * 64
    assert identity["filesystemScopeDigest"] == "e" * 64
    assert identity["attestationDigest"] == "b" * 64


def test_adapter_never_accepts_docker_tool_id(tmp_path: Path) -> None:
    mod = _sandbox_module()
    adapter_mod = _adapter_module()
    backend = mod.InversionSandboxProcessBackend(mod.InversionSandboxProfileRegistry((_profile(tmp_path),)))
    adapter = adapter_mod.InversionSandboxTerminalToolAdapter(backend)
    with pytest.raises(AuthorityViolation, match="terminal.inversion_sandbox"):
        adapter._process_request({"toolId": "terminal.docker"})


def _control_result(stdout: str = "", stderr: str = "", exit_code: int = 0, timed_out: bool = False):
    from types import SimpleNamespace

    return SimpleNamespace(
        stdout=stdout, stderr=stderr, exit_code=exit_code, timed_out=timed_out,
        stdout_total_bytes=len(stdout.encode()), stderr_total_bytes=len(stderr.encode()),
        stdout_truncated=False, stderr_truncated=False,
    )


def test_preflight_fails_closed_when_seccomp_is_not_proved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from capt_runtime.tools.backends.docker import DockerProcessRequest

    mod = _sandbox_module()
    profile = _profile(tmp_path)
    backend = mod.InversionSandboxProcessBackend(mod.InversionSandboxProfileRegistry((profile,)))
    prepared = DockerPreparedTarget(profile.docker_profile(), "unix:///tmp/docker.sock", "sha256:" + "9" * 64, None)
    monkeypatch.setattr(backend.docker_backend, "preflight", lambda _request: prepared)
    monkeypatch.setattr(
        backend.docker_backend,
        "_run_endpoint",
        lambda *_args, **_kwargs: _control_result('["name=cgroupns"]'),
    )
    request = DockerProcessRequest(profile.profile_id, ("/bin/true",), "/workspace", "/workspace")
    with pytest.raises(AuthorityViolation, match="seccomp"):
        backend.preflight(request)


def test_allowlist_preflight_requires_local_guardian_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from capt_runtime.tools.backends.docker import DockerProcessRequest

    mod = _sandbox_module()
    work = tmp_path / "allow-preflight"
    work.mkdir()
    profile = mod.InversionSandboxProfile(
        profile_id="inv-allow-preflight", context_name="desktop-linux",
        image_ref="example.invalid/workload:test", guardian_image_ref="example.invalid/guardian:test",
        allowed_host_roots=(work,),
        network_policy=mod.InversionSandboxNetworkPolicy(mode="allowlist", allow=("example.com",)),
    )
    backend = mod.InversionSandboxProcessBackend(mod.InversionSandboxProfileRegistry((profile,)))
    prepared = DockerPreparedTarget(profile.docker_profile(), "unix:///tmp/docker.sock", "sha256:" + "8" * 64, None)
    monkeypatch.setattr(backend.docker_backend, "preflight", lambda _request: prepared)

    def run_endpoint(_endpoint, args, **_kwargs):
        if tuple(args)[:2] == ("info", "--format"):
            return _control_result('["name=seccomp,profile=builtin"]')
        if tuple(args)[:2] == ("image", "inspect"):
            return _control_result(stderr="missing", exit_code=1)
        raise AssertionError(args)

    monkeypatch.setattr(backend.docker_backend, "_run_endpoint", run_endpoint)
    request = DockerProcessRequest(profile.profile_id, ("/bin/true",), "/workspace", "/workspace")
    with pytest.raises(AuthorityViolation, match="guardian image"):
        backend.preflight(request)
