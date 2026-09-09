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
from typing import Any, Callable, Iterable

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
    _validate_process_request,
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
    persistent_entrypoint_argv: tuple[str, ...] | None = None
    default_ttl_seconds: int = 1800
    max_ttl_seconds: int = 1800

    def __post_init__(self) -> None:
        for name, value in (("uid", self.uid), ("gid", self.gid)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > 2_147_483_647:
                raise AuthorityViolation(f"InversionSandbox requires non-root numeric {name}")
        if self.network_policy.mode == "unrestricted" and not self.allow_unrestricted_egress:
            raise AuthorityViolation("InversionSandbox unrestricted egress requires operator profile opt-in")
        if self.network_policy.mode == "allowlist" and not self.guardian_image_ref:
            raise AuthorityViolation("InversionSandbox allowlist requires an explicit guardian image")
        if self.persistent_entrypoint_argv is not None:
            if not self.persistent_entrypoint_argv:
                raise AuthorityViolation("InversionSandbox persistent entrypoint must not be empty")
            if len(self.persistent_entrypoint_argv) > 1024 or not all(
                isinstance(arg, str) and arg and "\x00" not in arg
                for arg in self.persistent_entrypoint_argv
            ):
                raise AuthorityViolation("InversionSandbox persistent entrypoint argv is invalid")
            if sum(len(arg.encode("utf-8")) for arg in self.persistent_entrypoint_argv) > 65536:
                raise AuthorityViolation("InversionSandbox persistent entrypoint exceeds 65536 bytes")
        for name, value in (("default_ttl_seconds", self.default_ttl_seconds), ("max_ttl_seconds", self.max_ttl_seconds)):
            if isinstance(value, bool) or not isinstance(value, int) or not (1 <= value <= 86400):
                raise AuthorityViolation(f"InversionSandbox {name} TTL must be in [1, 86400]")
        if self.default_ttl_seconds > self.max_ttl_seconds:
            raise AuthorityViolation("InversionSandbox default TTL cannot exceed max TTL")
        self.docker_profile()

    def profile_digest(self) -> str:
        material = {
            "profileId": self.profile_id,
            "contextName": self.context_name,
            "imageRef": self.image_ref,
            "allowedHostRoots": [str(path) for path in self.allowed_host_roots],
            "mounts": [
                {"host": str(m.host_path), "container": m.container_path, "mode": m.mode}
                for m in self.mounts
            ],
            "allowedContainerRoots": list(self.allowed_container_roots),
            "workingDir": self.working_dir,
            "environment": list(self.environment_overrides),
            "cpus": float(self.cpus),
            "memoryBytes": self.memory_bytes,
            "pidsLimit": self.pids_limit,
            "logMaxBytes": self.log_max_bytes,
            "uid": self.uid,
            "gid": self.gid,
            "tmpfsBytes": self.tmpfs_bytes,
            "networkPolicy": self.network_policy.canonical(),
            "allowUnrestrictedEgress": self.allow_unrestricted_egress,
            "guardianImageRef": self.guardian_image_ref,
            "guardianPython": self.guardian_python,
            "persistentEntrypointArgv": list(self.persistent_entrypoint_argv) if self.persistent_entrypoint_argv is not None else None,
            "defaultTtlSeconds": self.default_ttl_seconds,
            "maxTtlSeconds": self.max_ttl_seconds,
        }
        return "sha256:" + _digest(material)

    def persistent_entrypoint_digest(self) -> str:
        if self.persistent_entrypoint_argv is None:
            raise AuthorityViolation("InversionSandbox profile is not persistent-capable")
        return "sha256:" + _digest(list(self.persistent_entrypoint_argv))

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
class SandboxRuntimeIdentity:
    sandbox_lease_id: str
    profile_id: str
    profile_digest: str
    context_endpoint: str
    daemon_identity_digest: str
    workload_container_id: str
    workload_image_id: str
    security_profile_digest: str
    network_policy_digest: str
    filesystem_scope_digest: str
    persistent_entrypoint_digest: str
    creation_attestation_digest: str
    guardian_container_id: str | None = None
    guardian_image_id: str | None = None
    internal_network_name: str | None = None
    internal_network_id: str | None = None

    def canonical(self) -> dict[str, object]:
        return {
            "sandboxLeaseId": self.sandbox_lease_id,
            "profileId": self.profile_id,
            "profileDigest": self.profile_digest,
            "contextEndpoint": self.context_endpoint,
            "daemonIdentityDigest": self.daemon_identity_digest,
            "workloadContainerId": self.workload_container_id,
            "workloadImageId": self.workload_image_id,
            "securityProfileDigest": self.security_profile_digest,
            "networkPolicyDigest": self.network_policy_digest,
            "filesystemScopeDigest": self.filesystem_scope_digest,
            "persistentEntrypointDigest": self.persistent_entrypoint_digest,
            "creationAttestationDigest": self.creation_attestation_digest,
            "guardianContainerId": self.guardian_container_id,
            "guardianImageId": self.guardian_image_id,
            "internalNetworkName": self.internal_network_name,
            "internalNetworkId": self.internal_network_id,
        }

    def digest(self) -> str:
        return "sha256:" + _digest(self.canonical())


@dataclass(frozen=True)
class PersistentSandboxExecResult:
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_total_bytes: int
    stderr_total_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    termination_proven: bool
    observation_digest: str


@dataclass(frozen=True)
class PersistentSandboxCloseResult:
    cleanup_succeeded: bool
    closure_receipt_digest: str
    cleanup_error: str = ""


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

    @staticmethod
    def _contract_digest(value: str) -> str:
        return value if value.startswith("sha256:") else "sha256:" + value

    def _daemon_identity_digest(self, endpoint: str) -> str:
        info = self.docker_backend._run_endpoint(
            endpoint,
            ("info", "--format", "{{json .ID}}"),
            timeout_seconds=3.0,
            stdout_limit_bytes=8192,
            stderr_limit_bytes=8192,
        )
        if info.exit_code != 0 or info.timed_out:
            raise AuthorityViolation("InversionSandbox could not prove Docker daemon identity")
        try:
            daemon_id = json.loads(info.stdout)
        except json.JSONDecodeError as exc:
            raise AuthorityViolation("InversionSandbox Docker daemon identity is invalid") from exc
        if not isinstance(daemon_id, str) or not daemon_id.strip():
            raise AuthorityViolation("InversionSandbox Docker daemon identity is empty")
        return "sha256:" + _digest({"endpoint": endpoint, "daemonId": daemon_id})

    def persistent_labels(
        self,
        sandbox_lease_id: str,
        profile: InversionSandboxProfile,
        prepared: InversionSandboxPreparedTarget,
    ) -> dict[str, str]:
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", sandbox_lease_id):
            raise AuthorityViolation("InversionSandbox sandbox lease id is invalid")
        if prepared.profile.profile_id != profile.profile_id:
            raise AuthorityViolation("InversionSandbox prepared profile identity drifted")
        return {
            "capt.sandboxLeaseId": sandbox_lease_id,
            "capt.profileId": profile.profile_id,
            "capt.profileDigest": profile.profile_digest(),
            "capt.securityProfileDigest": self._contract_digest(profile.security_profile_digest()),
            "capt.networkPolicyDigest": self._contract_digest(profile.network_policy.digest()),
            "capt.filesystemScopeDigest": self._contract_digest(profile.filesystem_scope_digest()),
            "capt.persistentEntrypointDigest": profile.persistent_entrypoint_digest(),
        }

    def _persistent_prepared_from_identity(
        self, identity: SandboxRuntimeIdentity
    ) -> tuple[InversionSandboxProfile, DockerPreparedTarget]:
        profile = self.profiles.require(identity.profile_id)
        if profile.persistent_entrypoint_argv is None:
            raise AuthorityViolation("InversionSandbox profile is not persistent-capable")
        if profile.profile_digest() != identity.profile_digest:
            raise AuthorityViolation("InversionSandbox persistent profile identity drifted")
        if self._daemon_identity_digest(identity.context_endpoint) != identity.daemon_identity_digest:
            raise AuthorityViolation("InversionSandbox persistent daemon identity drifted")
        docker_profile = self.docker_profiles.require(profile.profile_id)
        prepared = DockerPreparedTarget(
            docker_profile,
            identity.context_endpoint,
            identity.workload_image_id,
            None,
        )
        return profile, prepared

    def _verify_persistent_workload(
        self,
        identity: SandboxRuntimeIdentity,
        profile: InversionSandboxProfile,
        prepared: DockerPreparedTarget,
    ) -> dict[str, Any]:
        try:
            record = self.docker_backend._inspect_exact(
                identity.context_endpoint, identity.workload_container_id
            )
        except RuntimeError as exc:
            raise AuthorityViolation("InversionSandbox persistent workload identity is unavailable") from exc
        if record.get("Image") != identity.workload_image_id:
            raise AuthorityViolation("InversionSandbox persistent workload image identity drifted")
        expected_labels = self.persistent_labels(
            identity.sandbox_lease_id,
            profile,
            InversionSandboxPreparedTarget(profile, prepared),
        )
        labels = (record.get("Config") or {}).get("Labels") or {}
        if not isinstance(labels, dict) or any(labels.get(k) != v for k, v in expected_labels.items()):
            raise AuthorityViolation("InversionSandbox persistent workload labels drifted")
        copy = json.loads(json.dumps(record))
        copy.setdefault("State", {})["Status"] = "created"
        expected_network = identity.internal_network_name
        attest_created_container(
            profile,
            prepared,
            copy,
            expected_network_name=expected_network,
        )
        return record

    def _verify_persistent_guardian(
        self, identity: SandboxRuntimeIdentity, profile: InversionSandboxProfile
    ) -> dict[str, Any] | None:
        if profile.network_policy.mode != "allowlist":
            if any(
                value is not None
                for value in (
                    identity.guardian_container_id,
                    identity.guardian_image_id,
                    identity.internal_network_name,
                    identity.internal_network_id,
                )
            ):
                raise AuthorityViolation("InversionSandbox persistent no-network identity contains guardian state")
            return None
        if not all(
            (
                identity.guardian_container_id,
                identity.guardian_image_id,
                identity.internal_network_name,
                identity.internal_network_id,
            )
        ):
            raise AuthorityViolation("InversionSandbox persistent allowlist identity is incomplete")
        try:
            guardian = self.docker_backend._inspect_exact(
                identity.context_endpoint, str(identity.guardian_container_id)
            )
        except RuntimeError as exc:
            raise AuthorityViolation("InversionSandbox persistent guardian identity is unavailable") from exc
        if guardian.get("Image") != identity.guardian_image_id:
            raise AuthorityViolation("InversionSandbox persistent guardian image identity drifted")
        labels = (guardian.get("Config") or {}).get("Labels") or {}
        expected_labels = self.persistent_labels(
            identity.sandbox_lease_id,
            profile,
            InversionSandboxPreparedTarget(
                profile,
                DockerPreparedTarget(
                    self.docker_profiles.require(profile.profile_id),
                    identity.context_endpoint,
                    identity.workload_image_id,
                    None,
                ),
            ),
        )
        if not isinstance(labels, dict) or any(labels.get(k) != v for k, v in expected_labels.items()):
            raise AuthorityViolation("InversionSandbox persistent guardian labels drifted")
        config = guardian.get("Config") or {}
        host = guardian.get("HostConfig") or {}
        if config.get("User") != f"{profile.uid}:{profile.gid}":
            raise AuthorityViolation("InversionSandbox persistent guardian user drifted")
        if host.get("ReadonlyRootfs") is not True or host.get("Privileged") is not False:
            raise AuthorityViolation("InversionSandbox persistent guardian isolation drifted")
        if "ALL" not in {str(v).upper() for v in (host.get("CapDrop") or [])}:
            raise AuthorityViolation("InversionSandbox persistent guardian capability drop drifted")
        if "no-new-privileges:true" not in (host.get("SecurityOpt") or []):
            raise AuthorityViolation("InversionSandbox persistent guardian no-new-privileges drifted")
        networks = (guardian.get("NetworkSettings") or {}).get("Networks") or {}
        if str(identity.internal_network_name) not in networks or "bridge" not in networks:
            raise AuthorityViolation("InversionSandbox persistent guardian network topology drifted")
        network = self.docker_backend._run_endpoint(
            identity.context_endpoint,
            ("network", "inspect", str(identity.internal_network_id)),
            timeout_seconds=5.0,
            stdout_limit_bytes=4 * 1024 * 1024,
            stderr_limit_bytes=16 * 1024,
        )
        if network.exit_code != 0 or network.timed_out:
            raise AuthorityViolation("InversionSandbox persistent internal network identity is unavailable")
        try:
            network_record = json.loads(network.stdout)[0]
        except (json.JSONDecodeError, IndexError, TypeError) as exc:
            raise AuthorityViolation("InversionSandbox persistent internal network evidence is invalid") from exc
        if (
            network_record.get("Id") != identity.internal_network_id
            or network_record.get("Name") != identity.internal_network_name
            or network_record.get("Internal") is not True
        ):
            raise AuthorityViolation("InversionSandbox persistent internal network identity drifted")
        network_labels = network_record.get("Labels") or {}
        if not isinstance(network_labels, dict) or any(
            network_labels.get(k) != v for k, v in expected_labels.items()
        ):
            raise AuthorityViolation("InversionSandbox persistent internal network labels drifted")
        return guardian

    def inspect_persistent(self, identity: SandboxRuntimeIdentity) -> dict[str, Any]:
        profile, prepared = self._persistent_prepared_from_identity(identity)
        workload = self._verify_persistent_workload(identity, profile, prepared)
        guardian = self._verify_persistent_guardian(identity, profile)
        evidence = {
            "sandboxLeaseId": identity.sandbox_lease_id,
            "identityDigest": identity.digest(),
            "workloadContainerId": identity.workload_container_id,
            "workloadState": (workload.get("State") or {}).get("Status"),
            "workloadRunning": bool((workload.get("State") or {}).get("Running")),
            "guardianContainerId": identity.guardian_container_id,
            "guardianState": (guardian.get("State") or {}).get("Status") if guardian else None,
            "networkId": identity.internal_network_id,
        }
        evidence["observationDigest"] = "sha256:" + _digest(evidence)
        return evidence

    def create_persistent_stopped(
        self,
        sandbox_lease_id: str,
        request: DockerProcessRequest,
        *,
        prepared: InversionSandboxPreparedTarget | None = None,
    ) -> SandboxRuntimeIdentity:
        target = prepared or self.preflight(request)
        profile = target.profile
        if profile.persistent_entrypoint_argv is None:
            raise AuthorityViolation("InversionSandbox profile is not persistent-capable")
        if tuple(request.argv) != tuple(profile.persistent_entrypoint_argv):
            raise AuthorityViolation("InversionSandbox persistent create requires profile-owned entrypoint")
        _root, cwd = _validate_process_request(request, target.docker.profile)
        self._require_seccomp(target.docker.context_endpoint)
        self._require_local_guardian_image(profile, target.docker.context_endpoint)
        daemon_digest = self._daemon_identity_digest(target.docker.context_endpoint)
        labels = self.persistent_labels(sandbox_lease_id, profile, target)
        label_pairs = tuple(sorted(labels.items()))
        allowlist_runtime: _AllowlistRuntime | None = None
        container_id = ""
        try:
            if profile.network_policy.mode == "allowlist":
                allowlist_runtime = self._prepare_allowlist_runtime(
                    profile, target.docker.context_endpoint, labels=label_pairs
                )
            container_id, created = self.docker_backend._create_stopped(
                target.docker,
                cwd,
                tuple(profile.persistent_entrypoint_argv),
                network_mode_override=(
                    allowlist_runtime.network_name if allowlist_runtime is not None else None
                ),
                labels=label_pairs,
            )
            if created.exit_code != 0 or created.timed_out:
                raise RuntimeError("InversionSandbox persistent workload create failed")
            if not re.fullmatch(r"[0-9a-f]{64}", container_id):
                raise AuthorityViolation("InversionSandbox persistent workload requires full Docker identity")
            record = self.docker_backend._inspect_exact(
                target.docker.context_endpoint, container_id
            )
            attestation = attest_created_container(
                profile,
                target.docker,
                record,
                expected_network_name=(
                    allowlist_runtime.network_name if allowlist_runtime is not None else None
                ),
            )
            identity = SandboxRuntimeIdentity(
                sandbox_lease_id=sandbox_lease_id,
                profile_id=profile.profile_id,
                profile_digest=profile.profile_digest(),
                context_endpoint=target.docker.context_endpoint,
                daemon_identity_digest=daemon_digest,
                workload_container_id=container_id,
                workload_image_id=target.docker.image_id,
                security_profile_digest=self._contract_digest(attestation.security_profile_digest),
                network_policy_digest=self._contract_digest(attestation.network_policy_digest),
                filesystem_scope_digest=self._contract_digest(attestation.filesystem_scope_digest),
                persistent_entrypoint_digest=profile.persistent_entrypoint_digest(),
                creation_attestation_digest=self._contract_digest(attestation.digest),
                guardian_container_id=(allowlist_runtime.guardian_id if allowlist_runtime else None),
                guardian_image_id=(allowlist_runtime.guardian_image_id if allowlist_runtime else None),
                internal_network_name=(allowlist_runtime.network_name if allowlist_runtime else None),
                internal_network_id=(allowlist_runtime.network_id if allowlist_runtime else None),
            )
            return identity
        except Exception:
            if container_id:
                self.docker_backend._cleanup(target.docker.context_endpoint, container_id)
            if allowlist_runtime is not None:
                self._cleanup_allowlist_runtime(target.docker.context_endpoint, allowlist_runtime)
            raise

    def start_persistent(self, identity: SandboxRuntimeIdentity) -> dict[str, Any]:
        profile, _prepared = self._persistent_prepared_from_identity(identity)
        before = self.inspect_persistent(identity)
        if before["workloadState"] != "created":
            raise AuthorityViolation("InversionSandbox persistent workload must be created before start")
        if profile.network_policy.mode == "allowlist":
            runtime = _AllowlistRuntime(
                network_name=str(identity.internal_network_name),
                network_id=str(identity.internal_network_id),
                guardian_id=str(identity.guardian_container_id),
                guardian_image_id=str(identity.guardian_image_id),
                guardian_source_digest=hashlib.sha256(self._guardian_source().encode("utf-8")).hexdigest(),
            )
            self._start_guardian(profile, identity.context_endpoint, runtime)
        self.docker_backend._start_exact(identity.context_endpoint, identity.workload_container_id)
        after = self.inspect_persistent(identity)
        if after["workloadRunning"] is not True:
            raise RuntimeError("InversionSandbox persistent workload start was not proven")
        return after

    def exec_persistent(
        self,
        identity: SandboxRuntimeIdentity,
        *,
        argv: tuple[str, ...],
        cwd: str,
        filesystem_root: str | None = None,
        timeout_seconds: float,
        stdout_limit_bytes: int,
        stderr_limit_bytes: int,
        observe_effect: Callable[[str], None] | None = None,
    ) -> PersistentSandboxExecResult:
        profile, _prepared = self._persistent_prepared_from_identity(identity)
        observation = self.inspect_persistent(identity)
        if observation["workloadRunning"] is not True:
            raise AuthorityViolation("InversionSandbox persistent workload is not running")
        request = DockerProcessRequest(
            profile_id=profile.profile_id,
            argv=argv,
            cwd=cwd,
            filesystem_root=filesystem_root or profile.working_dir,
            timeout_seconds=timeout_seconds,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
        )
        _root, normalized_cwd = _validate_process_request(
            request, self.docker_profiles.require(profile.profile_id)
        )
        observation_digest = str(observation["observationDigest"])
        if observe_effect is not None:
            observe_effect(observation_digest)
        result = self.docker_backend._exec_exact(
            identity.context_endpoint,
            identity.workload_container_id,
            user=f"{profile.uid}:{profile.gid}",
            cwd=normalized_cwd,
            argv=tuple(argv),
            timeout_seconds=timeout_seconds,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
        )
        return PersistentSandboxExecResult(
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            stdout_total_bytes=result.stdout_total_bytes,
            stderr_total_bytes=result.stderr_total_bytes,
            stdout_truncated=result.stdout_truncated,
            stderr_truncated=result.stderr_truncated,
            timed_out=result.timed_out,
            termination_proven=not result.timed_out,
            observation_digest=observation_digest,
        )

    def _container_absent(self, endpoint: str, container_id: str) -> bool:
        result = self.docker_backend._run_endpoint(
            endpoint,
            ("inspect", container_id),
            timeout_seconds=5.0,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=16 * 1024,
        )
        if result.exit_code == 0 and not result.timed_out:
            return False
        text = (result.stderr or result.stdout or "").lower()
        return not result.timed_out and ("no such" in text or "not found" in text)

    def _network_absent(self, endpoint: str, network_id: str) -> bool:
        result = self.docker_backend._run_endpoint(
            endpoint,
            ("network", "inspect", network_id),
            timeout_seconds=5.0,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=16 * 1024,
        )
        if result.exit_code == 0 and not result.timed_out:
            return False
        text = (result.stderr or result.stdout or "").lower()
        return not result.timed_out and ("no such" in text or "not found" in text)

    def close_persistent(self, identity: SandboxRuntimeIdentity) -> PersistentSandboxCloseResult:
        _profile, _prepared = self._persistent_prepared_from_identity(identity)
        self.inspect_persistent(identity)
        errors: list[str] = []
        cleaned, cleanup_error = self.docker_backend._cleanup(
            identity.context_endpoint, identity.workload_container_id
        )
        if not cleaned:
            errors.append("workload: " + cleanup_error)
        if identity.guardian_container_id is not None:
            cleaned, cleanup_error = self.docker_backend._cleanup(
                identity.context_endpoint, identity.guardian_container_id
            )
            if not cleaned:
                errors.append("guardian: " + cleanup_error)
        if identity.internal_network_id is not None:
            removed = self.docker_backend._run_endpoint(
                identity.context_endpoint,
                ("network", "rm", identity.internal_network_id),
                timeout_seconds=10.0,
                stdout_limit_bytes=4096,
                stderr_limit_bytes=16 * 1024,
            )
            if removed.exit_code != 0 or removed.timed_out:
                errors.append("network: " + (removed.stderr or removed.stdout or "remove failed")[:1024])
        workload_absent = self._container_absent(
            identity.context_endpoint, identity.workload_container_id
        )
        guardian_absent = (
            True
            if identity.guardian_container_id is None
            else self._container_absent(identity.context_endpoint, identity.guardian_container_id)
        )
        network_absent = (
            True
            if identity.internal_network_id is None
            else self._network_absent(identity.context_endpoint, identity.internal_network_id)
        )
        if not workload_absent:
            errors.append("workload absence not proven")
        if not guardian_absent:
            errors.append("guardian absence not proven")
        if not network_absent:
            errors.append("network absence not proven")
        evidence = {
            "sandboxLeaseId": identity.sandbox_lease_id,
            "identityDigest": identity.digest(),
            "workloadAbsent": workload_absent,
            "guardianAbsent": guardian_absent,
            "networkAbsent": network_absent,
        }
        return PersistentSandboxCloseResult(
            cleanup_succeeded=not errors,
            closure_receipt_digest="sha256:" + _digest(evidence),
            cleanup_error="; ".join(errors),
        )

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
        self,
        profile: InversionSandboxProfile,
        endpoint: str,
        *,
        labels: tuple[tuple[str, str], ...] = (),
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
        network_args = ["network", "create", "--internal", "--driver", "bridge"]
        for key, value in labels:
            network_args.extend(("--label", f"{key}={value}"))
        network_args.append(network_name)
        network = self.docker_backend._run_endpoint(
            endpoint, tuple(network_args),
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
        ]
        for key, value in labels:
            args.extend(("--label", f"{key}={value}"))
        args.extend((guardian_image_id, profile.guardian_python, "-c", source))
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
