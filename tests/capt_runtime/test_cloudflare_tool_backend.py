from __future__ import annotations

import base64
import json

import pytest

from capt_runtime.contracts import validate
from capt_runtime.errors import AuthorityViolation


def test_cloudflare_is_closed_terminal_backend_contract_member():
    assert validate("TerminalBackendId", "cloudflare") == []


def test_cloudflare_descriptor_is_remote_and_explicit():
    from capt_runtime.tools.builtins import TERMINAL_CLOUDFLARE_DESCRIPTOR
    assert TERMINAL_CLOUDFLARE_DESCRIPTOR["toolId"] == "terminal.cloudflare"
    assert TERMINAL_CLOUDFLARE_DESCRIPTOR["terminalBackends"] == ["cloudflare"]
    assert TERMINAL_CLOUDFLARE_DESCRIPTOR["operationEffects"] == [
        {"operation": "terminal.exec", "effectClass": "durable_remote"}
    ]


def _profile(**overrides):
    from capt_runtime.tools.backends.cloudflare import CloudflareSandboxProfile
    values = dict(profile_id="cf-default", api_url="https://capt-sandbox.example.workers.dev",
                  api_key_env="CAPT_CF_SANDBOX_KEY", allowed_remote_roots=("/workspace",), free_tier_eligible=True)
    values.update(overrides)
    return CloudflareSandboxProfile(**values)


def test_profile_rejects_plain_http_except_localhost():
    from capt_runtime.tools.backends.cloudflare import CloudflareSandboxProfileRegistry
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_BRIDGE_REQUIRES_HTTPS"):
        CloudflareSandboxProfileRegistry([_profile(api_url="http://example.com")])
    registry = CloudflareSandboxProfileRegistry([_profile(api_url="http://127.0.0.1:8787")])
    assert registry.require("cf-default").api_url == "http://127.0.0.1:8787"


def test_profile_requires_secret_reference_to_resolve(monkeypatch):
    from capt_runtime.tools.backends.cloudflare import (
        CloudflareSandboxBackend,
        CloudflareSandboxProfileRegistry,
    )
    monkeypatch.delenv("CAPT_CF_SANDBOX_KEY", raising=False)
    backend = CloudflareSandboxBackend(CloudflareSandboxProfileRegistry([_profile()]))
    assert backend.readiness()["status"] == "unavailable"


class FakeBridge:
    def __init__(self):
        self.created = []
        self.executed = []
        self.destroyed = []

    def create_sandbox(self, profile, token):
        self.created.append((profile.profile_id, token))
        return "sbx-123"

    def exec(self, profile, token, sandbox_id, *, argv, cwd, timeout_ms, **kwargs):
        self.executed.append((sandbox_id, argv, cwd, timeout_ms, token))
        return {"exitCode": 0, "stdout": "hello\n", "stderr": "",
                "stdoutTotalBytes": 6, "stderrTotalBytes": 0,
                "stdoutTruncated": False, "stderrTruncated": False}

    def destroy_sandbox(self, profile, token, sandbox_id):
        self.destroyed.append((sandbox_id, token))


def test_backend_executes_ephemerally_and_never_returns_secret(monkeypatch):
    from capt_runtime.tools.backends.cloudflare import (
        CloudflareProcessRequest,
        CloudflareSandboxBackend,
        CloudflareSandboxProfileRegistry,
    )
    monkeypatch.setenv("CAPT_CF_SANDBOX_KEY", "super-secret")
    bridge = FakeBridge()
    backend = CloudflareSandboxBackend(CloudflareSandboxProfileRegistry([_profile()]), bridge=bridge)
    result = backend.execute(CloudflareProcessRequest(
        profile_id="cf-default", argv=("python", "-V"), cwd="/workspace",
        filesystem_root="/workspace", timeout_seconds=10,
        stdout_limit_bytes=1024, stderr_limit_bytes=1024,
    ))
    assert result.exit_code == 0
    assert result.sandbox_id == "sbx-123"
    assert result.cleanup_status == "destroyed"
    assert bridge.destroyed == [("sbx-123", "super-secret")]
    assert "super-secret" not in repr(result)


def test_backend_rejects_scope_outside_profile(monkeypatch):
    from capt_runtime.tools.backends.cloudflare import (
        CloudflareProcessRequest,
        CloudflareSandboxBackend,
        CloudflareSandboxProfileRegistry,
    )
    monkeypatch.setenv("CAPT_CF_SANDBOX_KEY", "k")
    backend = CloudflareSandboxBackend(CloudflareSandboxProfileRegistry([_profile()]), bridge=FakeBridge())
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_FILESYSTEM_SCOPE_DENIED"):
        backend.execute(CloudflareProcessRequest(
            profile_id="cf-default", argv=("pwd",), cwd="/home",
            filesystem_root="/home", timeout_seconds=10,
            stdout_limit_bytes=1024, stderr_limit_bytes=1024,
        ))


def _tool_request():
    return {
        "toolId": "terminal.cloudflare", "operation": "terminal.exec",
        "backendId": "cloudflare", "targetIdentity": "cf-default",
        "filesystemScope": "/workspace",
        "arguments": [
            {"name": "argv", "value": json.dumps(["python", "-V"])},
            {"name": "cwd", "value": "/workspace"},
            {"name": "timeout_ms", "value": 10000},
        ],
    }


def test_adapter_returns_cloudflare_side_effect_identity_without_secret(monkeypatch):
    from capt_runtime.tools.adapters.cloudflare_terminal import (
        CloudflareTerminalToolAdapter,
    )
    from capt_runtime.tools.backends.cloudflare import (
        CloudflareSandboxBackend,
        CloudflareSandboxProfileRegistry,
    )
    monkeypatch.setenv("CAPT_CF_SANDBOX_KEY", "secret-x")
    adapter = CloudflareTerminalToolAdapter(
        CloudflareSandboxBackend(CloudflareSandboxProfileRegistry([_profile()]), bridge=FakeBridge())
    )
    result = adapter.execute(_tool_request())
    assert result["status"] == "succeeded"
    identity = json.loads(result["sideEffectIdentity"])
    assert identity["backend"] == "cloudflare"
    assert identity["sandboxId"] == "sbx-123"
    assert "secret-x" not in json.dumps(result)


class FakeSSEResponse:
    def __init__(self, lines):
        self._lines = [line.encode("utf-8") for line in lines]

    def __iter__(self):
        return iter(self._lines)


def test_http_bridge_parses_cloudflare_sse_and_bounds_output():
    from capt_runtime.tools.backends.cloudflare import CloudflareHTTPBridge
    stdout = base64.b64encode(b"hello world").decode("ascii")
    stderr = base64.b64encode(b"warn").decode("ascii")
    response = FakeSSEResponse([
        "event: stdout\n", f"data: {stdout}\n", "\n",
        "event: stderr\n", f"data: {stderr}\n", "\n",
        "event: exit\n", 'data: {"exit_code": 0}\n', "\n",
    ])
    result = CloudflareHTTPBridge._parse_exec_stream(response, 5, 10)
    assert result["exitCode"] == 0
    assert result["stdout"] == "hello"
    assert result["stdoutTotalBytes"] == 11
    assert result["stdoutTruncated"] is True
    assert result["stderr"] == "warn"


class FailingBridge(FakeBridge):
    def exec(self, *args, **kwargs):
        raise RuntimeError("connection lost after dispatch")


def test_transport_uncertainty_is_indeterminate_and_cleanup_is_attempted(monkeypatch):
    from capt_runtime.tools.adapters.cloudflare_terminal import (
        CloudflareTerminalToolAdapter,
    )
    from capt_runtime.tools.backends.cloudflare import (
        CloudflareSandboxBackend,
        CloudflareSandboxProfileRegistry,
    )
    monkeypatch.setenv("CAPT_CF_SANDBOX_KEY", "secret-y")
    bridge = FailingBridge()
    adapter = CloudflareTerminalToolAdapter(
        CloudflareSandboxBackend(CloudflareSandboxProfileRegistry([_profile()]), bridge=bridge)
    )
    result = adapter.execute(_tool_request())
    assert result["status"] == "indeterminate"
    identity = json.loads(result["sideEffectIdentity"])
    assert identity["sandboxId"] == "sbx-123"
    assert identity["cleanupStatus"] == "destroyed"
    assert bridge.destroyed == [("sbx-123", "secret-y")]


def test_composition_registers_cloudflare_as_truthful_optional_backend(tmp_path, monkeypatch):
    from capt_runtime.composition import create_runtime
    monkeypatch.setenv("CAPT_CF_SANDBOX_KEY", "secret-z")
    runtime = create_runtime(str(tmp_path / "ledger.sqlite"), cloudflare_profiles=[_profile()])
    try:
        assert runtime.tool_registry.require("terminal.cloudflare")["descriptor"]["terminalBackends"] == ["cloudflare"]
        assert runtime.tool_registry.readiness("terminal.cloudflare")["status"] == "available"
        assert runtime.cloudflare_profile_registry.require("cf-default").api_key_env == "CAPT_CF_SANDBOX_KEY"
    finally:
        runtime.close()
