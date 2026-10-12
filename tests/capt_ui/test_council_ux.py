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
