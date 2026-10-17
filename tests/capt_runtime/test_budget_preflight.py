import pytest

from capt_runtime.composition import create_runtime
from desktop.m1_command_service import RuntimeCommandService
from tests.capt_runtime.test_model_operator import _envelope


@pytest.mark.parametrize("model", ["xiaomi/mimo-v2.6-flash", "deepseek/deepseek-v4.1-flash"])
def test_invalid_budget_does_not_issue_approval(tmp_path, model):
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        service = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        result = service.execute(_envelope("request_model_prompt_approval", {
            "objective": "Inspect repository", "targetRoot": str(tmp_path),
            "provider": "openrouter", "model": model, "requestedContextBudget": 12000,
        }, key="budget-invalid"))
        assert result["status"] == "rejected"
        assert result["error"]["code"] == "AUTHORITYVIOLATION"
        assert not runtime.store.all_aggregates()
    finally:
        runtime.close()


@pytest.mark.parametrize("model", ["xiaomi/mimo-v2.6-flash", "deepseek/deepseek-v4.1-flash"])
def test_supported_budget_is_frozen_in_approval(tmp_path, model):
    runtime = create_runtime(str(tmp_path / "ledger.db"))
    try:
        service = RuntimeCommandService(runtime.store, "operator-x", "sess-1", runtime_service=runtime.service)
        receipt = service.execute(_envelope("request_model_prompt_approval", {
            "objective": "Inspect repository", "targetRoot": str(tmp_path),
            "provider": "openrouter", "model": model, "requestedContextBudget": 32000,
        }, key="budget-supported"))
        assert receipt["status"] == "accepted", receipt
        approval = runtime.store.require_state("human_approval-" + receipt["result"]["requestId"])
        assert approval["scope"]["approvalBinding"]["requestedContextBudget"] == 32000
        assert approval["scope"]["approvalBinding"]["model"] == model
    finally:
        runtime.close()
