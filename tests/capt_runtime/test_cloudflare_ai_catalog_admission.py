from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_ai_catalog import (
    parse_cloudflare_ai_model_catalog,
)
from capt_runtime.tools.backends.cloudflare_free_planner import (
    CloudflareFreeExecutionPlanner,
)
from capt_runtime.tools.backends.cloudflare_free_router import (
    CloudflareFreeEstimate,
    CloudflareFreeTierRouter,
    CloudflareWorkClass,
)
from capt_runtime.tools.backends.cloudflare_native import (
    CloudflareDispatchNotStarted,
    CloudflareWorkersAIInferencer,
)
from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger

NOW = datetime(2026, 9, 9, 4, 20, tzinfo=timezone.utc)
DAY = date(2026, 9, 9)
FREE_MODEL = "@cf/meta/llama-3.1-8b-instruct"
PAID_MODEL = "@cf/zai-org/glm-5.3-flash"


def _catalog(*, fetched_at=NOW):
    return parse_cloudflare_ai_model_catalog(
        [
            {"name": FREE_MODEL, "properties": []},
            {
                "name": PAID_MODEL,
                "properties": [
                    {"property_id": "require_workers_paid", "value": "true"}
                ],
            },
        ],
        fetched_at=fetched_at,
    )


def _planner(tmp_path):
    router = CloudflareFreeTierRouter.default()
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite", router=router)
    planner = CloudflareFreeExecutionPlanner(ledger, router, now=lambda: NOW)
    return planner, ledger


def test_router_requires_provider_catalog_for_inference():
    router = CloudflareFreeTierRouter.default()
    with pytest.raises(
        AuthorityViolation, match="CLOUDFLARE_AI_MODEL_CATALOG_REQUIRED"
    ):
        router.route(
            CloudflareWorkClass.INFERENCE,
            CloudflareFreeEstimate(ai_model=FREE_MODEL, ai_neurons=1),
            at=NOW,
        )


def test_planner_blocks_paid_model_before_neuron_reservation(tmp_path):
    planner, ledger = _planner(tmp_path)
    with pytest.raises(
        AuthorityViolation, match="CLOUDFLARE_AI_MODEL_REQUIRES_PAID_AUTHORITY"
     ):
        planner.reserve(
            operation_id="ai-paid-pre-reserve",
            work_class=CloudflareWorkClass.INFERENCE,
            estimate=CloudflareFreeEstimate(ai_model=PAID_MODEL, ai_neurons=50),
            ai_catalog=_catalog(),
            day=DAY,
        )
    assert ledger.snapshot(day=DAY).workers_ai_neurons == 0


def test_planner_blocks_stale_catalog_before_neuron_reservation(tmp_path):
    planner, ledger = _planner(tmp_path)
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_AI_MODEL_CATALOG_STALE"):
        planner.reserve(
            operation_id="ai-stale-pre-reserve",
            work_class=CloudflareWorkClass.INFERENCE,
            estimate=CloudflareFreeEstimate(ai_model=FREE_MODEL, ai_neurons=50),
            ai_catalog=_catalog(fetched_at=NOW - timedelta(minutes=16)),
            day=DAY,
        )
    assert ledger.snapshot(day=DAY).workers_ai_neurons == 0


class Bridge:
    def __init__(self, catalog):
        self.catalog = catalog
        self.calls = []

    def ai_model_catalog(self):
        self.calls.append("catalog")
        return self.catalog

    def workers_ai(self, **kwargs):
        self.calls.append("infer")
        return {
            "neurons": kwargs["estimated_neurons"],
            "output": {"text": "ok"},
            "usageBasis": "reserved_ceiling",
        }


def test_inferencer_discovers_catalog_before_reserving_and_returns_provenance(tmp_path):
    planner, ledger = _planner(tmp_path)
    bridge = Bridge(_catalog())
    inferencer = CloudflareWorkersAIInferencer(planner, bridge)
    result = inferencer.infer(
        operation_id="ai-catalog-provenance",
        model=FREE_MODEL,
        input_payload={"prompt": "hi"},
        estimated_neurons=25,
        day=DAY,
    )
    assert bridge.calls == ["catalog", "infer"]
    assert ledger.snapshot(day=DAY).workers_ai_neurons == 25
    assert result.catalog_digest == bridge.catalog.source_digest
    assert result.catalog_fetched_at == bridge.catalog.fetched_at.isoformat()


def test_catalog_discovery_failure_never_reserves_or_dispatches_inference(tmp_path):
    planner, ledger = _planner(tmp_path)

    class MissingCatalog(Bridge):
        def ai_model_catalog(self):
            self.calls.append("catalog")
            raise CloudflareDispatchNotStarted("CLOUDFLARE_AI_CATALOG_DISCOVERY_UNAVAILABLE")

    bridge = MissingCatalog(_catalog())
    inferencer = CloudflareWorkersAIInferencer(planner, bridge)
    with pytest.raises(
        CloudflareDispatchNotStarted,
        match="CLOUDFLARE_AI_CATALOG_DISCOVERY_UNAVAILABLE",
    ):
        inferencer.infer(
            operation_id="ai-catalog-missing",
            model=FREE_MODEL,
            input_payload={"prompt": "hi"},
            estimated_neurons=25,
            day=DAY,
        )
    assert bridge.calls == ["catalog"]
    assert ledger.snapshot(day=DAY).workers_ai_neurons == 0
