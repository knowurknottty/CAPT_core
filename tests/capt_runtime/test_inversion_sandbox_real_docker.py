from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.docker import DockerMount, DockerProcessRequest
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxNetworkPolicy,
    InversionSandboxProcessBackend,
    InversionSandboxProfile,
    InversionSandboxProfileRegistry,
)

CONTEXT = "desktop-linux"


def _docker() -> str:
    value = shutil.which("docker")
    if not value:
        pytest.skip("Docker CLI unavailable")
    return value


def _image(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        pytest.skip(f"{env_name} is not configured")
    checked = subprocess.run(
        [_docker(), "--context", CONTEXT, "image", "inspect", value],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if checked.returncode != 0:
        pytest.skip(f"{env_name} image is not present locally")
    return value


def _profile(tmp_path: Path, *, allowlist: bool = False) -> InversionSandboxProfile:
    image = _image("CAPT_DOCKER_TEST_IMAGE")
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    work.chmod(0o777)
    policy = (
        InversionSandboxNetworkPolicy(mode="allowlist", allow=("example.com",))
        if allowlist
        else InversionSandboxNetworkPolicy()
    )
    return InversionSandboxProfile(
        profile_id="real-inversion",
        context_name=CONTEXT,
        image_ref=image,
        guardian_image_ref=_image("CAPT_INVERSION_GUARDIAN_IMAGE") if allowlist else None,
        allowed_host_roots=(work,),
        mounts=(DockerMount(work, "/workspace", "rw"),),
        network_policy=policy,
    )


def _backend(profile: InversionSandboxProfile) -> InversionSandboxProcessBackend:
    return InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))


def _request(profile: InversionSandboxProfile, code: str, timeout: float = 10.0) -> DockerProcessRequest:
    return DockerProcessRequest(
        profile_id=profile.profile_id,
        argv=("/usr/local/bin/python3", "-c", code),
        cwd="/workspace",
        filesystem_root="/workspace",
        timeout_seconds=timeout,
        stdout_limit_bytes=64 * 1024,
        stderr_limit_bytes=64 * 1024,
    )


def _inspect(container_id: str) -> dict:
    result = subprocess.run(
        [_docker(), "--context", CONTEXT, "inspect", container_id],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return json.loads(result.stdout)[0]


def test_real_hardened_created_state_is_observed_before_start_and_cleaned(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    backend = _backend(profile)
    assert backend.readiness()["status"] == "available"
    observed: list[dict] = []

    def observe(identity: str) -> None:
        parsed = json.loads(identity)
        record = _inspect(parsed["containerId"])
        assert record["State"]["Status"] == "created"
        assert record["Config"]["User"] == "65532:65532"
        assert record["HostConfig"]["ReadonlyRootfs"] is True
        assert "ALL" in record["HostConfig"]["CapDrop"]
        assert "no-new-privileges:true" in record["HostConfig"]["SecurityOpt"]
        assert record["HostConfig"]["Privileged"] is False
        assert record["HostConfig"]["Devices"] == []
        assert record["HostConfig"]["NetworkMode"] == "none"
        observed.append(parsed)

    result = backend.execute(
        _request(profile, "import os; print(os.getuid()); open('/workspace/marker','w').write('ok')"),
        prepared=backend.preflight(_request(profile, "import os; print(os.getuid()); open('/workspace/marker','w').write('ok')")),
        observe_effect=observe,
    )
    assert result.docker.exit_code == 0
    assert result.docker.stdout.strip() == "65532"
    assert (tmp_path / "work" / "marker").read_text() == "ok"
    assert subprocess.run([_docker(), "--context", CONTEXT, "inspect", observed[0]["containerId"]], capture_output=True).returncode != 0


def test_real_parent_secret_is_not_inherited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile = _profile(tmp_path)
    backend = _backend(profile)
    monkeypatch.setenv("CAPT_INVERSION_PARENT_SECRET", "must-not-leak")
    request = _request(profile, "import os; print(os.environ.get('CAPT_INVERSION_PARENT_SECRET','unset'))")
    result = backend.execute(request, prepared=backend.preflight(request), observe_effect=lambda _identity: None)
    assert result.docker.exit_code == 0
    assert result.docker.stdout.strip() == "unset"


def test_real_allowlist_blocks_direct_route_allows_proxy_and_denies_metadata(tmp_path: Path) -> None:
    profile = _profile(tmp_path, allowlist=True)
    backend = _backend(profile)
    code = r'''
import socket, urllib.error, urllib.request
try:
    socket.create_connection(("93.184.216.34", 80), 1).close()
    print("DIRECT=BAD")
except OSError:
    print("DIRECT=BLOCKED")
try:
    with urllib.request.urlopen("http://example.com/", timeout=8) as r:
        print("PROXY=OK", r.status)
except Exception as e:
    print("PROXY=FAIL", type(e).__name__)
try:
    with urllib.request.urlopen("https://example.com/", timeout=8) as r:
        print("HTTPS=OK", r.status)
except Exception as e:
    print("HTTPS=FAIL", type(e).__name__)
try:
    urllib.request.urlopen("http://169.254.169.254/", timeout=3)
    print("META=BAD")
except urllib.error.HTTPError as e:
    print("META=DENIED", e.code)
except Exception as e:
    print("META=FAIL", type(e).__name__)
'''
    request = _request(profile, code, timeout=20.0)
    result = backend.execute(request, prepared=backend.preflight(request), observe_effect=lambda _identity: None)
    assert result.docker.exit_code == 0, result.docker.stderr
    assert "DIRECT=BLOCKED" in result.docker.stdout
    assert "PROXY=OK" in result.docker.stdout
    assert "HTTPS=OK" in result.docker.stdout
    assert "META=DENIED 403" in result.docker.stdout


def test_real_allowlist_timeout_removes_workload_guardian_and_network(tmp_path: Path) -> None:
    profile = _profile(tmp_path, allowlist=True)
    backend = _backend(profile)
    request = _request(profile, "import time; time.sleep(30)", timeout=0.25)
    result = backend.execute(request, prepared=backend.preflight(request), observe_effect=lambda _identity: None)
    assert result.docker.timed_out is True
    identity = json.loads(result.side_effect_identity or "{}")
    for container_id in (identity["containerId"], identity["guardianContainerId"]):
        assert subprocess.run([_docker(), "--context", CONTEXT, "inspect", container_id], capture_output=True).returncode != 0
    assert subprocess.run([_docker(), "--context", CONTEXT, "network", "inspect", identity["internalNetwork"]], capture_output=True).returncode != 0


def test_real_attestation_failure_never_starts_workload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import capt_runtime.tools.backends.inversion_sandbox as sandbox_mod

    profile = _profile(tmp_path)
    backend = _backend(profile)
    marker = tmp_path / "work" / "must-not-exist"
    request = _request(profile, "open('/workspace/must-not-exist','w').write('bad')")
    prepared = backend.preflight(request)

    def reject(*_args, **_kwargs):
        raise AuthorityViolation("forced attestation mismatch")

    monkeypatch.setattr(sandbox_mod, "attest_created_container", reject)
    with pytest.raises(AuthorityViolation, match="forced attestation mismatch"):
        backend.execute(request, prepared=prepared, observe_effect=lambda _identity: None)
    assert not marker.exists()
