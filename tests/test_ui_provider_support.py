"""Discriminating tests for provider support classification, transport
adapters, and secret handling (RTSP3 reconciliation hardening).

These distinguish REGISTERED vs OPERATIONAL providers, verify native vs
OpenAI-compatible transport routing, failed-health / missing-key handling, and
that secrets are never persisted or leaked.
"""

import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capt_ui.operator.adapters import (  # noqa: E402
    NativeAdapter,
    OllamaAdapter,
    OpenAICompatibleAdapter,
    SubprocessAdapter,
    adapter_for,
)
from capt_ui.operator.contract import ProviderHealth, ProviderKind  # noqa: E402
from capt_ui.operator.provider_support import (  # noqa: E402
    CAPABILITY_MATRIX,
    capability_for,
    full_matrix,
    level_of,
)
from capt_ui.operator.providers import Provider, ProviderManager  # noqa: E402
from capt_ui.operator.secrets import make_ref, resolve, safe_to_dict, scrub, scrub_obj  # noqa: E402


def _p(**kw) -> Provider:
    base = dict(id="p", name="P", kind=ProviderKind.LOCAL, transport="openai_compatible",
                base_url="http://127.0.0.1:9/v1")
    base.update(kw)
    return Provider(**base)


# -------------------------------------------------------- registered vs supported
def test_registered_only_does_not_imply_supported():
    for cap in CAPABILITY_MATRIX:
        if cap.id == "mlx":
            assert cap.registered is False
        else:
            assert cap.registered is True
        if cap.id in ("mlx", "hermes"):
            assert cap.model_execution is False


def test_support_level_defaults_to_registered_only():
    assert capability_for("mlx").registered is False
    assert level_of("mlx") == "UNREGISTERED"
    assert level_of("hermes") == "REGISTERED_ONLY"


def test_capability_matrix_shapes():
    m = full_matrix()
    assert len(m) == 7
    assert all({"id", "transport", "support_level"} <= set(row) for row in m)


def test_ollama_openrouter_have_health_probe():
    assert capability_for("ollama").health_probe is True
    assert capability_for("openrouter").health_probe is True


# -------------------------------------------------------- transport adaptation
def test_adapter_routing_by_transport():
    assert isinstance(adapter_for("openai_compatible"), OpenAICompatibleAdapter)
    assert isinstance(adapter_for("ollama"), OllamaAdapter)
    assert isinstance(adapter_for("native"), NativeAdapter)
    assert isinstance(adapter_for("subprocess"), SubprocessAdapter)


def test_native_adapter_is_honest_not_forced_http():
    p = _p(transport="native", base_url="")  # empty base_url - must not be HTTP-probed
    a = adapter_for("native")
    res = a.health(p)
    assert res["health"] == ProviderHealth.UNKNOWN.value
    assert res["reachable"] is None
    assert a.list_models(p) == []


def test_ollama_native_health_unreachable():
    p = _p(transport="ollama", base_url="http://127.0.0.1:1/v1")
    a = adapter_for("ollama")
    res = a.health(p)
    assert res["health"] in (ProviderHealth.RED.value,)
    assert res["reachable"] in (True, False)


def test_openai_compatible_unreachable_red():
    p = _p(transport="openai_compatible", base_url="http://127.0.0.1:1/v1")
    res = adapter_for("openai_compatible").health(p)
    assert res["health"] == ProviderHealth.RED.value
    assert res["reachable"] is False


def test_missing_api_key_openrouter_auth_failure():
    # unreachable endpoint; key missing must not crash
    p = _p(id="openrouter", transport="openai_compatible",
           base_url="http://127.0.0.1:2/v1")
    res = adapter_for("openai_compatible").health(p, api_key="")
    assert res["health"] in (ProviderHealth.RED.value, ProviderHealth.YELLOW.value)



def test_openrouter_auth_failure_is_classified_without_cloud_call():
    class Deny(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(401)
            self.end_headers()
        def log_message(self, format, *args):  # noqa: N802,A002
            return
    server = ThreadingHTTPServer(("127.0.0.1", 0), Deny)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        p = _p(id="openrouter", transport="openai_compatible",
               base_url="http://127.0.0.1:%d/v1" % server.server_port)
        result = adapter_for("openai_compatible").health(p, api_key="")
        assert result == {"health": ProviderHealth.RED.value, "reachable": True,
                          "authenticated": False, "model_list_ok": False,
                          "latency_ms": result["latency_ms"]}
    finally:
        server.shutdown()
        server.server_close()


def test_execution_not_supported_honest():
    p = _p(transport="openai_compatible")
    with pytest.raises(NotImplementedError):
        adapter_for("openai_compatible").execute_or_bind(p, "m")


# -------------------------------------------------------- secret handling
def test_secret_reference_never_raw():
    assert make_ref("env", "OPENROUTER_KEY").startswith("env:")
    assert "sk-" not in make_ref("env", "OPENROUTER_KEY")


def test_resolve_env_reference():
    os.environ["CAPT_TEST_SECRET_XYZ"] = "sk-abcdef1234567890"
    try:
        val = resolve("openrouter", "env:CAPT_TEST_SECRET_XYZ")
        assert val == "sk-abcdef1234567890"
    finally:
        del os.environ["CAPT_TEST_SECRET_XYZ"]


def test_scrub_removes_tokens():
    assert "sk-abcdef1234567890" not in scrub("key=sk-abcdef1234567890 done")
    assert "sk-abcdef1234567890" not in "".join(scrub_obj({"k": "Bearer sk-abcdef1234567890"}).values())


def test_safe_to_dict_hides_raw_secret():
    class P:
        def to_dict(self):
            return {"id": "openrouter", "key_ref": "sk-or-1234567890abcdef", "name": "OR"}

        key_ref = "sk-or-1234567890abcdef"

    d = safe_to_dict(P())
    assert "sk-or-1234567890abcdef" not in str(d)
    assert d["key_ref"] != "sk-or-1234567890abcdef"


def test_delete_provider_no_secret_leak():
    cfg = Path(tempfile.mkdtemp()) / "ui"
    pm = ProviderManager(cfg)
    p = _p(id="leaky", key_ref="env:CAPT_TEST_DEL", base_url="http://127.0.0.1:9/v1")
    pm.add(p)
    os.environ["CAPT_TEST_DEL"] = "sk-critsecret987654321"
    try:
        pm.deactivate("leaky")  # deactivate, not delete
        # raw secret must not appear in the persisted file
        raw = (cfg / "providers.json").read_text()
        assert "sk-critsecret987654321" not in raw
        assert "env:CAPT_TEST_DEL" in raw  # reference only
    finally:
        del os.environ["CAPT_TEST_DEL"]



def test_provider_rejects_raw_secret_and_unsafe_endpoint_without_persisting(tmp_path):
    cfg = tmp_path / "ui"
    pm = ProviderManager(cfg)
    with pytest.raises(ValueError, match="key_ref"):
        pm.update("openrouter", {"key_ref": "synthetic-raw-secret"})
    with pytest.raises(ValueError, match="base_url"):
        pm.update("openrouter", {"base_url": "ftp://example.invalid/v1"})
    with pytest.raises(ValueError, match="credentials"):
        pm.update("openrouter", {"base_url": "https://user:pass@example.invalid/v1"})
    raw = (cfg / "providers.json").read_text() if (cfg / "providers.json").exists() else ""
    assert "synthetic-raw-secret" not in raw
    assert "user:pass" not in raw


def test_provider_persistence_stores_reference_not_token():
    cfg = Path(tempfile.mkdtemp()) / "ui"
    pm = ProviderManager(cfg)
    pm.update("openrouter", {"key_ref": "env:OPENROUTER_API_KEY"})
    raw = (cfg / "providers.json").read_text()
    assert "OPENROUTER_API_KEY" in raw
    assert "env:" in raw
