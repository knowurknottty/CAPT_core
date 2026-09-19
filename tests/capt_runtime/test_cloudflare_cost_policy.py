from __future__ import annotations

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare import (
    CloudflareCostPolicy,
    CloudflareProcessRequest,
    CloudflareSandboxBackend,
    CloudflareSandboxProfile,
    CloudflareSandboxProfileRegistry,
)


class NeverBridge:
    def create_sandbox(self, profile, token):
        raise AssertionError("cost policy must block before provider dispatch")


def _request():
    return CloudflareProcessRequest(
        profile_id="cf-unknown", argv=("pwd",), cwd="/workspace",
        filesystem_root="/workspace", timeout_seconds=5,
    )


def test_free_only_blocks_unknown_remote_billing_class(monkeypatch):
    monkeypatch.setenv("CAPT_CF_SANDBOX_KEY", "k")
    profile = CloudflareSandboxProfile(
        profile_id="cf-unknown",
        api_url="https://capt-sandbox.example.workers.dev",
        api_key_env="CAPT_CF_SANDBOX_KEY",
    )
    backend = CloudflareSandboxBackend(
        CloudflareSandboxProfileRegistry([profile]),
        bridge=NeverBridge(),
        cost_policy=CloudflareCostPolicy(),
    )
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_FREE_TIER_NOT_PROVEN"):
        backend.execute(_request())


def test_localhost_dev_is_admitted_without_paid_authority(monkeypatch):
    monkeypatch.setenv("CAPT_CF_SANDBOX_KEY", "k")
    profile = CloudflareSandboxProfile(
        profile_id="cf-unknown",
        api_url="http://127.0.0.1:8787",
        api_key_env="CAPT_CF_SANDBOX_KEY",
    )
    policy = CloudflareCostPolicy()
    policy.require_admitted(profile)
