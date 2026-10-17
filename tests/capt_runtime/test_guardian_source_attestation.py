"""P0: never reuse a persistent Guardian without checking its baked source bytes."""
from __future__ import annotations

import hashlib

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.inversion_sandbox import (
    InversionSandboxNetworkPolicy,
    InversionSandboxProcessBackend,
    InversionSandboxProfile,
    InversionSandboxProfileRegistry,
    SandboxRuntimeIdentity,
)


def _case():
    profile = InversionSandboxProfile(
        profile_id="persistent-guardian-source",
        context_name="local-docker",
        image_ref="python:3.13-slim",
        guardian_image_ref="python:3.13-slim",
        network_policy=InversionSandboxNetworkPolicy(
            mode="allowlist", allow=("example.com",),
        ),
        persistent_entrypoint_argv=("/usr/local/bin/python3", "-c", "pass"),
    )
    backend = InversionSandboxProcessBackend(InversionSandboxProfileRegistry((profile,)))
    return profile, backend


def test_persistent_guardian_verifies_the_actual_docker_config_command():
    profile, backend = _case()
    source = backend._guardian_source()
    actual = [profile.guardian_python, "-c", source]
    result = backend._verify_guardian_source_command({"Cmd": actual}, profile)
    assert result == hashlib.sha256(source.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("cmd", [
    None,
    [],
    ["/usr/local/bin/python3", "-c", "old guardian source"],
    ["/usr/local/bin/python3", "-m", "fake_module"],
    ["/bin/sh", "-c", "old guardian source"],
    ["/usr/local/bin/python3", "-c", "old guardian source", "extra"],
])
def test_persistent_guardian_refuses_unverifiable_or_stale_commands(cmd):
    profile, backend = _case()
    with pytest.raises(AuthorityViolation, match="Guardian source"):
        backend._verify_guardian_source_command({"Cmd": cmd}, profile)


def test_persistent_guardian_inspection_rejects_stale_source_before_reuse(monkeypatch):
    profile, backend = _case()
    lease = "lease-guardian-old"
    from capt_runtime.tools.backends.docker import DockerPreparedTarget
    from capt_runtime.tools.backends.inversion_sandbox import (
        InversionSandboxPreparedTarget,
    )
    prepared = InversionSandboxPreparedTarget(
        profile, DockerPreparedTarget(profile.docker_profile(), "unix:///tmp/test.sock",
                                      "sha256:" + "a" * 64, None)
    )
    expected_labels = backend.persistent_labels(lease, profile, prepared)
    identity = SandboxRuntimeIdentity(
        sandbox_lease_id=lease,
        profile_id=profile.profile_id,
        profile_digest=profile.profile_digest(),
        context_endpoint="unix:///tmp/test.sock",
        daemon_identity_digest="sha256:" + "1" * 64,
        workload_container_id="b" * 64,
        workload_image_id="sha256:" + "a" * 64,
        security_profile_digest="sha256:" + "2" * 64,
        network_policy_digest="sha256:" + profile.network_policy.digest(),
        filesystem_scope_digest="sha256:" + "3" * 64,
        persistent_entrypoint_digest=profile.persistent_entrypoint_digest(),
        creation_attestation_digest="sha256:" + "4" * 64,
        guardian_container_id="c" * 64,
        guardian_image_id="sha256:" + "d" * 64,
        internal_network_name="test-capt-internal",
        internal_network_id="e" * 64,
    )
    record = {
        "Image": identity.guardian_image_id,
        "Config": {
            "Labels": expected_labels,
            "Cmd": [profile.guardian_python, "-c", "unpatched guardian source"],
        },
    }
    monkeypatch.setattr(backend.docker_backend, "_inspect_exact", lambda *_: record)
    with pytest.raises(AuthorityViolation, match="Guardian source"):
        backend._verify_persistent_guardian(identity, profile)
