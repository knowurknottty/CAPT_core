from __future__ import annotations

from capt_runtime.composition import create_runtime
from capt_runtime.tools.backends.cloudflare_native_api import CloudflareNativeAPIProfile


def _profile():
    return CloudflareNativeAPIProfile(
        account_id="acct-1",
        api_token_env="CF_API_TOKEN",
        worker_base_url="https://capt-control.example.workers.dev",
        worker_auth_env="CF_WORKER_TOKEN",
        worker_alias="capt-control",
    )


def test_runtime_has_no_native_cloudflare_surface_without_profile(tmp_path):
    runtime = create_runtime(str(tmp_path / "runtime.db"))
    try:
        assert runtime.cloudflare_native is None
    finally:
        runtime.close()


def test_runtime_constructs_all_native_surfaces_without_network_call(tmp_path):
    runtime = create_runtime(
        str(tmp_path / "runtime.db"),
        cloudflare_native_profile=_profile(),
    )
    try:
        native = runtime.cloudflare_native
        assert native is not None
        assert native.workers is not None
        assert native.queues is not None
        assert native.d1 is not None
        assert native.browser is not None
        assert native.ai is not None
        assert native.queues.bridge.binding_registry is not None
        assert native.queues.bridge.binding_registry.store is runtime.store
    finally:
        runtime.close()
