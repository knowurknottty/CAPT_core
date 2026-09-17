"""Cloudflare Sandbox Bridge process backend.

CAPT owns authority and evidence. This backend transports an already-admitted
process request to a named Cloudflare Sandbox Bridge profile.
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable
from urllib.parse import urlparse

from capt_runtime.errors import AuthorityViolation

MAX_REMOTE_CAPTURE_BYTES = 16 * 1024 * 1024
_ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _remote_path(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise AuthorityViolation(f"{name} must be an absolute POSIX path")
    path = PurePosixPath(value)
    if ".." in path.parts:
        raise AuthorityViolation(f"{name} may not contain parent traversal")
    return str(path)


def _within(root: str, candidate: str) -> bool:
    root_path = PurePosixPath(root)
    candidate_path = PurePosixPath(candidate)
    try:
        candidate_path.relative_to(root_path)
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class CloudflareSandboxProfile:
    profile_id: str
    api_url: str
    api_key_env: str
    allowed_remote_roots: tuple[str, ...] = ("/workspace",)
    free_tier_eligible: bool = False
    billing_class: str = "unknown"


@dataclass(frozen=True)
class CloudflareCostPolicy:
    mode: str = "free_only"
    allow_paid: bool = False

    def require_admitted(self, profile: "CloudflareSandboxProfile") -> None:
        parsed = urlparse(profile.api_url)
        if parsed.hostname in _LOCAL_HOSTS:
            return
        if self.mode == "free_only":
            if not profile.free_tier_eligible:
                raise AuthorityViolation("CLOUDFLARE_FREE_TIER_NOT_PROVEN")
            return
        if self.mode == "explicit_paid" and self.allow_paid:
            return
        raise AuthorityViolation("CLOUDFLARE_COST_AUTHORITY_REQUIRED")


@dataclass(frozen=True)
class CloudflareProcessRequest:
    profile_id: str
    argv: tuple[str, ...]
    cwd: str
    filesystem_root: str
    timeout_seconds: float = 30.0
    stdout_limit_bytes: int = 1024 * 1024
    stderr_limit_bytes: int = 1024 * 1024


@dataclass(frozen=True)
class CloudflareProcessResult:
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_total_bytes: int
    stderr_total_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool
    sandbox_id: str
    profile_id: str
    remote_cwd: str
    cleanup_status: str


class CloudflareIndeterminateExecution(RuntimeError):
    def __init__(self, sandbox_id: str, cleanup_status: str, reason: str) -> None:
        super().__init__(reason)
        self.sandbox_id = sandbox_id
        self.cleanup_status = cleanup_status
        self.reason = reason


class CloudflareSandboxProfileRegistry:
    def __init__(self, profiles: Iterable[CloudflareSandboxProfile] = ()) -> None:
        self._profiles = {}
        for profile in profiles:
            self.add(profile)

    def add(self, profile: CloudflareSandboxProfile) -> None:
        self._validate(profile)
        if profile.profile_id in self._profiles:
            raise AuthorityViolation("CLOUDFLARE_PROFILE_DUPLICATE")
        self._profiles[profile.profile_id] = profile

    def require(self, profile_id: str) -> CloudflareSandboxProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise AuthorityViolation("CLOUDFLARE_PROFILE_NOT_FOUND") from exc

    def __len__(self) -> int:
        return len(self._profiles)

    @staticmethod
    def _validate(profile: CloudflareSandboxProfile) -> None:
        if not profile.profile_id:
            raise AuthorityViolation("CLOUDFLARE_PROFILE_ID_REQUIRED")
        parsed = urlparse(profile.api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AuthorityViolation("CLOUDFLARE_BRIDGE_URL_INVALID")
        if parsed.scheme != "https" and parsed.hostname not in _LOCAL_HOSTS:
            raise AuthorityViolation("CLOUDFLARE_BRIDGE_REQUIRES_HTTPS")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise AuthorityViolation("CLOUDFLARE_BRIDGE_URL_INVALID")
        if not _ENV_RE.match(profile.api_key_env):
            raise AuthorityViolation("CLOUDFLARE_API_KEY_ENV_INVALID")
        if not profile.allowed_remote_roots:
            raise AuthorityViolation("CLOUDFLARE_REMOTE_ROOT_REQUIRED")
        roots = tuple(_remote_path(root, "allowed_remote_root") for root in profile.allowed_remote_roots)
        if len(set(roots)) != len(roots):
            raise AuthorityViolation("CLOUDFLARE_REMOTE_ROOT_DUPLICATE")


class CloudflareHTTPBridge:
    """Minimal client for Cloudflare's supported Sandbox Bridge HTTP API."""

    @staticmethod
    def _request(profile, token, method, path, payload=None, timeout=30.0):
        url = profile.api_url.rstrip("/") + path
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Authorization": f"Bearer {token}"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read(4096).decode("utf-8", errors="replace")
            raise RuntimeError(f"Cloudflare bridge HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cloudflare bridge unavailable: {exc.reason}") from exc

    def create_sandbox(self, profile, token):
        with self._request(profile, token, "POST", "/v1/sandbox") as response:
            payload = json.loads(response.read().decode("utf-8"))
        sandbox_id = payload.get("id")
        if not isinstance(sandbox_id, str) or not sandbox_id:
            raise RuntimeError("Cloudflare bridge returned invalid sandbox id")
        return sandbox_id

    def destroy_sandbox(self, profile, token, sandbox_id):
        with self._request(profile, token, "DELETE", f"/v1/sandbox/{sandbox_id}") as response:
            if response.status not in {200, 202, 204}:
                raise RuntimeError(f"Cloudflare bridge destroy returned HTTP {response.status}")

    def exec(self, profile, token, sandbox_id, *, argv, cwd, timeout_ms,
             stdout_limit_bytes=1024 * 1024, stderr_limit_bytes=1024 * 1024):
        payload = {"argv": list(argv), "cwd": cwd, "timeout_ms": timeout_ms}
        with self._request(profile, token, "POST", f"/v1/sandbox/{sandbox_id}/exec",
                           payload, timeout=max(5.0, timeout_ms / 1000.0 + 5.0)) as response:
            return self._parse_exec_stream(response, stdout_limit_bytes, stderr_limit_bytes)

    @staticmethod
    def _parse_exec_stream(response, stdout_limit, stderr_limit):
        out = bytearray()
        err = bytearray()
        out_total = err_total = 0
        event = None
        data_lines = []
        exit_code = None
        terminal = False

        def emit(kind, data):
            nonlocal out_total, err_total, exit_code, terminal
            if kind in {"stdout", "stderr"}:
                chunk = base64.b64decode(data, validate=True)
                target, limit = (out, stdout_limit) if kind == "stdout" else (err, stderr_limit)
                if kind == "stdout":
                    out_total += len(chunk)
                else:
                    err_total += len(chunk)
                if len(target) < limit:
                    target.extend(chunk[: max(0, limit - len(target))])
            elif kind == "exit":
                exit_code = int(json.loads(data)["exit_code"])
                terminal = True
            elif kind == "error":
                payload = json.loads(data)
                raise RuntimeError("Cloudflare sandbox exec error: " + str(payload.get("error") or payload))

        for raw in response:
            line = raw.decode("utf-8", errors="strict").rstrip("\r\n")
            if not line:
                if event is not None:
                    emit(event, "\n".join(data_lines))
                event = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if event is not None:
            emit(event, "\n".join(data_lines))
        if not terminal:
            raise RuntimeError("Cloudflare sandbox exec stream ended without terminal event")
        return {
            "exitCode": exit_code,
            "stdout": bytes(out).decode("utf-8", errors="replace"),
            "stderr": bytes(err).decode("utf-8", errors="replace"),
            "stdoutTotalBytes": out_total,
            "stderrTotalBytes": err_total,
            "stdoutTruncated": out_total > len(out),
            "stderrTruncated": err_total > len(err),
        }


def _validate_request(request: CloudflareProcessRequest, profile: CloudflareSandboxProfile):
    if not request.argv or len(request.argv) > 1024:
        raise ValueError("Cloudflare argv must contain 1..1024 elements")
    if not all(isinstance(arg, str) and arg and "\x00" not in arg for arg in request.argv):
        raise ValueError("Cloudflare argv elements must be non-empty strings without NUL")
    if sum(len(arg.encode("utf-8")) for arg in request.argv) > 65536:
        raise ValueError("Cloudflare argv exceeds 65536 encoded bytes")
    root = _remote_path(request.filesystem_root, "filesystem_root")
    cwd = _remote_path(request.cwd, "cwd")
    allowed = tuple(_remote_path(item, "allowed_remote_root") for item in profile.allowed_remote_roots)
    if not any(_within(item, root) for item in allowed):
        raise AuthorityViolation("CLOUDFLARE_FILESYSTEM_SCOPE_DENIED")
    if not _within(root, cwd):
        raise AuthorityViolation("CLOUDFLARE_CWD_OUTSIDE_SCOPE")
    if request.timeout_seconds <= 0 or request.timeout_seconds > 3600:
        raise ValueError("Cloudflare timeout_seconds must be in (0, 3600]")
    for value in (request.stdout_limit_bytes, request.stderr_limit_bytes):
        if value < 0 or value > MAX_REMOTE_CAPTURE_BYTES:
            raise ValueError("Cloudflare capture limit out of range")
    return root, cwd


class CloudflareSandboxBackend:
    backend_id = "cloudflare"
    adapter_id = "backend-cloudflare-sandbox"

    def __init__(self, profiles: CloudflareSandboxProfileRegistry, bridge=None, cost_policy: CloudflareCostPolicy | None = None) -> None:
        self.profiles = profiles
        self.bridge = bridge or CloudflareHTTPBridge()
        self.cost_policy = cost_policy or CloudflareCostPolicy()

    def readiness(self) -> dict[str, object]:
        if len(self.profiles) == 0:
            return {"status": "unavailable", "reason": "no Cloudflare Sandbox profiles configured"}
        missing = [p.profile_id for p in self.profiles._profiles.values() if not os.environ.get(p.api_key_env)]
        if missing:
            return {"status": "unavailable", "reason": "Cloudflare bridge credential missing for profile(s): " + ", ".join(sorted(missing))}
        return {"status": "available", "reason": "Cloudflare Sandbox Bridge profile and credential references available"}

    def preflight(self, request: CloudflareProcessRequest) -> CloudflareSandboxProfile:
        profile = self.profiles.require(request.profile_id)
        self.cost_policy.require_admitted(profile)
        _validate_request(request, profile)
        if not os.environ.get(profile.api_key_env):
            raise AuthorityViolation("CLOUDFLARE_BRIDGE_CREDENTIAL_UNAVAILABLE")
        return profile

    def execute(self, request: CloudflareProcessRequest) -> CloudflareProcessResult:
        profile = self.preflight(request)
        _, cwd = _validate_request(request, profile)
        token = os.environ[profile.api_key_env]
        sandbox_id = ""
        cleanup_status = "not_created"
        try:
            sandbox_id = self.bridge.create_sandbox(profile, token)
            cleanup_status = "pending"
            try:
                payload = self.bridge.exec(
                    profile, token, sandbox_id, argv=request.argv, cwd=cwd,
                    timeout_ms=max(1, int(request.timeout_seconds * 1000)),
                    stdout_limit_bytes=request.stdout_limit_bytes,
                    stderr_limit_bytes=request.stderr_limit_bytes,
                )
            except TypeError:
                payload = self.bridge.exec(
                    profile, token, sandbox_id, argv=request.argv, cwd=cwd,
                    timeout_ms=max(1, int(request.timeout_seconds * 1000)),
                )
        except Exception as exc:
            if sandbox_id:
                try:
                    self.bridge.destroy_sandbox(profile, token, sandbox_id)
                    cleanup_status = "destroyed"
                except Exception:
                    cleanup_status = "cleanup_failed"
            raise CloudflareIndeterminateExecution(
                sandbox_id or "unknown", cleanup_status, str(exc)[:4096]
            ) from exc

        try:
            self.bridge.destroy_sandbox(profile, token, sandbox_id)
            cleanup_status = "destroyed"
        except Exception:
            cleanup_status = "cleanup_failed"
        return CloudflareProcessResult(
            exit_code=payload.get("exitCode"),
            stdout=str(payload.get("stdout") or ""),
            stderr=str(payload.get("stderr") or ""),
            stdout_total_bytes=int(payload.get("stdoutTotalBytes", 0)),
            stderr_total_bytes=int(payload.get("stderrTotalBytes", 0)),
            stdout_truncated=bool(payload.get("stdoutTruncated", False)),
            stderr_truncated=bool(payload.get("stderrTruncated", False)),
            sandbox_id=sandbox_id,
            profile_id=profile.profile_id,
            remote_cwd=cwd,
            cleanup_status=cleanup_status,
        )
