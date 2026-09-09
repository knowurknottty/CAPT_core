from __future__ import annotations

import pytest

from capt_runtime.tools.backends.cloudflare_native import CloudflareDispatchNotStarted
from capt_runtime.tools.backends.cloudflare_native_api import (
    CloudflareNativeAPIBridge,
    CloudflareNativeAPIProfile,
)


class NoNetwork:
    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError(
            "network dispatch must not start without an adopted binding registry"
        )


def profile():
    return CloudflareNativeAPIProfile(
        account_id="acct-1",
        api_token_env="CF_API_TOKEN",
        worker_base_url="https://capt-control.example.workers.dev",
        worker_auth_env="CF_WORKER_TOKEN",
    )


@pytest.mark.parametrize(
    "invoke",
    [
        lambda bridge: bridge.queue_send(
            operation_id="op-q", queue="capt-delegates", body={"x": 1}
        ),
        lambda bridge: bridge.d1_read(
            operation_id="op-d1",
            database="capt-state",
            statement="SELECT 1",
            params=[],
        ),
        lambda bridge: bridge.worker_request(
            operation_id="op-w",
            route="/coordinate",
            payload={"x": 1},
            cpu_ms=1,
        ),
    ],
)
def test_remote_resource_dispatch_requires_eventstore_binding_registry(invoke):
    opener = NoNetwork()
    bridge = CloudflareNativeAPIBridge(profile(), opener=opener)
    with pytest.raises(
        CloudflareDispatchNotStarted,
        match="CLOUDFLARE_RESOURCE_BINDING_REGISTRY_REQUIRED",
    ):
        invoke(bridge)
    assert opener.calls == 0


def test_profile_rejects_raw_provider_resource_id_maps():
    from capt_runtime.errors import AuthorityViolation
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_NATIVE_RAW_RESOURCE_IDS_FORBIDDEN"):
        CloudflareNativeAPIProfile(
            account_id="acct-1", api_token_env="CF_API_TOKEN",
            worker_base_url="https://capt-control.example.workers.dev", worker_auth_env="CF_WORKER_TOKEN",
            queue_ids={"capt-delegates": "queue-raw"}, d1_database_ids={},
        )
