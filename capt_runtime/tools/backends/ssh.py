"""Strict named-profile OpenSSH backend for governed terminal execution.

No user command text is interpolated into SSH's shell-parsed remote command.
The fixed bootstrap receives argv/cwd as bounded JSON on stdin and executes the
argv vector with shell=False. Host identity is pinned to the CAPT profile id.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import posixpath
import re
import shutil
import socket
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.local import LocalProcessBackend, LocalProcessRequest
from capt_runtime.tools.backends.ssh_bootstrap import bootstrap_command

MAX_REMOTE_CAPTURE_BYTES = 4 * 1024 * 1024
MAX_SSH_CONTROL_BYTES = 12 * 1024 * 1024
_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_USER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")
_REMOTE_PYTHON_RE = re.compile(r"^/[A-Za-z0-9_./+@-]+$")


@dataclass(frozen=True)
class SSHNetworkPolicy:
    allowed_destination_classes: Tuple[str, ...] = ("public",)
    allowed_cidrs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        allowed = {"public", "private", "loopback", "link_local"}
        unknown = set(self.allowed_destination_classes).difference(allowed)
        if unknown:
            raise ValueError(f"unknown SSH destination classes: {sorted(unknown)!r}")
        for value in self.allowed_cidrs:
            ipaddress.ip_network(value, strict=False)


@dataclass(frozen=True)
class SSHProfile:
    profile_id: str
    hostname: str
    port: int
    username: str
    known_hosts_policy: str
    known_hosts_file: Path
    credential_ref: str
    allowed_remote_roots: Tuple[str, ...]
    network_policy: SSHNetworkPolicy
    remote_python: str = "/usr/bin/python3"

    def __post_init__(self) -> None:
        object.__setattr__(self, "known_hosts_file", Path(self.known_hosts_file))
        if not _PROFILE_RE.fullmatch(self.profile_id):
            raise ValueError("invalid SSH profile id")
        if not self.hostname or any(ch.isspace() or ord(ch) < 32 for ch in self.hostname):
            raise ValueError("invalid SSH hostname")
        if self.hostname.startswith("-"):
            raise ValueError("invalid SSH hostname")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not (1 <= self.port <= 65535):
            raise ValueError("SSH port must be in [1, 65535]")
        if not _USER_RE.fullmatch(self.username):
            raise ValueError("invalid SSH username")
        if self.known_hosts_policy != "strict_profile_alias":
            raise ValueError("initial release requires knownHostsPolicy=strict_profile_alias")
        if not self.known_hosts_file.is_absolute():
            raise ValueError("known_hosts_file must be absolute")
        if not self.allowed_remote_roots:
            raise ValueError("SSH profile requires at least one allowed remote root")
        for root in self.allowed_remote_roots:
            _remote_path(root, "allowed_remote_root")
        if not _REMOTE_PYTHON_RE.fullmatch(self.remote_python) or ".." in Path(self.remote_python).parts:
            raise ValueError("remote_python must be a restricted absolute path")


class SSHProfileRegistry:
    def __init__(self, profiles: Iterable[SSHProfile] = ()) -> None:
        self._profiles: dict[str, SSHProfile] = {}
        for profile in profiles:
            self.register(profile)

    def register(self, profile: SSHProfile) -> None:
        if profile.profile_id in self._profiles:
            raise ValueError(f"duplicate SSH profile id: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile

    def require(self, profile_id: str) -> SSHProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise AuthorityViolation(f"unknown SSH profile: {profile_id}") from exc

    def __len__(self) -> int:
        return len(self._profiles)


@dataclass(frozen=True)
class SSHProcessRequest:
    profile_id: str
    argv: Tuple[str, ...]
    cwd: str
    filesystem_root: str
    timeout_seconds: float = 30.0
    stdout_limit_bytes: int = 1024 * 1024
    stderr_limit_bytes: int = 1024 * 1024
    terminate_grace_seconds: float = 0.5


@dataclass(frozen=True)
class SSHPreparedTarget:
    profile: SSHProfile
    resolved_ip: str
    host_fingerprint: str
    identity_file: Path


@dataclass(frozen=True)
class SSHProcessResult:
    exit_code: Optional[int]
    stdout: str
    stderr: str
    stdout_total_bytes: int
    stderr_total_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    profile_id: str
    host_fingerprint: str
    remote_cwd: str
    remote_pid: int
    remote_process_group_id: int
    denied: bool = False
    denial_reason: str = ""


def openssh_sha256_fingerprint(public_key_blob_b64: str) -> str:
    try:
        blob = base64.b64decode(public_key_blob_b64.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError("invalid OpenSSH public key blob") from exc
    digest = base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
    return "SHA256:" + digest


def _remote_path(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise AuthorityViolation(f"{name} must be an absolute POSIX path")
    normalized = posixpath.normpath(value)
    if not normalized.startswith("/"):
        raise AuthorityViolation(f"{name} must be absolute")
    return normalized


def _within(root: str, candidate: str) -> bool:
    root = root.rstrip("/") or "/"
    candidate = candidate.rstrip("/") or "/"
    return candidate == root or (root != "/" and candidate.startswith(root + "/")) or root == "/"


def _address_class(address: ipaddress._BaseAddress) -> str:
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link_local"
    if address.is_private:
        return "private"
    if address.is_unspecified or address.is_multicast or address.is_reserved:
        return "forbidden"
    return "public"


def _network_allows(policy: SSHNetworkPolicy, address: ipaddress._BaseAddress) -> bool:
    for cidr in policy.allowed_cidrs:
        if address in ipaddress.ip_network(cidr, strict=False):
            return True
    return _address_class(address) in set(policy.allowed_destination_classes)


def _resolve_target(profile: SSHProfile) -> str:
    try:
        infos = socket.getaddrinfo(profile.hostname, profile.port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise AuthorityViolation(f"SSH network policy could not resolve profile target: {type(exc).__name__}") from exc
    addresses = {ipaddress.ip_address(item[4][0]) for item in infos}
    if not addresses:
        raise AuthorityViolation("SSH network policy resolved no addresses")
    denied = sorted(str(address) for address in addresses if not _network_allows(profile.network_policy, address))
    if denied:
        raise AuthorityViolation(f"SSH network policy denies resolved address(es): {', '.join(denied)}")
    chosen = sorted(addresses, key=lambda value: (value.version, value.packed))[0]
    return str(chosen)


def _resolve_identity_file(credential_ref: str) -> Path:
    prefix = "identity-file:"
    if not isinstance(credential_ref, str) or not credential_ref.startswith(prefix):
        raise AuthorityViolation("SSH credentialRef must be an identity-file: secret reference")
    path = Path(credential_ref[len(prefix):])
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise AuthorityViolation("SSH credentialRef identity file is unavailable")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise AuthorityViolation("SSH credentialRef identity file permissions are too broad")
    return path


def _known_host_fingerprints(profile: SSHProfile) -> set[str]:
    path = profile.known_hosts_file
    if not path.is_file() or path.is_symlink():
        raise AuthorityViolation("SSH strict known-hosts file is unavailable")
    keygen = shutil.which("ssh-keygen")
    if not keygen:
        raise AuthorityViolation("ssh-keygen is unavailable for strict host-key verification")
    completed = subprocess.run(
        [keygen, "-F", profile.profile_id, "-f", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
        shell=False,
        check=False,
    )
    lines = [line for line in completed.stdout.splitlines() if line and not line.startswith("#")]
    fingerprints: set[str] = set()
    for line in lines:
        fields = line.split()
        if len(fields) >= 3:
            fingerprints.add(openssh_sha256_fingerprint(fields[2]))
    if not fingerprints:
        raise AuthorityViolation(f"SSH host key check has no pinned key for profile {profile.profile_id}")
    return fingerprints


def _scan_host_fingerprints(profile: SSHProfile, resolved_ip: str) -> set[str]:
    keyscan = shutil.which("ssh-keyscan")
    if not keyscan:
        raise AuthorityViolation("ssh-keyscan is unavailable for strict host-key verification")
    completed = subprocess.run(
        [keyscan, "-T", "5", "-p", str(profile.port), "-t", "ed25519,ecdsa,rsa", resolved_ip],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=7,
        shell=False,
        check=False,
    )
    fingerprints: set[str] = set()
    for line in completed.stdout.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) >= 3:
            fingerprints.add(openssh_sha256_fingerprint(fields[2]))
    if not fingerprints:
        raise AuthorityViolation("SSH host key check could not observe a server host key")
    return fingerprints


def _validate_request(request: SSHProcessRequest, profile: SSHProfile) -> tuple[str, str]:
    if not request.argv or len(request.argv) > 1024:
        raise ValueError("SSH argv must contain 1..1024 elements")
    if not all(isinstance(arg, str) and arg and "\x00" not in arg for arg in request.argv):
        raise ValueError("SSH argv elements must be non-empty strings without NUL")
    if sum(len(arg.encode("utf-8")) for arg in request.argv) > 65536:
        raise ValueError("SSH argv exceeds 65536 encoded bytes")
    root = _remote_path(request.filesystem_root, "filesystem_root")
    cwd = _remote_path(request.cwd, "cwd")
    if not any(_within(_remote_path(allowed, "allowed_remote_root"), root) for allowed in profile.allowed_remote_roots):
        raise AuthorityViolation("SSH filesystem scope is outside profile allowedRemoteRoots")
    if not _within(root, cwd):
        raise AuthorityViolation("SSH cwd is outside admitted filesystem scope")
    if request.timeout_seconds <= 0 or request.timeout_seconds > 3600:
        raise ValueError("SSH timeout_seconds must be in (0, 3600]")
    if request.terminate_grace_seconds < 0 or request.terminate_grace_seconds > 10:
        raise ValueError("SSH terminate_grace_seconds must be in [0, 10]")
    for name, value in (("stdout_limit_bytes", request.stdout_limit_bytes), ("stderr_limit_bytes", request.stderr_limit_bytes)):
        if value < 0 or value > MAX_REMOTE_CAPTURE_BYTES:
            raise ValueError(f"{name} must be in [0, {MAX_REMOTE_CAPTURE_BYTES}]")
    return root, cwd


class SSHProcessBackend:
    backend_id = "ssh"
    adapter_id = "backend-ssh-process"

    def __init__(self, profiles: SSHProfileRegistry, local_backend: LocalProcessBackend | None = None) -> None:
        self.profiles = profiles
        self.local_backend = local_backend or LocalProcessBackend()

    def readiness(self) -> dict[str, object]:
        missing = [name for name in ("ssh", "ssh-keygen", "ssh-keyscan") if shutil.which(name) is None]
        if missing:
            return {"status": "unavailable", "reason": "missing OpenSSH executable(s): " + ", ".join(missing)}
        if len(self.profiles) == 0:
            return {"status": "unavailable", "reason": "no named SSH profiles configured"}
        return {"status": "available", "reason": "OpenSSH client and named SSH profile registry available"}

    def preflight(self, request: SSHProcessRequest) -> SSHPreparedTarget:
        profile = self.profiles.require(request.profile_id)
        _validate_request(request, profile)
        resolved_ip = _resolve_target(profile)
        identity_file = _resolve_identity_file(profile.credential_ref)
        pinned = _known_host_fingerprints(profile)
        observed = _scan_host_fingerprints(profile, resolved_ip)
        matched = sorted(pinned.intersection(observed))
        if not matched:
            raise AuthorityViolation("SSH host key check failed: observed key does not match pinned profile key")
        return SSHPreparedTarget(
            profile=profile,
            resolved_ip=resolved_ip,
            host_fingerprint=matched[0],
            identity_file=identity_file,
        )

    def execute(self, request: SSHProcessRequest) -> SSHProcessResult:
        prepared = self.preflight(request)
        profile = prepared.profile
        root, cwd = _validate_request(request, profile)
        ssh = shutil.which("ssh")
        if not ssh:
            raise RuntimeError("OpenSSH ssh client became unavailable after preflight")
        control = {
            "protocol": "capt-ssh-exec-v1",
            "argv": list(request.argv),
            "cwd": cwd,
            "filesystemRoot": root,
            "timeoutMs": max(1, int(request.timeout_seconds * 1000)),
            "stdoutLimitBytes": request.stdout_limit_bytes,
            "stderrLimitBytes": request.stderr_limit_bytes,
            "terminateGraceMs": int(request.terminate_grace_seconds * 1000),
        }
        encoded = json.dumps(control, sort_keys=True, separators=(",", ":")).encode("utf-8")
        argv = (
            ssh,
            "-F", "/dev/null",
            "-T",
            "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f"UserKnownHostsFile={profile.known_hosts_file}",
            "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "PasswordAuthentication=no",
            "-o", "KbdInteractiveAuthentication=no",
            "-o", "GSSAPIAuthentication=no",
            "-o", "ForwardAgent=no",
            "-o", "ForwardX11=no",
            "-o", "ClearAllForwardings=yes",
            "-o", "ControlMaster=no",
            "-o", f"HostKeyAlias={profile.profile_id}",
            "-i", str(prepared.identity_file),
            "-p", str(profile.port),
            "-l", profile.username,
            prepared.resolved_ip,
            bootstrap_command(profile.remote_python),
        )
        transport = self.local_backend.execute(
            LocalProcessRequest(
                argv=tuple(argv),
                cwd=Path("/"),
                filesystem_root=Path("/"),
                timeout_seconds=min(request.timeout_seconds + 5.0, 3600.0),
                stdout_limit_bytes=MAX_SSH_CONTROL_BYTES,
                stderr_limit_bytes=1024 * 1024,
                stdin_data=encoded,
                terminate_grace_seconds=request.terminate_grace_seconds,
            )
        )
        if transport.timed_out or transport.cancelled:
            raise RuntimeError("SSH transport became indeterminate before a framed remote result")
        if transport.exit_code != 0:
            reason = transport.stderr.strip().replace(str(prepared.identity_file), "<credential-ref>")[:4096]
            raise RuntimeError(f"SSH transport failed with exit {transport.exit_code}: {reason}")
        if transport.stdout_truncated:
            raise RuntimeError("SSH framed remote result exceeded local control-channel bound")
        try:
            payload = json.loads(transport.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("SSH remote bootstrap returned invalid framed JSON") from exc
        if payload.get("protocol") != "capt-ssh-exec-v1":
            raise RuntimeError("SSH remote bootstrap protocol mismatch")
        status = payload.get("status")
        if status == "denied":
            return SSHProcessResult(
                exit_code=None, stdout="", stderr="", stdout_total_bytes=0, stderr_total_bytes=0,
                stdout_truncated=False, stderr_truncated=False, timed_out=False,
                profile_id=profile.profile_id, host_fingerprint=prepared.host_fingerprint,
                remote_cwd=cwd, remote_pid=0, remote_process_group_id=0,
                denied=True, denial_reason=str(payload.get("reason") or "remote bootstrap denied request")[:4096],
            )
        if status == "indeterminate":
            raise RuntimeError("SSH remote bootstrap reported indeterminate execution: " + str(payload.get("reason") or "unknown"))
        if status != "completed":
            raise RuntimeError(f"SSH remote bootstrap returned invalid status: {status!r}")
        try:
            stdout_bytes = base64.b64decode(payload["stdoutB64"], validate=True)
            stderr_bytes = base64.b64decode(payload["stderrB64"], validate=True)
        except Exception as exc:
            raise RuntimeError("SSH remote bootstrap returned invalid output encoding") from exc
        return SSHProcessResult(
            exit_code=payload.get("exitCode"),
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            stdout_total_bytes=int(payload["stdoutTotalBytes"]),
            stderr_total_bytes=int(payload["stderrTotalBytes"]),
            stdout_truncated=bool(payload["stdoutTruncated"]),
            stderr_truncated=bool(payload["stderrTruncated"]),
            timed_out=bool(payload["timedOut"]),
            profile_id=profile.profile_id,
            host_fingerprint=prepared.host_fingerprint,
            remote_cwd=str(payload["remoteCwd"]),
            remote_pid=int(payload["remotePid"]),
            remote_process_group_id=int(payload["remoteProcessGroupId"]),
        )
