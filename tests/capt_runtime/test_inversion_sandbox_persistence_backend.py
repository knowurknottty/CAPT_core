from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.docker import (
    DockerPreparedTarget,
    DockerProcessRequest,
)
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxPreparedTarget,
    InversionSandboxProcessBackend,
    InversionSandboxProfile,
    InversionSandboxProfileRegistry,
)

IMAGE = "sha256:" + "a" * 64
CONTAINER = "b" * 64
ENDPOINT = "unix:///tmp/docker.sock"


def _profile(**kwargs) -> InversionSandboxProfile:
    values = {
        "profile_id": "persistent-test",
        "context_name": "desktop-linux",
        "image_ref": "python:3.13-slim",
        "persistent_entrypoint_argv": ("/usr/local/bin/python3", "-c", "import time; time.sleep(3600)"),
        "default_ttl_seconds": 1800,
        "max_ttl_seconds": 3600,
    }
    values.update(kwargs)
    return InversionSandboxProfile(**values)


def _prepared(profile: InversionSandboxProfile) -> InversionSandboxPreparedTarget:
    docker_profile = profile.docker_profile()
    return InversionSandboxPreparedTarget(
        profile=profile,
        docker=DockerPreparedTarget(docker_profile, ENDPOINT, IMAGE, None),
    )


def _request(profile: InversionSandboxProfile) -> DockerProcessRequest:
    return DockerProcessRequest(
        profile_id=profile.profile_id,
        argv=profile.persistent_entrypoint_argv or ("/bin/false",),
        cwd=profile.working_dir,
        filesystem_root=profile.working_dir,
        timeout_seconds=10.0,
        stdout_limit_bytes=4096,
        stderr_limit_bytes=4096,
    )


def _result(*, stdout="", stderr="", exit_code=0, timed_out=False):
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


def _created_record(profile: InversionSandboxProfile, *, image=IMAGE, labels=None, running=False):
    return {
        "Id": CONTAINER,
        "Image": image,
        "State": {"Status": "running" if running else "created", "Running": running},
        "Config": {"User": f"{profile.uid}:{profile.gid}", "Labels": labels or {}},
        "HostConfig": {
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "Memory": profile.memory_bytes,
            "NanoCpus": int(float(profile.cpus) * 1_000_000_000),
            "PidsLimit": profile.pids_limit,
            "Privileged": False,
            "Devices": [],
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "",
            "Tmpfs": {
                "/tmp": f"rw,nosuid,nodev,noexec,size={profile.tmpfs_bytes}",
                "/run": f"rw,nosuid,nodev,noexec,size={profile.tmpfs_bytes}",
            },
            "NetworkMode": "none",
        },
        "Mounts": [],
        "NetworkSettings": {"Networks": {"none": {}}},
    }


def test_persistent_profile_is_opt_in_and_ttl_is_bounded() -> None:
    ordinary = InversionSandboxProfile(
        profile_id="ordinary", context_name="desktop-linux", image_ref="python:3.13-slim"
    )
    assert ordinary.persistent_entrypoint_argv is None
    with pytest.raises(AuthorityViolation, match="entrypoint"):
        _profile(persistent_entrypoint_argv=())
    with pytest.raises(AuthorityViolation, match="TTL"):
        _profile(max_ttl_seconds=86401)
    with pytest.raises(AuthorityViolation, match="TTL"):
        _profile(default_ttl_seconds=3601, max_ttl_seconds=3600)


def test_profile_digest_binds_persistent_entrypoint_and_ttl() -> None:
    a = _profile()
    b = _profile(persistent_entrypoint_argv=("/bin/sleep", "3600"))
    c = _profile(max_ttl_seconds=1800)
    assert a.profile_digest().startswith("sha256:")
    assert a.profile_digest() != b.profile_digest()
    assert a.profile_digest() != c.profile_digest()


def test_persistent_create_attests_stopped_workload_and_applies_exact_labels(monkeypatch) -> None:
    profile = _profile()
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    prepared = _prepared(profile)
    calls = []
    labels = backend.persistent_labels("sandbox-1", profile, prepared)

    def fake_run(endpoint, args, **kwargs):
        calls.append(args)
        if args[0] == "info":
            if "SecurityOptions" in args[-1]:
                return _result(stdout=json.dumps(["name=seccomp,profile=builtin"]))
            return _result(stdout=json.dumps("daemon-1"))
        if args[0] == "create":
            return _result(stdout=CONTAINER + "\n")
        if args[0] == "inspect":
            return _result(stdout=json.dumps([_created_record(profile, labels=labels)]))
        raise AssertionError(args)

    monkeypatch.setattr(backend.docker_backend, "_run_endpoint", fake_run)
    identity = backend.create_persistent_stopped(
        "sandbox-1", _request(profile), prepared=prepared
    )
    create = next(args for args in calls if args[0] == "create")
    assert "start" not in [args[0] for args in calls]
    for key, value in labels.items():
        assert "--label" in create
        assert f"{key}={value}" in create
    assert identity.workload_container_id == CONTAINER
    assert identity.workload_image_id == IMAGE
    assert identity.profile_digest == profile.profile_digest()
    assert identity.creation_attestation_digest.startswith("sha256:")


def test_persistent_start_rejects_image_drift_before_start(monkeypatch) -> None:
    profile = _profile()
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    prepared = _prepared(profile)
    labels = backend.persistent_labels("sandbox-1", profile, prepared)
    phase = {"drift": False}
    calls = []

    def fake_run(endpoint, args, **kwargs):
        calls.append(args)
        if args[0] == "info":
            if "SecurityOptions" in args[-1]:
                return _result(stdout=json.dumps(["name=seccomp,profile=builtin"]))
            return _result(stdout=json.dumps("daemon-1"))
        if args[0] == "create":
            return _result(stdout=CONTAINER + "\n")
        if args[0] == "inspect":
            image = "sha256:" + "c" * 64 if phase["drift"] else IMAGE
            return _result(stdout=json.dumps([_created_record(profile, image=image, labels=labels)]))
        if args[0] == "start":
            return _result(stdout=CONTAINER + "\n")
        raise AssertionError(args)

    monkeypatch.setattr(backend.docker_backend, "_run_endpoint", fake_run)
    identity = backend.create_persistent_stopped("sandbox-1", _request(profile), prepared=prepared)
    phase["drift"] = True
    with pytest.raises(AuthorityViolation, match="identity"):
        backend.start_persistent(identity)
    assert not any(args[0] == "start" for args in calls)


def test_persistent_exec_is_nonroot_and_timeout_is_not_proven_terminated(monkeypatch) -> None:
    profile = _profile()
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    prepared = _prepared(profile)
    labels = backend.persistent_labels("sandbox-1", profile, prepared)
    calls = []
    inspect_count = {"n": 0}

    def fake_run(endpoint, args, **kwargs):
        calls.append(args)
        if args[0] == "info":
            if "SecurityOptions" in args[-1]:
                return _result(stdout=json.dumps(["name=seccomp,profile=builtin"]))
            return _result(stdout=json.dumps("daemon-1"))
        if args[0] == "create":
            return _result(stdout=CONTAINER + "\n")
        if args[0] == "inspect":
            inspect_count["n"] += 1
            return _result(stdout=json.dumps([
                _created_record(profile, labels=labels, running=inspect_count["n"] > 1)
            ]))
        if args[0] == "exec":
            return _result(stderr="timeout", exit_code=None, timed_out=True)
        raise AssertionError(args)

    monkeypatch.setattr(backend.docker_backend, "_run_endpoint", fake_run)
    identity = backend.create_persistent_stopped("sandbox-1", _request(profile), prepared=prepared)
    result = backend.exec_persistent(
        identity,
        argv=("/bin/echo", "ok"),
        cwd="/workspace",
        timeout_seconds=0.1,
        stdout_limit_bytes=4096,
        stderr_limit_bytes=4096,
    )
    exec_args = next(args for args in calls if args[0] == "exec")
    assert exec_args[exec_args.index("--user") + 1] == f"{profile.uid}:{profile.gid}"
    assert "--privileged" not in exec_args and "--detach" not in exec_args
    assert result.timed_out is True
    assert result.termination_proven is False


def test_persistent_close_removes_only_exact_identity_after_reinspection(monkeypatch) -> None:
    profile = _profile()
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    prepared = _prepared(profile)
    labels = backend.persistent_labels("sandbox-1", profile, prepared)
    calls = []
    state = {"inspect_count": 0, "removed": False}

    def fake_run(endpoint, args, **kwargs):
        calls.append(args)
        if args[0] == "info":
            if "SecurityOptions" in args[-1]:
                return _result(stdout=json.dumps(["name=seccomp,profile=builtin"]))
            return _result(stdout=json.dumps("daemon-1"))
        if args[0] == "create":
            return _result(stdout=CONTAINER + "\n")
        if args[0] == "inspect":
            if state["removed"]:
                return _result(stderr="Error: No such container", exit_code=1)
            state["inspect_count"] += 1
            return _result(stdout=json.dumps([
                _created_record(profile, labels=labels, running=state["inspect_count"] > 1)
            ]))
        if args[0] == "rm":
            assert args[-1] == CONTAINER
            state["removed"] = True
            return _result(stdout=CONTAINER + "\n")
        raise AssertionError(args)

    monkeypatch.setattr(backend.docker_backend, "_run_endpoint", fake_run)
    identity = backend.create_persistent_stopped("sandbox-1", _request(profile), prepared=prepared)
    receipt = backend.close_persistent(identity)
    assert receipt.cleanup_succeeded is True
    assert receipt.closure_receipt_digest.startswith("sha256:")
    assert any(args[0] == "rm" and args[-1] == CONTAINER for args in calls)
