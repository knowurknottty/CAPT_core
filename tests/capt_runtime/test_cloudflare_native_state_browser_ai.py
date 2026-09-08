from __future__ import annotations

from datetime import date

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.backends.cloudflare_free_planner import (
    CloudflareFreeExecutionPlanner,
)
from capt_runtime.tools.backends.cloudflare_free_router import CloudflareFreeTierRouter
from capt_runtime.tools.backends.cloudflare_native import (
    CloudflareBrowserRunner,
    CloudflareD1StateStore,
    CloudflareWorkersAIInferencer,
)
from capt_runtime.tools.backends.cloudflare_usage import CloudflareUsageLedger


class Bridge:
    def d1_read(self, **kwargs):
        return {"rows": [{"value": "ok"}], "rowsRead": 3}

    def d1_write(self, **kwargs):
        return {"rowsWritten": 1, "changeId": "chg-1"}

    def browser_run(self, **kwargs):
        return {"browserSeconds": 4, "artifactRef": "browser-artifact-1"}

    def workers_ai(self, **kwargs):
        return {"neurons": 20, "output": {"text": "ok"}}


def _planner(tmp_path):
    router = CloudflareFreeTierRouter.default()
    ledger = CloudflareUsageLedger(tmp_path / "usage.sqlite", router=router)
    return CloudflareFreeExecutionPlanner(ledger, router), ledger


def test_d1_read_and_write_are_independently_metered(tmp_path):
    planner, ledger = _planner(tmp_path)
    store = CloudflareD1StateStore(planner, Bridge())
    read = store.read(
        operation_id="d1-read-1",
        database="capt-state",
        statement="SELECT value FROM kv WHERE key=?",
        params=["k"],
        estimated_rows_read=5,
        day=date(2026, 9, 8),
    )
    assert read.rows[0]["value"] == "ok"
    write = store.write(
        operation_id="d1-write-1",
        database="capt-state",
        statement="UPDATE kv SET value=? WHERE key=?",
        params=["v", "k"],
        estimated_rows_written=2,
        day=date(2026, 9, 8),
    )
    assert write.change_id == "chg-1"
    usage = ledger.snapshot(day=date(2026, 9, 8))
    assert usage.d1_rows_read == 5
    assert usage.d1_rows_written == 2


def test_browser_run_reserves_seconds_and_requires_artifact_identity(tmp_path):
    planner, ledger = _planner(tmp_path)
    browser = CloudflareBrowserRunner(planner, Bridge())
    result = browser.run(
        operation_id="browser-1",
        action="navigate_and_extract",
        arguments={"url": "https://example.com"},
        estimated_seconds=5,
        day=date(2026, 9, 8),
    )
    assert result.artifact_ref == "browser-artifact-1"
    assert ledger.snapshot(day=date(2026, 9, 8)).browser_seconds == 5


def test_workers_ai_is_free_model_gated_and_metered(tmp_path):
    planner, ledger = _planner(tmp_path)
    ai = CloudflareWorkersAIInferencer(planner, Bridge())
    result = ai.infer(
        operation_id="ai-1",
        model="@cf/meta/llama-3.1-8b-instruct",
        input_payload={"prompt": "hello"},
        estimated_neurons=25,
        day=date(2026, 9, 8),
    )
    assert result.output["text"] == "ok"
    assert ledger.snapshot(day=date(2026, 9, 8)).workers_ai_neurons == 25
    with pytest.raises(AuthorityViolation, match="CLOUDFLARE_AI_MODEL_REQUIRES_PAID_AUTHORITY"):
        ai.infer(
            operation_id="ai-paid",
            model="@cf/zai-org/glm-5.3-flash",
            input_payload={"prompt": "no"},
            estimated_neurons=1,
            day=date(2026, 9, 8),
        )
