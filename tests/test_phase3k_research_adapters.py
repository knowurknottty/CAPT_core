"""Phase 3K — Research module adapters tests."""
from __future__ import annotations

from capt_solo.research.adapter import (
    AdapterStatus,
    LocalFallbackAdapter,
    ResearchAdapter,
    ResearchAdapterRegistry,
    ResearchResult,
)


class _StubAdapter(ResearchAdapter):
    name = "stub_research"
    version = "0.1.0"

    def capabilities(self) -> list:
        return ["summarize"]

    def run(self, input, **kwargs):
        return ResearchResult(adapter=self.name, ok=True,
                              output=f"processed:{input}")


def test_k_register_and_get():
    reg = ResearchAdapterRegistry()
    a = _StubAdapter()
    reg.register("stub", a)
    assert reg.get("stub") is a
    assert "stub" in reg.list_modules()


def test_k_run_active_adapter():
    reg = ResearchAdapterRegistry()
    reg.register("stub", _StubAdapter())
    res = reg.run("stub", "data")
    assert res.ok is True
    assert res.output == "processed:data"


def test_k_missing_module_graceful_fallback():
    reg = ResearchAdapterRegistry()
    # no adapter registered for 'absent' -> local fallback (I-09)
    res = reg.run("absent", "data")
    assert res.ok is False
    assert "unavailable" in res.error
    assert res.adapter == "local_fallback"


def test_k_adapter_failure_bounded():
    class Boom(ResearchAdapter):
        name = "boom"
        version = "0.0.1"
        def run(self, input, **kwargs):
            raise RuntimeError("kaboom")
    reg = ResearchAdapterRegistry()
    reg.register("boom", Boom())
    res = reg.run("boom", "x")
    assert res.ok is False
    assert "RuntimeError" in res.error


def test_k_health_status():
    reg = ResearchAdapterRegistry()
    reg.register("stub", _StubAdapter())
    reg.register("missing", LocalFallbackAdapter(for_module="x"))
    h = reg.health()
    assert h["stub"] == AdapterStatus.ACTIVE.value
    assert h["missing"] == AdapterStatus.DEGRADED.value


def test_k_default_registry_exists():
    from capt_solo.research.adapter import DEFAULT_REGISTRY
    assert isinstance(DEFAULT_REGISTRY, ResearchAdapterRegistry)
