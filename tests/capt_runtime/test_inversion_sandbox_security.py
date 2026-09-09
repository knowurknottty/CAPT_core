from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.docker import DockerPreparedTarget


def _mod():
    return importlib.import_module("capt_runtime.tools.backends.inversion_sandbox")


def _profile(tmp_path: Path, **overrides):
    mod = _mod()
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    values = {
        "profile_id": "inv-test",
        "context_name": "desktop-linux",
        "image_ref": "example.invalid/image:test",
        "allowed_host_roots": (work,),
        "allowed_container_roots": ("/workspace",),
        "working_dir": "/workspace",
        "memory_bytes": 256 * 1024 * 1024,
        "pids_limit": 64,
    }
    values.update(overrides)
    return mod.InversionSandboxProfile(**values)


def test_profile_rejects_root_identity_and_unrestricted_without_opt_in(tmp_path: Path) -> None:
    mod = _mod()
    with pytest.raises(AuthorityViolation, match="non-root"):
        _profile(tmp_path, uid=0)
    unrestricted = mod.InversionSandboxNetworkPolicy(mode="unrestricted")
    with pytest.raises(AuthorityViolation, match="unrestricted"):
        _profile(tmp_path, network_policy=unrestricted)


def test_network_policy_is_canonical_and_digest_stable() -> None:
    mod = _mod()
    first = mod.InversionSandboxNetworkPolicy(
        mode="allowlist", allow=("EXAMPLE.COM.", "10.20.0.0/16", "*.Example.org")
    )
    second = mod.InversionSandboxNetworkPolicy(
        mode="allowlist", allow=("*.example.org", "10.20.3.4/16", "example.com")
    )
    assert first.canonical() == second.canonical()
    assert first.digest() == second.digest()
    assert "169.254.0.0/16" in first.canonical()["platformDeny"]
    assert "10.0.0.0/8" in first.canonical()["platformDeny"]


def test_seccomp_readiness_requires_docker_seccomp_security_option() -> None:
    mod = _mod()
    assert mod.docker_security_options_have_seccomp(["name=seccomp,profile=builtin", "name=cgroupns"])
    assert not mod.docker_security_options_have_seccomp(["name=cgroupns"])
    assert not mod.docker_security_options_have_seccomp(None)


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


def test_attestation_accepts_hardened_created_state_and_rejects_weakened_state(tmp_path: Path) -> None:
    mod = _mod()
    profile = _profile(tmp_path)
    docker_profile = profile.docker_profile()
    prepared = DockerPreparedTarget(
        profile=docker_profile,
        context_endpoint="unix:///tmp/docker.sock",
        image_id="sha256:" + "c" * 64,
        repo_digest=None,
    )
    container_id = "d" * 64
    record = _created_record(profile, prepared.image_id, container_id)
    attestation = mod.attest_created_container(profile, prepared, record)
    assert len(attestation.digest) == 64
    assert attestation.security_profile_digest == profile.security_profile_digest()
    assert attestation.network_policy_digest == profile.network_policy.digest()
    assert len(attestation.filesystem_scope_digest) == 64

    weakened = _created_record(profile, prepared.image_id, container_id)
    weakened["HostConfig"]["ReadonlyRootfs"] = False
    with pytest.raises(AuthorityViolation, match="read-only rootfs"):
        mod.attest_created_container(profile, prepared, weakened)


def test_attestation_rejects_identity_and_privilege_drift(tmp_path: Path) -> None:
    mod = _mod()
    profile = _profile(tmp_path)
    prepared = DockerPreparedTarget(profile.docker_profile(), "unix:///tmp/docker.sock", "sha256:" + "e" * 64, None)
    record = _created_record(profile, prepared.image_id, "f" * 64)
    record["HostConfig"]["Privileged"] = True
    with pytest.raises(AuthorityViolation, match="privileged"):
        mod.attest_created_container(profile, prepared, record)
