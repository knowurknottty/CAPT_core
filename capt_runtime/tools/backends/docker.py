"""Governed local-Docker backend with immutable image and container identity.

Initial release constraints are deliberately narrow:
- named profiles only;
- local unix-socket Docker endpoints only;
- no implicit image pulls;
- no Docker socket passthrough;
- network is either `none` or explicitly unrestricted `bridge`;
- bounded resources/log storage and cleanup_policy=always.
"""
from __future__ import annotations

import json
import math
import os
import posixpath
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.local import LocalProcessBackend, LocalProcessRequest

MAX_DOCKER_CAPTURE_BYTES = 4 * 1024 * 1024
MAX_DOCKER_CONTROL_BYTES = 4 * 1024 * 1024
MIN_MEMORY_BYTES = 64 * 1024 * 1024
MAX_MEMORY_BYTES = 128 * 1024 * 1024 * 1024
_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CONTEXT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_CONTAINER_ID_RE = re.compile(r"^[0-9a-f]{12,64}$")
_IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _safe_cli_env() -> dict[str, str]:
    allowed = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
    return {key: os.environ[key] for key in allowed if key in os.environ}


def _docker_executable() -> str:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is unavailable")
    return docker


def docker_context_endpoint(context_name: str) -> str:
    if not _CONTEXT_RE.fullmatch(context_name):
        raise ValueError("invalid Docker context name")
    completed = subprocess.run(
        [
            _docker_executable(),
            "context",
            "inspect",
            context_name,
            "--format",
            "{{json .Endpoints.docker.Host}}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_safe_cli_env(),
        timeout=5,
        shell=False,
        check=False,
    )
    if completed.returncode != 0:
        raise AuthorityViolation(
            "Docker context is unavailable: " + completed.stderr.strip()[:512]
        )
    try:
        endpoint = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("Docker context returned invalid endpoint JSON") from exc
    if not isinstance(endpoint, str) or not endpoint:
        raise RuntimeError("Docker context returned empty endpoint")
    return endpoint


def _container_path(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value or "," in value:
        raise AuthorityViolation(f"{name} must be an absolute POSIX path without NUL/comma")
    normalized = posixpath.normpath(value)
    if not normalized.startswith("/"):
        raise AuthorityViolation(f"{name} must be absolute")
    return normalized


def _within_posix(root: str, candidate: str) -> bool:
    root = root.rstrip("/") or "/"
    candidate = candidate.rstrip("/") or "/"
    return candidate == root or root == "/" or candidate.startswith(root + "/")


def _within_host(root: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath((str(root), str(candidate))) == str(root)
    except ValueError:
        return False


def _looks_like_docker_socket(path: Path | str) -> bool:
    text = str(path)
    normalized = text.rstrip("/")
    return (
        normalized.endswith("/docker.sock")
        or normalized.endswith("/.docker/run/docker.sock")
        or normalized in {"/var/run/docker.sock", "/run/docker.sock"}
    )


@dataclass(frozen=True)
class DockerMount:
    host_path: Path
    container_path: str
    mode: str
    recursive: bool = True

    def __post_init__(self) -> None:
        raw = Path(self.host_path)
        if not raw.is_absolute():
            raise AuthorityViolation("Docker mount host path must be absolute")
        if _looks_like_docker_socket(raw):
            raise AuthorityViolation("Docker socket passthrough is denied by default")
        if not raw.exists():
            raise AuthorityViolation(f"Docker mount host path does not exist: {raw}")
        canonical = raw.resolve(strict=True)
        if _looks_like_docker_socket(canonical):
            raise AuthorityViolation("Docker socket passthrough is denied by default")
        try:
            if stat.S_ISSOCK(canonical.stat().st_mode):
                raise AuthorityViolation("Docker socket/Unix-socket passthrough is denied by default")
        except FileNotFoundError as exc:
            raise AuthorityViolation("Docker mount host path disappeared during validation") from exc
        container = _container_path(self.container_path, "Docker mount container path")
        if _looks_like_docker_socket(container):
            raise AuthorityViolation("Docker socket passthrough is denied by default")
        if self.mode not in {"ro", "rw"}:
            raise ValueError("Docker mount mode must be ro or rw")
        if self.recursive is not True:
            raise ValueError("initial Docker release supports recursive bind mounts only")
        if "," in str(canonical):
            raise AuthorityViolation("Docker bind mount host path containing comma is unsupported")
        object.__setattr__(self, "host_path", canonical)
        object.__setattr__(self, "container_path", container)


@dataclass(frozen=True)
class DockerNetworkPolicy:
    mode: str = "none"
    unrestricted_egress: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"none", "bridge"}:
            raise ValueError("Docker network mode must be none or bridge in the initial release")
        if self.mode == "none" and self.unrestricted_egress:
            raise ValueError("Docker network mode none cannot claim unrestricted egress")
        if self.mode == "bridge" and not self.unrestricted_egress:
            raise ValueError("Docker bridge requires explicitly unrestricted egress")


@dataclass(frozen=True)
class DockerProfile:
    profile_id: str
    context_name: str
    image_ref: str
    allowed_host_roots: Tuple[Path, ...] = ()
    mounts: Tuple[DockerMount, ...] = ()
    allowed_container_roots: Tuple[str, ...] = ("/workspace",)
    working_dir: str = "/workspace"
    environment_overrides: Tuple[Tuple[str, str], ...] = ()
    cpus: float = 1.0
    memory_bytes: int = 512 * 1024 * 1024
    pids_limit: int = 256
    network_policy: DockerNetworkPolicy = DockerNetworkPolicy()
    cleanup_policy: str = "always"
    read_only_rootfs: bool = False
    log_max_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        if not _PROFILE_RE.fullmatch(self.profile_id):
            raise ValueError("invalid Docker profile id")
        if not _CONTEXT_RE.fullmatch(self.context_name):
            raise ValueError("invalid Docker context name")
        if (
            not isinstance(self.image_ref, str)
            or not self.image_ref
            or self.image_ref.startswith("-")
            or any(ch.isspace() or ord(ch) < 32 for ch in self.image_ref)
        ):
            raise ValueError("invalid Docker image_ref")
        roots: list[Path] = []
        for root in self.allowed_host_roots:
            path = Path(root)
            if not path.is_absolute() or not path.exists():
                raise AuthorityViolation("Docker allowed host roots must be existing absolute paths")
            roots.append(path.resolve(strict=True))
        object.__setattr__(self, "allowed_host_roots", tuple(roots))

        container_roots = tuple(
            _container_path(root, "Docker allowed container root")
            for root in self.allowed_container_roots
        )
        if not container_roots:
            raise ValueError("Docker profile requires at least one allowed container root")
        object.__setattr__(self, "allowed_container_roots", container_roots)
        working_dir = _container_path(self.working_dir, "Docker working_dir")
        if not any(_within_posix(root, working_dir) for root in container_roots):
            raise AuthorityViolation("Docker working_dir is outside allowed container roots")
        object.__setattr__(self, "working_dir", working_dir)

        for mount in self.mounts:
            if not any(_within_host(root, mount.host_path) for root in roots):
                raise AuthorityViolation("Docker mount is outside profile allowed host roots")
            if not any(_within_posix(root, mount.container_path) for root in container_roots):
                raise AuthorityViolation("Docker mount target is outside allowed container roots")

        seen_env: set[str] = set()
        for key, value in self.environment_overrides:
            if not _ENV_RE.fullmatch(key):
                raise ValueError(f"invalid Docker environment key: {key!r}")
            if key in seen_env:
                raise ValueError(f"duplicate Docker environment key: {key}")
            if not isinstance(value, str) or "\x00" in value or "\n" in value or "\r" in value:
                raise ValueError(f"invalid Docker environment value for {key}")
            seen_env.add(key)

        if isinstance(self.cpus, bool) or not isinstance(self.cpus, (int, float)) or not (0.1 <= float(self.cpus) <= 128.0):
            raise ValueError("Docker cpus must be in [0.1, 128]")
        if isinstance(self.memory_bytes, bool) or not isinstance(self.memory_bytes, int) or not (MIN_MEMORY_BYTES <= self.memory_bytes <= MAX_MEMORY_BYTES):
            raise ValueError(f"Docker memory_bytes must be in [{MIN_MEMORY_BYTES}, {MAX_MEMORY_BYTES}]")
        if isinstance(self.pids_limit, bool) or not isinstance(self.pids_limit, int) or not (16 <= self.pids_limit <= 32768):
            raise ValueError("Docker pids_limit must be in [16, 32768]")
        if self.cleanup_policy != "always":
            raise ValueError("initial Docker cleanup_policy must be always")
        if not isinstance(self.read_only_rootfs, bool):
            raise ValueError("Docker read_only_rootfs must be boolean")
        if not isinstance(self.log_max_bytes, int) or not (1024 * 1024 <= self.log_max_bytes <= 64 * 1024 * 1024):
            raise ValueError("Docker log_max_bytes must be in [1 MiB, 64 MiB]")


class DockerProfileRegistry:
    def __init__(self, profiles: Iterable[DockerProfile] = ()) -> None:
        self._profiles: dict[str, DockerProfile] = {}
        for profile in profiles:
            self.register(profile)

    def register(self, profile: DockerProfile) -> None:
        if profile.profile_id in self._profiles:
            raise ValueError(f"duplicate Docker profile id: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile

    def require(self, profile_id: str) -> DockerProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise AuthorityViolation(f"unknown Docker profile: {profile_id}") from exc

    def __len__(self) -> int:
        return len(self._profiles)

    def values(self) -> tuple[DockerProfile, ...]:
        return tuple(self._profiles.values())


@dataclass(frozen=True)
class DockerProcessRequest:
    profile_id: str
    argv: Tuple[str, ...]
    cwd: str
    filesystem_root: str
    timeout_seconds: float = 30.0
    stdout_limit_bytes: int = 1024 * 1024
    stderr_limit_bytes: int = 1024 * 1024
    terminate_grace_seconds: float = 1.0


@dataclass(frozen=True)
class DockerPreparedTarget:
    profile: DockerProfile
    context_endpoint: str
    image_id: str
    repo_digest: Optional[str]


@dataclass(frozen=True)
class DockerProcessResult:
    exit_code: Optional[int]
    stdout: str
    stderr: str
    stdout_total_bytes: int
    stderr_total_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    profile_id: str
    image_id: str
    repo_digest: Optional[str]
    container_id: str
    container_cwd: str
    cleanup_succeeded: bool
    cleanup_error: str = ""
    control_error: str = ""


def _validate_process_request(
    request: DockerProcessRequest, profile: DockerProfile
) -> tuple[str, str]:
    if not request.argv or len(request.argv) > 1024:
        raise ValueError("Docker argv must contain 1..1024 elements")
    if not all(isinstance(arg, str) and arg and "\x00" not in arg for arg in request.argv):
        raise ValueError("Docker argv elements must be non-empty strings without NUL")
    if sum(len(arg.encode("utf-8")) for arg in request.argv) > 65536:
        raise ValueError("Docker argv exceeds 65536 encoded bytes")
    root = _container_path(request.filesystem_root, "Docker filesystem_root")
    cwd = _container_path(request.cwd, "Docker cwd")
    if not any(_within_posix(allowed, root) for allowed in profile.allowed_container_roots):
        raise AuthorityViolation("Docker filesystem scope is outside profile allowed container roots")
    if not _within_posix(root, cwd):
        raise AuthorityViolation("Docker cwd is outside admitted filesystem scope")
    if request.timeout_seconds <= 0 or request.timeout_seconds > 3600:
        raise ValueError("Docker timeout_seconds must be in (0, 3600]")
    if request.terminate_grace_seconds < 0 or request.terminate_grace_seconds > 10:
        raise ValueError("Docker terminate_grace_seconds must be in [0, 10]")
    for name, value in (
        ("stdout_limit_bytes", request.stdout_limit_bytes),
        ("stderr_limit_bytes", request.stderr_limit_bytes),
    ):
        if value < 0 or value > MAX_DOCKER_CAPTURE_BYTES:
            raise ValueError(f"{name} must be in [0, {MAX_DOCKER_CAPTURE_BYTES}]")
    return root, cwd


class DockerProcessBackend:
    backend_id = "docker"
    adapter_id = "backend-docker-process"

    def __init__(
        self,
        profiles: DockerProfileRegistry,
        local_backend: LocalProcessBackend | None = None,
    ) -> None:
        self.profiles = profiles
        self.local_backend = local_backend or LocalProcessBackend()
        self.docker = shutil.which("docker")

    def _run_endpoint(
        self,
        endpoint: str,
        args: tuple[str, ...],
        *,
        timeout_seconds: float = 10.0,
        stdout_limit_bytes: int = MAX_DOCKER_CONTROL_BYTES,
        stderr_limit_bytes: int = MAX_DOCKER_CONTROL_BYTES,
    ):
        if not self.docker:
            raise RuntimeError("Docker CLI is unavailable")
        return self.local_backend.execute(
            LocalProcessRequest(
                argv=(self.docker, "--host", endpoint, *args),
                cwd=Path("/"),
                filesystem_root=Path("/"),
                timeout_seconds=timeout_seconds,
                stdout_limit_bytes=stdout_limit_bytes,
                stderr_limit_bytes=stderr_limit_bytes,
            )
        )

    def readiness(self) -> dict[str, object]:
        if not self.docker:
            return {"status": "unavailable", "reason": "Docker CLI unavailable"}
        if len(self.profiles) == 0:
            return {"status": "unavailable", "reason": "no named Docker profiles configured"}
        reasons: list[str] = []
        for profile in self.profiles.values():
            try:
                endpoint = docker_context_endpoint(profile.context_name)
                if not endpoint.startswith("unix://"):
                    reasons.append(f"{profile.profile_id}: remote Docker context denied")
                    continue
                info = self._run_endpoint(
                    endpoint,
                    ("info", "--format", "{{.ServerVersion}}"),
                    timeout_seconds=3.0,
                    stdout_limit_bytes=4096,
                    stderr_limit_bytes=4096,
                )
                if info.exit_code == 0 and not info.timed_out:
                    return {
                        "status": "available",
                        "reason": "local Docker daemon reachable for named profile",
                    }
                reasons.append(f"{profile.profile_id}: Docker daemon unavailable")
            except Exception as exc:
                reasons.append(f"{profile.profile_id}: {type(exc).__name__}")
        return {
            "status": "unavailable",
            "reason": "; ".join(reasons)[:1024] or "no usable Docker profile",
        }

    def preflight(self, request: DockerProcessRequest) -> DockerPreparedTarget:
        profile = self.profiles.require(request.profile_id)
        _validate_process_request(request, profile)
        endpoint = docker_context_endpoint(profile.context_name)
        if not endpoint.startswith("unix://"):
            raise AuthorityViolation(
                "initial Docker release admits local unix-socket contexts only"
            )
        socket_path = Path(endpoint[len("unix://") :])
        if not socket_path.is_absolute():
            raise AuthorityViolation("Docker unix endpoint must be absolute")
        socket_canonical = socket_path.resolve(strict=False)
        for mount in profile.mounts:
            if mount.host_path == socket_canonical or _looks_like_docker_socket(mount.host_path):
                raise AuthorityViolation("Docker socket passthrough is denied by default")

        info = self._run_endpoint(
            endpoint,
            ("info", "--format", "{{.ServerVersion}}"),
            timeout_seconds=5.0,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=4096,
        )
        if info.exit_code != 0 or info.timed_out:
            raise RuntimeError("Docker daemon is unavailable for configured local context")
        image = self._run_endpoint(
            endpoint,
            ("image", "inspect", profile.image_ref),
            timeout_seconds=10.0,
            stdout_limit_bytes=MAX_DOCKER_CONTROL_BYTES,
            stderr_limit_bytes=64 * 1024,
        )
        if image.exit_code != 0 or image.timed_out:
            raise AuthorityViolation(
                "approved Docker image is unavailable locally; implicit pull is disabled"
            )
        try:
            decoded = json.loads(image.stdout)
            record = decoded[0]
            image_id = record["Id"]
        except (json.JSONDecodeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("Docker image inspect returned invalid identity data") from exc
        if not isinstance(image_id, str) or not _IMAGE_ID_RE.fullmatch(image_id):
            raise RuntimeError("Docker image inspect returned non-immutable image identity")
        repo_digests = record.get("RepoDigests") or []
        repo_digest = next(
            (
                value
                for value in sorted(repo_digests)
                if isinstance(value, str) and "@sha256:" in value
            ),
            None,
        )
        return DockerPreparedTarget(
            profile=profile,
            context_endpoint=endpoint,
            image_id=image_id,
            repo_digest=repo_digest,
        )

    def effect_identity(
        self, prepared: DockerPreparedTarget, container_id: str, cwd: str
    ) -> str:
        return json.dumps(
            {
                "backend": "docker",
                "profileId": prepared.profile.profile_id,
                "contextEndpoint": prepared.context_endpoint,
                "containerId": container_id,
                "imageId": prepared.image_id,
                "repoDigest": prepared.repo_digest,
                "containerCwd": cwd,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _cleanup(self, endpoint: str, container_id: str) -> tuple[bool, str]:
        cleaned = self._run_endpoint(
            endpoint,
            ("rm", "-f", container_id),
            timeout_seconds=10.0,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=16 * 1024,
        )
        if cleaned.exit_code == 0 and not cleaned.timed_out:
            return True, ""
        return False, (cleaned.stderr or cleaned.stdout or "Docker cleanup failed")[:4096]

    def execute(
        self,
        request: DockerProcessRequest,
        *,
        prepared: DockerPreparedTarget | None = None,
        observe_effect: Callable[[str], None] | None = None,
    ) -> DockerProcessResult:
        prepared = prepared or self.preflight(request)
        profile = prepared.profile
        if profile.profile_id != request.profile_id:
            raise AuthorityViolation("Docker prepared profile does not match request")
        root, cwd = _validate_process_request(request, profile)
        current_endpoint = docker_context_endpoint(profile.context_name)
        if current_endpoint != prepared.context_endpoint:
            raise RuntimeError("Docker context endpoint changed after preflight")

        create_args: list[str] = [
            "create",
            "--pull",
            "never",
            "--network",
            profile.network_policy.mode,
            "--cpus",
            str(float(profile.cpus)),
            "--memory",
            str(profile.memory_bytes),
            "--pids-limit",
            str(profile.pids_limit),
            "--log-driver",
            "json-file",
            "--log-opt",
            f"max-size={profile.log_max_bytes}",
            "--log-opt",
            "max-file=1",
            "--workdir",
            cwd,
        ]
        if profile.read_only_rootfs:
            create_args.append("--read-only")
        for key, value in profile.environment_overrides:
            create_args.extend(("--env", f"{key}={value}"))
        for mount in profile.mounts:
            mount_spec = (
                f"type=bind,src={mount.host_path},dst={mount.container_path}"
                + (",readonly" if mount.mode == "ro" else "")
            )
            create_args.extend(("--mount", mount_spec))
        create_args.append(prepared.image_id)
        create_args.extend(request.argv)

        created = self._run_endpoint(
            prepared.context_endpoint,
            tuple(create_args),
            timeout_seconds=15.0,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=64 * 1024,
        )
        if created.exit_code != 0 or created.timed_out:
            return DockerProcessResult(
                exit_code=None,
                stdout="",
                stderr=created.stderr,
                stdout_total_bytes=0,
                stderr_total_bytes=created.stderr_total_bytes,
                stdout_truncated=False,
                stderr_truncated=created.stderr_truncated,
                timed_out=created.timed_out,
                profile_id=profile.profile_id,
                image_id=prepared.image_id,
                repo_digest=prepared.repo_digest,
                container_id="",
                container_cwd=cwd,
                cleanup_succeeded=True,
                control_error="docker create failed before container identity was returned",
            )
        container_id = created.stdout.strip()
        if not _CONTAINER_ID_RE.fullmatch(container_id):
            raise RuntimeError("docker create returned invalid container identity")

        created_inspect = self._run_endpoint(
            prepared.context_endpoint,
            ("inspect", container_id),
            timeout_seconds=5.0,
            stdout_limit_bytes=MAX_DOCKER_CONTROL_BYTES,
            stderr_limit_bytes=16 * 1024,
        )
        if created_inspect.exit_code != 0 or created_inspect.timed_out:
            cleanup_ok, cleanup_error = self._cleanup(prepared.context_endpoint, container_id)
            raise RuntimeError(
                "Docker could not verify created container identity before start; cleanup="
                f"{cleanup_ok} {cleanup_error}"
            )
        try:
            created_record = json.loads(created_inspect.stdout)[0]
        except (json.JSONDecodeError, IndexError, TypeError) as exc:
            cleanup_ok, cleanup_error = self._cleanup(prepared.context_endpoint, container_id)
            raise RuntimeError(
                "Docker created-container inspect returned invalid JSON; cleanup="
                f"{cleanup_ok} {cleanup_error}"
            ) from exc
        if created_record.get("Id") != container_id or created_record.get("Image") != prepared.image_id:
            cleanup_ok, cleanup_error = self._cleanup(prepared.context_endpoint, container_id)
            raise RuntimeError(
                "Docker created container does not match immutable prepared identity; cleanup="
                f"{cleanup_ok} {cleanup_error}"
            )
        if (created_record.get("State") or {}).get("Status") != "created":
            cleanup_ok, cleanup_error = self._cleanup(prepared.context_endpoint, container_id)
            raise RuntimeError(
                "Docker container was not in created state before effect observation; cleanup="
                f"{cleanup_ok} {cleanup_error}"
            )

        identity = self.effect_identity(prepared, container_id, cwd)
        if len(identity) > 2048:
            cleanup_ok, cleanup_error = self._cleanup(prepared.context_endpoint, container_id)
            raise RuntimeError(
                "Docker side-effect identity exceeds ToolExecution bound; cleanup="
                f"{cleanup_ok} {cleanup_error}"
            )
        if observe_effect is not None:
            observe_effect(identity)

        exit_code: Optional[int] = None
        timed_out = False
        stdout = ""
        stderr = ""
        stdout_total = 0
        stderr_total = 0
        stdout_truncated = False
        stderr_truncated = False
        control_error = ""
        cleanup_succeeded = False
        cleanup_error = ""
        try:
            started = self._run_endpoint(
                prepared.context_endpoint,
                ("start", container_id),
                timeout_seconds=10.0,
                stdout_limit_bytes=4096,
                stderr_limit_bytes=64 * 1024,
            )
            if started.exit_code != 0 or started.timed_out:
                control_error = "docker start failed: " + (started.stderr or started.stdout)[:2048]
            else:
                waited = self._run_endpoint(
                    prepared.context_endpoint,
                    ("wait", container_id),
                    timeout_seconds=request.timeout_seconds,
                    stdout_limit_bytes=4096,
                    stderr_limit_bytes=16 * 1024,
                )
                if waited.timed_out:
                    timed_out = True
                    grace = max(0, int(math.ceil(request.terminate_grace_seconds)))
                    stopped = self._run_endpoint(
                        prepared.context_endpoint,
                        ("stop", "--timeout", str(grace), container_id),
                        timeout_seconds=max(request.terminate_grace_seconds + 5.0, 5.0),
                        stdout_limit_bytes=4096,
                        stderr_limit_bytes=16 * 1024,
                    )
                    if stopped.exit_code != 0 or stopped.timed_out:
                        killed = self._run_endpoint(
                            prepared.context_endpoint,
                            ("kill", container_id),
                            timeout_seconds=5.0,
                            stdout_limit_bytes=4096,
                            stderr_limit_bytes=16 * 1024,
                        )
                        if killed.exit_code != 0 or killed.timed_out:
                            control_error = "Docker timeout termination could not prove container stopped"
                elif waited.exit_code != 0:
                    control_error = "docker wait failed: " + (waited.stderr or waited.stdout)[:2048]

            state = self._run_endpoint(
                prepared.context_endpoint,
                ("inspect", "--format", "{{json .State}}", container_id),
                timeout_seconds=5.0,
                stdout_limit_bytes=64 * 1024,
                stderr_limit_bytes=16 * 1024,
            )
            if state.exit_code == 0 and not state.timed_out:
                try:
                    state_data = json.loads(state.stdout.strip())
                    if state_data.get("Running"):
                        control_error = control_error or "Docker container remained running after wait/termination"
                    raw_exit = state_data.get("ExitCode")
                    if isinstance(raw_exit, int):
                        exit_code = raw_exit
                except json.JSONDecodeError:
                    control_error = control_error or "Docker state inspect returned invalid JSON"
            else:
                control_error = control_error or "Docker state inspect failed after execution"

            logs = self._run_endpoint(
                prepared.context_endpoint,
                ("logs", container_id),
                timeout_seconds=10.0,
                stdout_limit_bytes=request.stdout_limit_bytes,
                stderr_limit_bytes=request.stderr_limit_bytes,
            )
            if logs.exit_code != 0 or logs.timed_out:
                control_error = control_error or "Docker logs could not be retrieved deterministically"
            else:
                stdout = logs.stdout
                stderr = logs.stderr
                stdout_total = logs.stdout_total_bytes
                stderr_total = logs.stderr_total_bytes
                stdout_truncated = logs.stdout_truncated
                stderr_truncated = logs.stderr_truncated
        finally:
            cleanup_succeeded, cleanup_error = self._cleanup(
                prepared.context_endpoint, container_id
            )

        return DockerProcessResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            stdout_total_bytes=stdout_total,
            stderr_total_bytes=stderr_total,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            timed_out=timed_out,
            profile_id=profile.profile_id,
            image_id=prepared.image_id,
            repo_digest=prepared.repo_digest,
            container_id=container_id,
            container_cwd=cwd,
            cleanup_succeeded=cleanup_succeeded,
            cleanup_error=cleanup_error,
            control_error=control_error,
        )
