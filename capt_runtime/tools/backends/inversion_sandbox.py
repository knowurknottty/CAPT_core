"""CAPT-native hardened local sandbox profiles and applied-state attestation."""
from __future__ import annotations

import base64
import hashlib
import inspect
import ipaddress
import json
import re
import secrets
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends import inversion_guardian
from capt_runtime.tools.backends.docker import (
    DockerMount,
    DockerNetworkPolicy,
    DockerPreparedTarget,
    DockerProcessBackend,
    DockerProcessRequest,
    DockerProcessResult,
    DockerProfile,
    DockerProfileRegistry,
    DockerTmpfsMount,
)

DEFAULT_PLATFORM_DENY = (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16",
    "224.0.0.0/4", "240.0.0.0/4", "::1/128", "fc00::/7",
    "fe80::/10", "ff00::/8",
)
_HOST_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$")
_CONTAINER_ID_RE = re.compile(r"^[0-9a-f]{12,64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_target(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("sandbox network target must be a string")
    target = value.strip().lower()
    if not target or len(target) > 253 or "://" in target:
        raise ValueError(f"invalid sandbox network target: {value!r}")
    try:
        return str(ipaddress.ip_network(target, strict=False))
    except ValueError:
        pass
    wildcard = target.startswith("*.")
    host = target[2:] if wildcard else target
    host = host.rstrip(".")
    if not host or not _HOST_RE.fullmatch(host):
        raise ValueError(f"invalid sandbox network target: {value!r}")
    return "*." + host if wildcard else host


def docker_security_options_have_seccomp(options: object) -> bool:
    if not isinstance(options, list):
        return False
    return any(isinstance(item, str) and item.startswith(("name=seccomp", "seccomp=")) for item in options)


@dataclass(frozen=True)
class InversionSandboxNetworkPolicy:
    mode: str = "none"
    allow: tuple[str, ...] = ()
    platform_deny: tuple[str, ...] = DEFAULT_PLATFORM_DENY

    def __post_init__(self) -> None:
        if self.mode not in {"none", "allowlist", "unrestricted"}:
            raise ValueError("InversionSandbox network mode must be none, allowlist, or unrestricted")
        allow = tuple(sorted({_normalize_target(value) for value in self.allow}))
        deny = tuple(sorted({_normalize_target(value) for value in self.platform_deny}))
        if len(allow) > 128 or len(deny) > 128:
            raise ValueError("InversionSandbox network policy exceeds 128 targets")
        if self.mode != "allowlist" and allow:
            raise ValueError("network allow targets require allowlist mode")
        object.__setattr__(self, "allow", allow)
        object.__setattr__(self, "platform_deny", deny)

    def canonical(self) -> dict[str, object]:
        return {"mode": self.mode, "allow": list(self.allow), "platformDeny": list(self.platform_deny)}

    def digest(self) -> str:
        return _digest(self.canonical())


@dataclass(frozen=True)
class InversionSandboxAttestation:
    digest: str
    security_profile_digest: str
    network_policy_digest: str
    filesystem_scope_digest: str
    canonical_json: str


@dataclass(frozen=True)
class InversionSandboxProfile:
    profile_id: str
    context_name: str
    image_ref: str
    allowed_host_roots: tuple[Path, ...] = ()
    mounts: tuple[DockerMount, ...] = ()
    allowed_container_roots: tuple[str, ...] = ("/workspace",)
    working_dir: str = "/workspace"
    environment_overrides: tuple[tuple[str, str], ...] = ()
    cpus: float = 1.0
    memory_bytes: int = 512 * 1024 * 1024
    pids_limit: int = 256
    log_max_bytes: int = 8 * 1024 * 1024
    uid: int = 65532
    gid: int = 65532
    tmpfs_bytes: int = 64 * 1024 * 1024
    network_policy: InversionSandboxNetworkPolicy = field(default_factory=InversionSandboxNetworkPolicy)
    allow_unrestricted_egress: bool = False
    guardian_image_ref: str | None = None
    guardian_python: str = "/usr/local/bin/python3"

    def __post_init__(self) -> None:
        for name, value in (("uid", self.uid), ("gid", self.gid)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > 2_147_483_647:
                raise AuthorityViolation(f"InversionSandbox requires non-root numeric {name}")
        if self.network_policy.mode == "unrestricted" and not self.allow_unrestricted_egress:
            raise AuthorityViolation("InversionSandbox unrestricted egress requires operator profile opt-in")
        if self.network_policy.mode == "allowlist" and not self.guardian_image_ref:
            raise AuthorityViolation("InversionSandbox allowlist requires an explicit guardian image")
        self.docker_profile()

    def docker_profile(self) -> DockerProfile:
        docker_network = (
            DockerNetworkPolicy(mode="bridge", unrestricted_egress=True)
            if self.network_policy.mode == "unrestricted"
            else DockerNetworkPolicy(mode="none")
        )
        environment = list(self.environment_overrides)
        if self.network_policy.mode == "allowlist":
            protected = {"HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"}
            if protected.intersection(key for key, _value in environment):
                raise AuthorityViolation("InversionSandbox guardian proxy environment is profile-owned")
            proxy = "http://capt-guardian:18080"
            environment.extend((key, proxy) for key in sorted(protected))
        return DockerProfile(
            profile_id=self.profile_id,
            context_name=self.context_name,
            image_ref=self.image_ref,
            allowed_host_roots=self.allowed_host_roots,
            mounts=self.mounts,
            allowed_container_roots=self.allowed_container_roots,
            working_dir=self.working_dir,
            environment_overrides=tuple(environment),
            cpus=self.cpus,
            memory_bytes=self.memory_bytes,
            pids_limit=self.pids_limit,
            network_policy=docker_network,
            cleanup_policy="always",
            read_only_rootfs=True,
            user=f"{self.uid}:{self.gid}",
            cap_drop=("ALL",),
            no_new_privileges=True,
            tmpfs=(
                DockerTmpfsMount("/tmp", self.tmpfs_bytes),
                DockerTmpfsMount("/run", self.tmpfs_bytes),
            ),
            log_max_bytes=self.log_max_bytes,
        )

    def security_profile_digest(self) -> str:
        return _digest({
            "uid": self.uid, "gid": self.gid, "readOnlyRootfs": True,
            "capDrop": ["ALL"], "noNewPrivileges": True,
            "tmpfsBytes": self.tmpfs_bytes, "cpus": float(self.cpus),
            "memoryBytes": self.memory_bytes, "pidsLimit": self.pids_limit,
        })

    def filesystem_scope_digest(self) -> str:
        mounts = [
            {"host": str(m.host_path), "container": m.container_path, "mode": m.mode}
            for m in self.mounts
        ]
        return _digest({
            "allowedHostRoots": [str(p) for p in self.allowed_host_roots],
            "allowedContainerRoots": list(self.allowed_container_roots),
            "workingDir": self.working_dir,
            "mounts": mounts,
        })


class InversionSandboxProfileRegistry:
    def __init__(self, profiles: Iterable[InversionSandboxProfile] = ()) -> None:
        self._profiles: dict[str, InversionSandboxProfile] = {}
        for profile in profiles:
            if profile.profile_id in self._profiles:
                raise ValueError(f"duplicate InversionSandbox profile id: {profile.profile_id}")
            self._profiles[profile.profile_id] = profile

    def require(self, profile_id: str) -> InversionSandboxProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise AuthorityViolation(f"unknown InversionSandbox profile: {profile_id}") from exc

    def __len__(self) -> int:
        return len(self._profiles)

    def values(self) -> tuple[InversionSandboxProfile, ...]:
        return tuple(self._profiles.values())


def _tmpfs_options(value: object) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _none_network_isolated(networks: dict[str, object]) -> bool:
    if not networks:
        return True
    if set(networks) != {"none"}:
        return False
    record = networks.get("none")
    if not isinstance(record, dict):
        return False
    for key in ("NetworkID", "EndpointID", "Gateway", "IPAddress", "GlobalIPv6Address"):
        if record.get(key) not in (None, ""):
            return False
    for key in ("IPPrefixLen", "GlobalIPv6PrefixLen"):
        if record.get(key) not in (None, 0):
            return False
    return True


def _attest_mounts(profile: InversionSandboxProfile, record: dict[str, Any]) -> list[dict[str, object]]:
    raw = record.get("Mounts")
    if not isinstance(raw, list):
        raise AuthorityViolation("InversionSandbox inspect record missing mount evidence")
    actual: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("Type") != "bind":
            raise AuthorityViolation("InversionSandbox created container has unexpected non-bind mount")
        actual.append({"source": item.get("Source"), "destination": item.get("Destination"), "rw": item.get("RW")})
    expected = [
        {"source": str(m.host_path), "destination": m.container_path, "rw": m.mode == "rw"}
        for m in profile.mounts
    ]
    if sorted(actual, key=lambda x: str(x["destination"])) != sorted(expected, key=lambda x: str(x["destination"])):
        raise AuthorityViolation("InversionSandbox applied mounts differ from authorized filesystem scope")
    return actual


def attest_created_container(
    profile: InversionSandboxProfile,
    prepared: DockerPreparedTarget,
    record: dict[str, Any],
    *,
    expected_network_name: str | None = None,
) -> InversionSandboxAttestation:
    container_id = record.get("Id")
    if not isinstance(container_id, str) or not _CONTAINER_ID_RE.fullmatch(container_id):
        raise AuthorityViolation("InversionSandbox created container identity is invalid")
    if record.get("Image") != prepared.image_id:
        raise AuthorityViolation("InversionSandbox created container image identity drifted")
    if (record.get("State") or {}).get("Status") != "created":
        raise AuthorityViolation("InversionSandbox container must remain created before attestation")
    config = record.get("Config")
    host = record.get("HostConfig")
    if not isinstance(config, dict) or not isinstance(host, dict):
        raise AuthorityViolation("InversionSandbox inspect record is incomplete")
    if config.get("User") != f"{profile.uid}:{profile.gid}":
        raise AuthorityViolation("InversionSandbox applied user differs from required non-root identity")
    if host.get("ReadonlyRootfs") is not True:
        raise AuthorityViolation("InversionSandbox requires applied read-only rootfs")
    caps = host.get("CapDrop")
    if not isinstance(caps, list) or "ALL" not in {str(v).upper() for v in caps}:
        raise AuthorityViolation("InversionSandbox requires applied cap-drop ALL")
    security_opt = host.get("SecurityOpt")
    if not isinstance(security_opt, list) or "no-new-privileges:true" not in security_opt:
        raise AuthorityViolation("InversionSandbox requires applied no-new-privileges")

    expected_nano_cpus = int(float(profile.cpus) * 1_000_000_000)
    if host.get("Memory") != profile.memory_bytes:
        raise AuthorityViolation("InversionSandbox applied memory limit drifted")
    if host.get("NanoCpus") != expected_nano_cpus:
        raise AuthorityViolation("InversionSandbox applied CPU limit drifted")
    if host.get("PidsLimit") != profile.pids_limit:
        raise AuthorityViolation("InversionSandbox applied PID limit drifted")
    if host.get("Privileged") is not False:
        raise AuthorityViolation("InversionSandbox privileged mode is forbidden")
    if host.get("Devices") not in (None, []):
        raise AuthorityViolation("InversionSandbox device passthrough is forbidden")
    if host.get("PidMode") not in (None, ""):
        raise AuthorityViolation("InversionSandbox PID namespace sharing is forbidden")
    if host.get("IpcMode") in {"host"}:
        raise AuthorityViolation("InversionSandbox host IPC namespace is forbidden")
    if host.get("UTSMode") not in (None, ""):
        raise AuthorityViolation("InversionSandbox UTS namespace sharing is forbidden")

    tmpfs = host.get("Tmpfs")
    if not isinstance(tmpfs, dict) or set(tmpfs) != {"/tmp", "/run"}:
        raise AuthorityViolation("InversionSandbox tmpfs layout drifted")
    required_tmpfs = {"rw", "nosuid", "nodev", "noexec", f"size={profile.tmpfs_bytes}"}
    for path in ("/tmp", "/run"):
        if not required_tmpfs.issubset(_tmpfs_options(tmpfs.get(path))):
            raise AuthorityViolation(f"InversionSandbox tmpfs hardening drifted for {path}")
    mounts = _attest_mounts(profile, record)

    network_mode = host.get("NetworkMode")
    networks = (record.get("NetworkSettings") or {}).get("Networks")
    if not isinstance(networks, dict):
        raise AuthorityViolation("InversionSandbox network attachment evidence is missing")
    if expected_network_name is not None:
        if network_mode != expected_network_name or set(networks) != {expected_network_name}:
            raise AuthorityViolation("InversionSandbox allowlist network attachment drifted")
    elif profile.network_policy.mode == "unrestricted":
        if network_mode not in {"bridge", "default"}:
            raise AuthorityViolation("InversionSandbox unrestricted network mode drifted")
    else:
        if network_mode != "none" or not _none_network_isolated(networks):
            raise AuthorityViolation("InversionSandbox no-network mode drifted")

    security_digest = profile.security_profile_digest()
    network_digest = profile.network_policy.digest()
    filesystem_digest = profile.filesystem_scope_digest()
    applied = {
        "containerId": container_id,
        "imageId": prepared.image_id,
        "user": config.get("User"),
        "readOnlyRootfs": True,
        "capDrop": sorted(str(v).upper() for v in caps),
        "securityOpt": sorted(str(v) for v in security_opt),
        "memory": host.get("Memory"),
        "nanoCpus": host.get("NanoCpus"),
        "pidsLimit": host.get("PidsLimit"),
        "tmpfs": {key: sorted(_tmpfs_options(value)) for key, value in sorted(tmpfs.items())},
        "mounts": sorted(mounts, key=lambda x: str(x["destination"])),
        "networkMode": network_mode,
        "networks": sorted(networks),
    }
    canonical = _canonical_json(
        {
            "profileId": profile.profile_id,
            "contextEndpoint": prepared.context_endpoint,
            "applied": applied,
            "securityProfileDigest": security_digest,
            "networkPolicyDigest": network_digest,
            "filesystemScopeDigest": filesystem_digest,
        }
    )
    return InversionSandboxAttestation(
        digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        security_profile_digest=security_digest,
        network_policy_digest=network_digest,
        filesystem_scope_digest=filesystem_digest,
        canonical_json=canonical,
    )


@dataclass(frozen=True)
class InversionSandboxPreparedTarget:
    profile: InversionSandboxProfile
    docker: DockerPreparedTarget


@dataclass(frozen=True)
class InversionSandboxProcessResult:
    docker: DockerProcessResult
    attestation: InversionSandboxAttestation | None
    side_effect_identity: str | None


@dataclass(frozen=True)
class _AllowlistRuntime:
    network_name: str
    network_id: str
    guardian_id: str
    guardian_image_id: str
    guardian_source_digest: str


class InversionSandboxProcessBackend:
    backend_id = "inversion_sandbox"
    adapter_id = "backend-inversion-sandbox-process"

    def __init__(self, profiles: InversionSandboxProfileRegistry) -> None:
        self.profiles = profiles
        self.docker_profiles = DockerProfileRegistry(
            profile.docker_profile() for profile in profiles.values()
        )
        self.docker_backend = DockerProcessBackend(self.docker_profiles)

    def readiness(self) -> dict[str, object]:
        if len(self.profiles) == 0:
            return {
                "status": "unavailable",
                "reason": "no named InversionSandbox profiles configured",
            }
        base = self.docker_backend.readiness()
        if base.get("status") != "available":
            return base
        for profile in self.profiles.values():
            prepared_profile = self.docker_profiles.require(profile.profile_id)
            try:
                endpoint = self.docker_backend.preflight(
                    DockerProcessRequest(
                        profile_id=prepared_profile.profile_id,
                        argv=("/bin/true",),
                        cwd=prepared_profile.working_dir,
                        filesystem_root=prepared_profile.working_dir,
                        timeout_seconds=1.0,
                    )
                ).context_endpoint
                info = self.docker_backend._run_endpoint(
                    endpoint, ("info", "--format", "{{json .SecurityOptions}}"),
                    timeout_seconds=3.0, stdout_limit_bytes=8192, stderr_limit_bytes=8192,
                )
            except (AuthorityViolation, RuntimeError, ValueError):
                continue
            if info.exit_code != 0 or info.timed_out:
                continue
            try:
                security_options = json.loads(info.stdout)
            except json.JSONDecodeError:
                continue
            if docker_security_options_have_seccomp(security_options):
                return {
                    "status": "available",
                    "reason": "local Docker profile available with seccomp enabled",
                }
        return {
            "status": "unavailable",
            "reason": "no InversionSandbox profile proved local image, daemon, and seccomp readiness",
        }

    def _require_seccomp(self, endpoint: str) -> None:
        info = self.docker_backend._run_endpoint(
            endpoint, ("info", "--format", "{{json .SecurityOptions}}"),
            timeout_seconds=3.0, stdout_limit_bytes=8192, stderr_limit_bytes=8192,
        )
        if info.exit_code != 0 or info.timed_out:
            raise AuthorityViolation("InversionSandbox could not prove Docker seccomp readiness")
        try:
            options = json.loads(info.stdout)
        except json.JSONDecodeError as exc:
            raise AuthorityViolation("InversionSandbox Docker security options are invalid") from exc
        if not docker_security_options_have_seccomp(options):
            raise AuthorityViolation("InversionSandbox requires Docker seccomp")

    def _require_local_guardian_image(self, profile: InversionSandboxProfile, endpoint: str) -> None:
        if profile.network_policy.mode != "allowlist":
            return
        if not profile.guardian_image_ref:
            raise AuthorityViolation("InversionSandbox allowlist requires guardian image")
        inspected = self.docker_backend._run_endpoint(
            endpoint, ("image", "inspect", profile.guardian_image_ref),
            timeout_seconds=10.0, stdout_limit_bytes=4 * 1024 * 1024, stderr_limit_bytes=64 * 1024,
        )
        if inspected.exit_code != 0 or inspected.timed_out:
            raise AuthorityViolation("InversionSandbox guardian image is unavailable locally; implicit pull is disabled")
        try:
            image_id = json.loads(inspected.stdout)[0]["Id"]
        except (json.JSONDecodeError, IndexError, KeyError, TypeError) as exc:
            raise AuthorityViolation("InversionSandbox guardian image identity is invalid") from exc
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise AuthorityViolation("InversionSandbox guardian image identity is not immutable")

    def preflight(self, request: DockerProcessRequest) -> InversionSandboxPreparedTarget:
        profile = self.profiles.require(request.profile_id)
        docker = self.docker_backend.preflight(request)
        if docker.profile.profile_id != profile.profile_id:
            raise AuthorityViolation("InversionSandbox prepared Docker profile identity drifted")
        self._require_seccomp(docker.context_endpoint)
        self._require_local_guardian_image(profile, docker.context_endpoint)
        return InversionSandboxPreparedTarget(profile=profile, docker=docker)

    def effect_identity(
        self,
        prepared: DockerPreparedTarget,
        profile: InversionSandboxProfile,
        container_id: str,
        cwd: str,
        attestation: InversionSandboxAttestation,
        *,
        allowlist_runtime: _AllowlistRuntime | None = None,
    ) -> str:
        identity: dict[str, object] = {
            "backend": self.backend_id,
            "profileId": profile.profile_id,
            "contextEndpoint": prepared.context_endpoint,
            "containerId": container_id,
            "imageId": prepared.image_id,
            "repoDigest": prepared.repo_digest,
            "containerCwd": cwd,
            "securityProfileDigest": attestation.security_profile_digest,
            "networkPolicyDigest": attestation.network_policy_digest,
            "filesystemScopeDigest": attestation.filesystem_scope_digest,
            "attestationDigest": attestation.digest,
        }
        if allowlist_runtime is not None:
            identity.update({
                "internalNetwork": allowlist_runtime.network_name,
                "guardianContainerId": allowlist_runtime.guardian_id,
                "guardianImageId": allowlist_runtime.guardian_image_id,
                "guardianSourceDigest": allowlist_runtime.guardian_source_digest,
            })
        return _canonical_json(identity)

    def _guardian_source(self) -> str:
        return inspect.getsource(inversion_guardian)

    def _prepare_allowlist_runtime(
        self, profile: InversionSandboxProfile, endpoint: str
    ) -> _AllowlistRuntime:
        if not profile.guardian_image_ref:
            raise AuthorityViolation("InversionSandbox allowlist requires guardian image")
        inspected = self.docker_backend._run_endpoint(
            endpoint, ("image", "inspect", profile.guardian_image_ref),
            timeout_seconds=10.0, stdout_limit_bytes=4 * 1024 * 1024, stderr_limit_bytes=64 * 1024,
        )
        if inspected.exit_code != 0 or inspected.timed_out:
            raise AuthorityViolation("InversionSandbox guardian image is unavailable locally; implicit pull is disabled")
        try:
            guardian_image_id = json.loads(inspected.stdout)[0]["Id"]
        except (json.JSONDecodeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("InversionSandbox guardian image inspect returned invalid identity") from exc
        if not isinstance(guardian_image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", guardian_image_id):
            raise RuntimeError("InversionSandbox guardian image identity is not immutable")

        network_name = "capt_inv_" + secrets.token_hex(6)
        network = self.docker_backend._run_endpoint(
            endpoint, ("network", "create", "--internal", "--driver", "bridge", network_name),
            timeout_seconds=10.0, stdout_limit_bytes=4096, stderr_limit_bytes=16 * 1024,
        )
        if network.exit_code != 0 or network.timed_out:
            raise RuntimeError("InversionSandbox internal network creation failed")
        network_id = network.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{12,64}", network_id):
            self.docker_backend._run_endpoint(endpoint, ("network", "rm", network_name), timeout_seconds=5.0)
            raise RuntimeError("InversionSandbox internal network identity is invalid")

        source = self._guardian_source()
        source_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        policy_json = _canonical_json(profile.network_policy.canonical()).encode("utf-8")
        policy_b64 = base64.b64encode(policy_json).decode("ascii")
        guardian_name = "capt_guard_" + network_name.removeprefix("capt_inv_")
        args = [
            "create", "--pull", "never", "--name", guardian_name, "--network", "bridge",
            "--read-only", "--user", f"{profile.uid}:{profile.gid}",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--cpus", "0.25", "--memory", str(128 * 1024 * 1024), "--pids-limit", "64",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=16777216",
            "--tmpfs", "/run:rw,nosuid,nodev,noexec,size=16777216",
            "--env", f"CAPT_GUARDIAN_POLICY_B64={policy_b64}",
            "--env", f"CAPT_GUARDIAN_POLICY_DIGEST={profile.network_policy.digest()}",
            guardian_image_id, profile.guardian_python, "-c", source,
        ]
        created = self.docker_backend._run_endpoint(
            endpoint, tuple(args), timeout_seconds=15.0, stdout_limit_bytes=4096, stderr_limit_bytes=64 * 1024,
        )
        if created.exit_code != 0 or created.timed_out:
            self.docker_backend._run_endpoint(endpoint, ("network", "rm", network_name), timeout_seconds=5.0)
            raise RuntimeError("InversionSandbox guardian create failed")
        guardian_id = created.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{12,64}", guardian_id):
            self.docker_backend._run_endpoint(endpoint, ("network", "rm", network_name), timeout_seconds=5.0)
            raise RuntimeError("InversionSandbox guardian identity is invalid")
        connected = self.docker_backend._run_endpoint(
            endpoint, ("network", "connect", "--alias", "capt-guardian", network_name, guardian_id),
            timeout_seconds=10.0, stdout_limit_bytes=4096, stderr_limit_bytes=16 * 1024,
        )
        if connected.exit_code != 0 or connected.timed_out:
            self.docker_backend._cleanup(endpoint, guardian_id)
            self.docker_backend._run_endpoint(endpoint, ("network", "rm", network_name), timeout_seconds=5.0)
            raise RuntimeError("InversionSandbox guardian internal-network attachment failed")
        self._attest_guardian(profile, endpoint, guardian_id, guardian_image_id)
        return _AllowlistRuntime(network_name, network_id, guardian_id, guardian_image_id, source_digest)

    def _attest_guardian(
        self, profile: InversionSandboxProfile, endpoint: str, guardian_id: str, image_id: str
    ) -> None:
        inspected = self.docker_backend._run_endpoint(
            endpoint, ("inspect", guardian_id), timeout_seconds=5.0,
            stdout_limit_bytes=4 * 1024 * 1024, stderr_limit_bytes=16 * 1024,
        )
        if inspected.exit_code != 0 or inspected.timed_out:
            raise AuthorityViolation("InversionSandbox guardian inspect failed")
        try:
            record = json.loads(inspected.stdout)[0]
        except (json.JSONDecodeError, IndexError, TypeError) as exc:
            raise AuthorityViolation("InversionSandbox guardian inspect evidence is invalid") from exc
        host = record.get("HostConfig") or {}
        config = record.get("Config") or {}
        if record.get("Id") != guardian_id or record.get("Image") != image_id or (record.get("State") or {}).get("Status") != "created":
            raise AuthorityViolation("InversionSandbox guardian identity/state drifted")
        if config.get("User") != f"{profile.uid}:{profile.gid}":
            raise AuthorityViolation("InversionSandbox guardian user drifted")
        if host.get("ReadonlyRootfs") is not True or host.get("Privileged") is not False:
            raise AuthorityViolation("InversionSandbox guardian isolation drifted")
        if "ALL" not in {str(v).upper() for v in (host.get("CapDrop") or [])}:
            raise AuthorityViolation("InversionSandbox guardian capability drop drifted")
        if "no-new-privileges:true" not in (host.get("SecurityOpt") or []):
            raise AuthorityViolation("InversionSandbox guardian no-new-privileges drifted")
        if host.get("Devices") not in (None, []):
            raise AuthorityViolation("InversionSandbox guardian device passthrough is forbidden")

    def _start_guardian(self, profile: InversionSandboxProfile, endpoint: str, runtime: _AllowlistRuntime) -> None:
        started = self.docker_backend._run_endpoint(
            endpoint, ("start", runtime.guardian_id), timeout_seconds=10.0,
            stdout_limit_bytes=4096, stderr_limit_bytes=16 * 1024,
        )
        if started.exit_code != 0 or started.timed_out:
            raise RuntimeError("InversionSandbox guardian start failed")
        expected = f"CAPT_GUARDIAN_READY {profile.network_policy.digest()}"
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            logs = self.docker_backend._run_endpoint(
                endpoint, ("logs", runtime.guardian_id), timeout_seconds=2.0,
                stdout_limit_bytes=64 * 1024, stderr_limit_bytes=64 * 1024,
            )
            if logs.exit_code == 0 and not logs.timed_out and expected in logs.stdout.splitlines():
                return
            if "CAPT_GUARDIAN_FATAL" in (logs.stderr + logs.stdout):
                break
            time.sleep(0.05)
        raise RuntimeError("InversionSandbox guardian readiness was not proven")

    def _cleanup_allowlist_runtime(self, endpoint: str, runtime: _AllowlistRuntime) -> tuple[bool, str]:
        errors: list[str] = []
        cleaned, cleanup_error = self.docker_backend._cleanup(endpoint, runtime.guardian_id)
        if not cleaned:
            errors.append("guardian: " + cleanup_error)
        network = self.docker_backend._run_endpoint(
            endpoint, ("network", "rm", runtime.network_name), timeout_seconds=10.0,
            stdout_limit_bytes=4096, stderr_limit_bytes=16 * 1024,
        )
        if network.exit_code != 0 or network.timed_out:
            errors.append("network: " + (network.stderr or network.stdout or "remove failed")[:1024])
        return not errors, "; ".join(errors)

    def execute(
        self,
        request: DockerProcessRequest,
        *,
        prepared: InversionSandboxPreparedTarget | None = None,
        observe_effect=None,
    ) -> InversionSandboxProcessResult:
        target = prepared or self.preflight(request)
        profile = target.profile
        attestation: InversionSandboxAttestation | None = None
        enriched_identity: str | None = None
        allowlist_runtime: _AllowlistRuntime | None = None
        endpoint = target.docker.context_endpoint
        cleanup_ok = True
        cleanup_error = ""
        try:
            if profile.network_policy.mode == "allowlist":
                allowlist_runtime = self._prepare_allowlist_runtime(profile, endpoint)

            def observe(base_identity: str) -> None:
                nonlocal attestation, enriched_identity
                base = json.loads(base_identity)
                container_id = base["containerId"]
                try:
                    inspected = self.docker_backend._run_endpoint(
                        endpoint, ("inspect", container_id), timeout_seconds=5.0,
                        stdout_limit_bytes=4 * 1024 * 1024, stderr_limit_bytes=16 * 1024,
                    )
                    if inspected.exit_code != 0 or inspected.timed_out:
                        raise AuthorityViolation("InversionSandbox could not re-inspect created container")
                    record = json.loads(inspected.stdout)[0]
                    attestation = attest_created_container(
                        profile, target.docker, record,
                        expected_network_name=(allowlist_runtime.network_name if allowlist_runtime else None),
                    )
                    enriched_identity = self.effect_identity(
                        target.docker, profile, container_id, base["containerCwd"], attestation,
                        allowlist_runtime=allowlist_runtime,
                    )
                    if observe_effect is not None:
                        observe_effect(enriched_identity)
                    if allowlist_runtime is not None:
                        self._start_guardian(profile, endpoint, allowlist_runtime)
                except Exception:
                    self.docker_backend._cleanup(endpoint, container_id)
                    raise

            docker_result = self.docker_backend.execute(
                request, prepared=target.docker, observe_effect=observe,
                network_mode_override=(allowlist_runtime.network_name if allowlist_runtime else None),
            )
        finally:
            if allowlist_runtime is not None:
                cleanup_ok, cleanup_error = self._cleanup_allowlist_runtime(endpoint, allowlist_runtime)

        if not cleanup_ok:
            prior = docker_result.control_error
            message = "InversionSandbox allowlist cleanup failed: " + cleanup_error
            docker_result = replace(
                docker_result, cleanup_succeeded=False,
                cleanup_error=(docker_result.cleanup_error + "; " + cleanup_error).strip("; "),
                control_error=(prior + "; " + message).strip("; "),
            )
        return InversionSandboxProcessResult(
            docker=docker_result, attestation=attestation, side_effect_identity=enriched_identity
        )
