from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from capt_ui.operator.council_ux import (
    approval_presentation, draft_path, execution_projection,
    load_draft_snapshot, provider_catalog, refresh_provider_models,
    save_draft_snapshot,
)
from capt_ui.operator.council_workflow import donor_convergence_workflow


class FakeManager:
    def __init__(self):
        self.items = [
            SimpleNamespace(id="openrouter", enabled=True,
                            models=["z-ai/glm-5.3-flash", "qwen/qwen3.8-flash"]),
            SimpleNamespace(id="disabled", enabled=False, models=["not-visible"]),
        ]
        self.probed = []

    def list(self):
        return self.items

    def get(self, key):
        return next((p for p in self.items if p.id == key), None)

    def test(self, key):
        self.probed.append(key)
        return SimpleNamespace(model_list_ok=True, models=["new-model", "new-model"])


def test_catalog_cached_does_not_contact_network():
    m = FakeManager()
    assert provider_catalog(m) == {
        "openrouter": ("qwen/qwen3.8-flash", "z-ai/glm-5.3-flash"),
    }
    assert not m.probed
    assert refresh_provider_models(m, "openrouter") == ("new-model",)
    assert m.probed == ["openrouter"]
    with pytest.raises(ValueError):
        refresh_provider_models(m, "disabled")


def test_draft_is_private_atomic_and_contains_no_approvals(tmp_path):
    workflow = donor_convergence_workflow(str(tmp_path)).to_record()
    workflow.update({"approvals": [{"requestId": "never-persist"}],
                     "executions": [{"driverRunId": "never-persist"}],
                     "selectedCohort": "mimo26-flash",
                     "editorDraft": {"objective": "unsaved text"}})
    p = draft_path(tmp_path)
    save_draft_snapshot(workflow, p)
    assert p.stat().st_mode & 0o777 == 0o600
    raw = json.loads(p.read_text())
    assert "approvals" not in raw and "executions" not in raw
    assert raw["selectedCohort"] == "mimo26-flash"
    assert raw["editorDraft"]["objective"] == "unsaved text"
    restored = load_draft_snapshot(p)
    assert restored is not None and restored.logical_vessels == 33


def test_execution_projection_never_fabricates_success():
    class Client:
        def get_state(self, key):
            return {"state": "lost", "reconciliationStatus": "required"} if key.endswith("a") else {}
    rows = execution_projection(Client(), [
        {"cohortSpec": {"cohortId": "first"}, "driverRunId": "a"},
        {"cohortSpec": {"cohortId": "second"}, "driverRunId": "b"},
    ])
    assert rows[0]["state"] == "lost"
    assert rows[0]["reconciliation"] == "required"
    assert rows[1]["state"] == "not dispatched / unknown"
    assert rows[1]["reconciliation"] == "unknown"
    assert approval_presentation("approved")[1] == "approved"
    assert approval_presentation("requested")[1] == "pending"

def test_missing_runtime_stream_remains_unknown():
    class Client:
        def get_state(self, key):
            raise RuntimeError("unknown stream")

    rows = execution_projection(Client(), [
        {"cohortSpec": {"cohortId": "c01"}, "driverRunId": "missing"},
    ])
    assert rows[0]["state"] == "not dispatched / unknown"


def test_partial_form_values_survive_without_becoming_authority(tmp_path):
    p = draft_path(tmp_path)
    record = donor_convergence_workflow(str(tmp_path)).to_record()
    record["pendingFields"] = {"contextBudget": "still editing"}
    record["editorDraft"] = {"objective": "not yet applied"}
    save_draft_snapshot(record, p)
    saved = json.loads(p.read_text())
    assert saved["pendingFields"]["contextBudget"] == "still editing"
    assert load_draft_snapshot(p).requested_context_budget == 128000


def test_council_status_never_confuses_dispatch_with_verified_success(tmp_path):
    from capt_ui.operator.council_ux import (
        execution_summary, council_receipt_summary, mission_execution_projection,
    )
    workflow = donor_convergence_workflow(str(tmp_path))
    class Reader:
        def get_state(self, stream_id):
            if stream_id.endswith("qwen38-flash"):
                return {"state": "lost", "reconciliationStatus": "required"}
            if stream_id.endswith("mimo26-flash"):
                return {"state": "completed", "reconciliationStatus": "not_required"}
            return {}
    rows = mission_execution_projection(Reader(), workflow)
    assert len(rows) == 3
    assert [r["driverRunId"] for r in rows] == [
        "dr-m-capt-donor-convergence-r1-qwen38-flash",
        "dr-m-capt-donor-convergence-r1-mimo26-flash",
        "dr-m-capt-donor-convergence-r1-glm53-flash",
    ]
    text, kind = execution_summary(rows)
    assert kind == "error" and "RECONCILIATION REQUIRED" in text
    assert "qwen38-flash" in text
    assert execution_summary([
        {"cohortId": "a", "state": "completed", "reconciliation": "not_required"}
    ])[1] == "review"
    assert "incomplete" in council_receipt_summary({
        "status": "accepted",
        "result": {
            "cohorts": [
                {"cohortId": "a", "receipt": {"status": "rejected"}},
                {"cohortId": "b", "receipt": {"status": "blocked"}},
            ]
        },
    })
    assert "inspect DriverRun receipts" in council_receipt_summary({
        "status": "accepted", "result": {"cohorts": [
            {"cohortId": "a", "receipt": {"status": "accepted"}},
        ]}
    })


def test_existing_driver_run_ids_cannot_be_silently_reused(tmp_path):
    from capt_ui.operator.council_ux import existing_driver_run_conflicts
    workflow = donor_convergence_workflow(str(tmp_path))
    class Reader:
        def get_state(self, stream):
            if stream.endswith("qwen38-flash"):
                return {"state": "lost"}
            raise RuntimeError("unknown stream: " + stream)
    conflicts = existing_driver_run_conflicts(Reader(), workflow)
    assert conflicts == ["dr-m-capt-donor-convergence-r1-qwen38-flash (lost)"]
    class BrokenReader:
        def get_state(self, stream):
            raise RuntimeError("transport disconnected")
    with pytest.raises(RuntimeError, match="transport disconnected"):
        existing_driver_run_conflicts(BrokenReader(), workflow)


def test_sanitized_provider_failure_is_visible_without_raw_http_body():
    from capt_ui.operator.council_ux import execution_projection
    class Reader:
        def get_state(self, stream):
            return {"state": "lost", "reconciliationStatus": "required"}
        def _query(self, request):
            assert request["op"] == "provider_failure_diagnostic"
            return {"result": {
                "failureCode": "PROVIDER_HTTP_ERROR",
                "httpStatus": 400,
                "providerHttpRequestAttempts": 24,
                "rawExceptionPersisted": False,
            }}
    rows = execution_projection(Reader(), [
        {"cohortSpec": {"cohortId": "glm"}, "driverRunId": "dr-glm"},
    ])
    assert rows[0]["diagnostic"] == "PROVIDER_HTTP_ERROR | HTTP 400 | 24 HTTP attempts"
    assert rows[0]["state"] == "lost"


def test_durable_council_id_conflict_requires_fresh_council_id(tmp_path):
    from capt_ui.operator.council_ux import existing_council_receipt_conflict
    wf = donor_convergence_workflow(str(tmp_path))
    class Reader:
        def _query(self, request):
            assert request["op"] == "council_receipt"
            assert request["councilId"] == wf.council_id
            return {"result": {"state": "terminal", "replayForbidden": True}}
    assert "replayForbidden=True" in existing_council_receipt_conflict(Reader(), wf)
    class EmptyReader:
        def _query(self, request):
            return {"result": None}
    assert existing_council_receipt_conflict(EmptyReader(), wf) == ""
