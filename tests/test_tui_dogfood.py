"""Dogfood regression tests for CAPT's Textual provider workbench."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from capt_ui.operator.contract import Dashboard, OperatorStatus, RuntimeHealth


class _Providers:
    def __init__(self):
        self._models = {
            "ollama": ["muse-glimmer:30b-mlx", "qwen3.6-fable-fusion:latest"],
            "openrouter": [],
        }

    def test(self, provider_id):
        return SimpleNamespace(models=list(self._models[provider_id]))

    def list(self):
        return [
            SimpleNamespace(id="ollama", name="Ollama", health=SimpleNamespace(value="green")),
            SimpleNamespace(id="openrouter", name="OpenRouter", health=SimpleNamespace(value="unknown")),
        ]

    @staticmethod
    def label(provider):
        return "LOCAL" if provider.id == "ollama" else "REMOTE"


class _Client:
    def __init__(self):
        self.calls = []

    def command(self, operation, payload, idempotency_key=None):
        self.calls.append((operation, payload, idempotency_key))
        if operation == "submit_provider_result_review":
            accepted = payload.get("disposition") == "accept"
            return {
                "status": "accepted",
                "result": {
                    "driverRunId": payload.get("driverRunId"),
                    "claimId": "cl-ui-review",
                    "verificationId": "vr-ui-review",
                    "claimState": "accepted" if accepted else "rejected",
                    "taskState": "succeeded" if accepted else "failed",
                },
            }
        return {
            "status": "accepted",
            "result": {
                "missionId": payload.get("missionId", "m-ui"),
                "taskId": payload.get("taskId", "t-ui"),
                "driverRunId": payload.get("driverRunId", "dr-ui"),
                "observations": [{"summary": "CAPT TEST"}],
                "cognitiveProvenance": {
                    "requestedContextBudget": 32000,
                    "effectiveContextBudget": 8192,
                    "promptAssemblyDigest": "sha256:test-assembly",
                },
            },
        }


    def get_state(self, stream_id):
        return {"state": "awaiting_verification"}


class _Operator:
    def __init__(self):
        self.client = _Client()
        self.connected = True
        self.approval_requests = []
        self.approval_decisions = []
        self.proposal_compiles = []
        self.proposal_approval_requests = []
        self.authoritative_approval_state = "approved"

    def dashboard(self):
        return Dashboard(status=OperatorStatus(health=RuntimeHealth.HEALTHY), verification={})

    def compile_prompt_proposal(self, payload, idempotency_key=None):
        self.proposal_compiles.append(dict(payload))
        return {
            "status": "accepted",
            "result": {
                "proposalId": "pp-ui", "revision": 0, "state": "active",
                "status": "ready_for_approval",
                "originalPrompt": payload["originalPrompt"],
                "proposedPrompt": "Compiled governed prompt for: " + payload["originalPrompt"],
                "originalPromptDigest": "sha256:" + "a" * 64,
                "proposedPromptDigest": "sha256:" + "b" * 64,
                "stageChain": ["OMNI", "META"], "stageRecords": [],
                "verificationContract": {"acceptanceCriteria": ["tests pass"]},
                "targetRoot": payload["targetRoot"],
                "provider": payload["provider"], "model": payload["model"],
                "requestedContextBudget": payload["requestedContextBudget"],
                "unresolvedQuestions": [], "rationale": "governed compiler",
            },
        }

    def request_prompt_proposal_approval(self, payload, idempotency_key=None):
        self.proposal_approval_requests.append(dict(payload))
        return {
            "status": "accepted",
            "result": {
                "requestId": "approval-proposal-ui", "missionId": "m-ui",
                "taskId": "t-ui", "driverRunId": "dr-ui",
                "promptAssemblyDigest": "sha256:" + "c" * 64,
                "proposalId": payload["proposalId"],
                "proposalRevision": payload["proposalRevision"],
                "selectedPromptKind": payload["selection"],
                "authorityProfile": payload["authorityProfile"],
            },
        }

    def request_prompt_approval(self, payload, idempotency_key=None):
        self.approval_requests.append(dict(payload))
        return {
            "requestId": "approval-ui",
            "missionId": "m-ui",
            "taskId": "t-ui",
            "driverRunId": "dr-ui",
            "promptAssemblyDigest": "sha256:" + "d" * 64,
        }

    def decide_approval(self, request_id, decision, note=None):
        self.approval_decisions.append((request_id, decision, note))
        return {"status": "accepted", "result": {"requestId": request_id, "state": "approved"}}

    def approval_state(self, request_id):
        return {"requestId": request_id, "state": self.authoritative_approval_state}


def _app(monkeypatch):
    import capt_ui.surfaces.tui.app as tui

    monkeypatch.setattr(tui, "ProviderManager", _Providers)
    import capt_ui.operator.openrouter_models as openrouter_models
    monkeypatch.setattr(
        openrouter_models,
        "available_text_models",
        lambda: [SimpleNamespace(model_id="deepseek/deepseek-v4-flash-0731")],
    )
    return tui.CaptTUI(operator=_Operator())


def test_provider_switch_invalidates_model_and_rebinds(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_model = "muse-glimmer:30b-mlx"
            app._selected_provider = "openrouter"
            app._refresh_models("openrouter", preserve_model=False)
            for _ in range(40):
                await asyncio.sleep(0.01)
                if app._selected_model == "deepseek/deepseek-v4-flash-0731":
                    break
            assert app._selected_model == "deepseek/deepseek-v4-flash-0731"
            assert "muse-glimmer:30b-mlx" not in app._model_inventory["openrouter"]
            app._selected_provider = "ollama"
            app._selected_model = ""
            app._refresh_models("ollama", preserve_model=False)
            for _ in range(40):
                await asyncio.sleep(0.01)
                if app._selected_model == "muse-glimmer:30b-mlx":
                    break
            assert app._selected_model == "muse-glimmer:30b-mlx"

    asyncio.run(run())


def test_unmounted_model_filter_change_is_ignored(monkeypatch):
    app = _app(monkeypatch)
    event = SimpleNamespace(input=SimpleNamespace(id="model-filter", is_mounted=False))

    app.on_input_changed(event)


def test_model_filter_cannot_change_command_selection_to_other_provider(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test() as pilot:
            app._selected_provider = "ollama"
            app._refresh_models("ollama", preserve_model=False)
            for _ in range(40):
                await asyncio.sleep(0.01)
                if app._model_inventory.get("ollama"):
                    break
            app.query_one("#model-filter").value = "qwen"
            await pilot.pause()
            assert app._selected_model == "qwen3.6-fable-fusion:latest"
            app._selected_provider = "openrouter"
            app._selected_model = ""
            app._refresh_models("openrouter", preserve_model=False)
            for _ in range(40):
                await asyncio.sleep(0.01)
                if app._selected_model == "deepseek/deepseek-v4-flash-0731":
                    break
            await pilot.pause()
            assert app._selected_model == "deepseek/deepseek-v4-flash-0731"

    asyncio.run(run())


def test_off_still_requires_durable_prompt_approval_before_run(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._refresh_models("ollama", preserve_model=False)
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#prompt").text = "Inspect code and report findings."
            app.action_run()
            await asyncio.sleep(0.05)
            assert not app._run_busy
            assert not app._op.client.calls
            assert "approval" in str(app.query_one("#output").render()).lower()

    asyncio.run(run())


def test_approve_binds_runtime_receipt_and_run_carries_exact_ids(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._refresh_models("ollama", preserve_model=False)
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#prompt").text = "Inspect code and report findings."

            app.action_approve_prompt()
            assert app._approval_receipt["requestId"] == "approval-ui"
            assert app._op.approval_requests[-1]["objective"] == "Inspect code and report findings."
            assert app._op.approval_decisions[-1][:2] == ("approval-ui", "approve")

            app.action_run()
            for _ in range(10):
                await asyncio.sleep(0.05)
                if not app._run_busy:
                    break

            operation, payload, _ = app._op.client.calls[-1]
            assert operation == "run_approved_hermes_inspection"
            assert payload["approvalRequestId"] == "approval-ui"
            assert payload["missionId"] == "m-ui"
            assert payload["taskId"] == "t-ui"
            assert payload["driverRunId"] == "dr-ui"
            assert payload["provider"] == "ollama"
            assert payload["model"] == "muse-glimmer:30b-mlx"
            assert "CAPT TEST" in str(app.query_one("#output").render())
            assert "dr-ui" in str(app.query_one("#current-run").render())
            assert "requested 32k / effective 8k" in str(app.query_one("#current-run").render())

    asyncio.run(run())



def test_openrouter_approval_binds_explicit_remote_authority(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_provider = "openrouter"
            app._selected_model = "qwen/qwen3.8-max-0902"
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#prompt").text = "Inspect code and report findings."
            app.query_one("#target-root").value = "/tmp/capt-project"
            app.query_one("#network-authority").value = "remote_allowed"
            app.query_one("#file-mutation").value = False
            app.query_one("#shell-authority").value = False

            app.action_approve_prompt()

            authority = app._op.approval_requests[-1]["authorityProfile"]
            assert authority["filesystemRoot"] == "/tmp/capt-project"
            assert authority["fileMutationAllowed"] is False
            assert authority["shellAccessAllowed"] is False
            assert authority["providerNetworkPolicy"] == "remote_allowed"

    asyncio.run(run())


def test_approval_decision_requires_explicit_approved_state(monkeypatch):
    app = _app(monkeypatch)
    app._op.decide_approval = lambda *args, **kwargs: {"status": "accepted", "result": {}}
    app._op.authoritative_approval_state = "requested"

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#prompt").text = "Inspect code and report findings."
            app.action_approve_prompt()
            assert not app._approval_receipt
            assert "did not record" in str(app.query_one("#output").render()).lower()

    asyncio.run(run())



def test_approval_decision_without_receipt_state_reads_authoritative_state(monkeypatch):
    app = _app(monkeypatch)
    app._op.decide_approval = lambda *args, **kwargs: {"status": "accepted", "result": {}}
    app._op.authoritative_approval_state = "approved"

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#prompt").text = "Inspect code and report findings."
            app.action_approve_prompt()
            assert app._approval_receipt["requestId"] == "approval-ui"

    asyncio.run(run())

def test_enhance_uses_runtime_prompt_proposal_without_overwriting_raw_prompt(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "AUTO"
            app.query_one("#prompt").text = "Raw operator intent."

            app.action_enhance()

            assert app._op.proposal_compiles[-1]["originalPrompt"] == "Raw operator intent."
            assert app.query_one("#prompt").text == "Raw operator intent."
            assert app._prompt_proposal["proposalId"] == "pp-ui"
            rendered = str(app.query_one("#output").render())
            assert "Compiled governed prompt" in rendered
            assert "pp-ui" in rendered

    asyncio.run(run())


def test_enhanced_approval_binds_proposal_revision_and_selection(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "AUTO"
            app.query_one("#prompt").text = "Raw operator intent."
            app.action_enhance()
            app.query_one("#proposal-selection").value = "upgrade"

            app.action_approve_prompt()

            payload = app._op.proposal_approval_requests[-1]
            assert payload["proposalId"] == "pp-ui"
            assert payload["proposalRevision"] == 0
            assert payload["selection"] == "upgrade"
            assert payload["authorityProfile"]["filesystemRoot"] == str(Path.cwd())
            assert app._approval_receipt["requestId"] == "approval-proposal-ui"

    asyncio.run(run())

def test_edit_after_approval_invalidates_receipt_and_blocks_run(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test() as pilot:
            app._selected_provider = "ollama"
            app._refresh_models("ollama", preserve_model=False)
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#prompt").text = "Inspect code and report findings."
            app.action_approve_prompt()
            assert app._approval_receipt

            app.query_one("#prompt").text = "Inspect code and report different findings."
            await pilot.pause()
            assert not app._approval_receipt

            app.action_run()
            await pilot.pause()
            assert not app._op.client.calls
            assert "approval" in str(app.query_one("#output").render()).lower()

    asyncio.run(run())


def test_printable_input_is_not_stolen_by_global_navigation(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test() as pilot:
            await pilot.click("#prompt")
            await pilot.press("p")
            assert app.query_one("#prompt").text == "p"

    asyncio.run(run())


def test_mouse_to_keyboard_recovery_focuses_provider(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test() as pilot:
            await pilot.click("#current-run")
            await pilot.press("p")
            assert app.focused is app.query_one("#provider-select")

    asyncio.run(run())



def test_dispatch_transport_failure_preserves_approval_for_retry(monkeypatch):
    app = _app(monkeypatch)

    def fail_command(*args, **kwargs):
        raise OSError("socket closed before authoritative disposition")

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#prompt").text = "Inspect code and report findings."
            app.action_approve_prompt()
            assert app._approval_receipt["requestId"] == "approval-ui"
            app._op.client.command = fail_command

            app.action_run()
            for _ in range(20):
                await asyncio.sleep(0.02)
                if not app._run_busy:
                    break

            assert app._approval_receipt["requestId"] == "approval-ui"
            assert "socket closed" in str(app.query_one("#output").render()).lower()

    asyncio.run(run())


def test_approval_cursor_survives_inflight_then_clears_after_accepted_dispatch(monkeypatch):
    import threading

    app = _app(monkeypatch)
    entered = threading.Event()
    release = threading.Event()

    def blocking_command(operation, payload, idempotency_key=None):
        entered.set()
        release.wait(timeout=2)
        return _Client().command(operation, payload, idempotency_key)

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#prompt").text = "Inspect code and report findings."
            app.action_approve_prompt()
            app._op.client.command = blocking_command

            app.action_run()
            for _ in range(40):
                await asyncio.sleep(0.01)
                if entered.is_set():
                    break
            assert entered.is_set()
            assert app._approval_receipt["requestId"] == "approval-ui"

            release.set()
            for _ in range(40):
                await asyncio.sleep(0.02)
                if not app._run_busy:
                    break
            assert not app._approval_receipt

    asyncio.run(run())


def test_model_inventory_refresh_is_dispatched_off_ui_path(monkeypatch):
    import time

    app = _app(monkeypatch)

    class SlowProviders(_Providers):
        def test(self, provider_id):
            time.sleep(0.20)
            return SimpleNamespace(models=["slow-model"])

    async def run():
        async with app.run_test():
            app._providers = SlowProviders()
            app._selected_provider = "ollama"
            started = time.perf_counter()
            app._refresh_models("ollama", preserve_model=False)
            elapsed = time.perf_counter() - started
            assert elapsed < 0.05
            for _ in range(40):
                await asyncio.sleep(0.02)
                if app._model_inventory.get("ollama") == ["slow-model"]:
                    break
            assert app._model_inventory["ollama"] == ["slow-model"]

    asyncio.run(run())


def test_output_preserves_tail_authority_code_beyond_2000_chars(monkeypatch):
    app = _app(monkeypatch)
    tail = "AUTHORITY_PROVIDER_NETWORK_POLICY_INVALID"
    payload = "x" * 2500 + tail

    async def run():
        async with app.run_test():
            app._show_output(payload)
            rendered = str(app.query_one("#output").render())
            assert tail in rendered
            assert len(rendered) > 2500

    asyncio.run(run())

def test_failure_releases_busy_with_visible_safe_error(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._run_busy = True
            app.query_one("#run").disabled = True
            app._finish_run("openrouter", "deepseek/deepseek-v4-flash-0731", None, "PROVIDER_CREDENTIAL_UNAVAILABLE")
            assert app._run_busy is False
            assert app.query_one("#run").disabled is False
            assert "PROVIDER_CREDENTIAL_UNAVAILABLE" in str(app.query_one("#output").render())

    asyncio.run(run())


def test_compiler_unavailable_defaults_to_original_and_remains_approvable(monkeypatch):
    app = _app(monkeypatch)
    original_compile = app._op.compile_prompt_proposal

    def unavailable(payload, idempotency_key=None):
        receipt = original_compile(payload, idempotency_key)
        result = receipt["result"]
        result["status"] = "compiler_unavailable"
        result["proposedPrompt"] = result["originalPrompt"]
        result["proposedPromptDigest"] = result["originalPromptDigest"]
        result["stageRecords"] = [{"stage": "OMNI", "executionEnabled": False}]
        return receipt

    app._op.compile_prompt_proposal = unavailable

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "AUTO"
            app.query_one("#prompt").text = "Literal fallback intent."
            app.action_enhance()
            assert app._prompt_proposal["status"] == "compiler_unavailable"
            assert app.query_one("#proposal-selection").value == "original"
            app.action_approve_prompt()
            assert app._op.proposal_approval_requests[-1]["selection"] == "original"
            assert app._approval_receipt["requestId"] == "approval-proposal-ui"

    asyncio.run(run())


def test_proposal_approved_run_dispatches_selected_prompt_with_enhancement_off(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "AUTO"
            app.query_one("#prompt").text = "Raw operator intent."
            app.action_enhance()
            app.query_one("#proposal-selection").value = "upgrade"
            app.action_approve_prompt()
            app.action_run()
            for _ in range(30):
                await asyncio.sleep(0.02)
                if not app._run_busy:
                    break
            operation, payload, _ = app._op.client.calls[-1]
            assert operation == "run_approved_hermes_inspection"
            assert payload["objective"] == "Compiled governed prompt for: Raw operator intent."
            assert payload["promptEnhancement"] == "OFF"

    asyncio.run(run())


def test_run_uses_exact_approved_target_root(monkeypatch):
    app = _app(monkeypatch)
    approved_root = "/tmp/capt-project"

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "OFF"
            app.query_one("#target-root").value = approved_root
            app.query_one("#prompt").text = "Inspect approved root."
            app.action_approve_prompt()
            app.action_run()
            for _ in range(30):
                await asyncio.sleep(0.02)
                if not app._run_busy:
                    break
            _, payload, _ = app._op.client.calls[-1]
            assert payload["targetRoot"] == approved_root

    asyncio.run(run())


def test_deterministic_clarification_without_executed_stage_blocks_tui_approval(monkeypatch):
    app = _app(monkeypatch)
    original_compile = app._op.compile_prompt_proposal

    def clarification(payload, idempotency_key=None):
        receipt = original_compile(payload, idempotency_key)
        result = receipt["result"]
        result["status"] = "clarification_required"
        result["proposedPrompt"] = result["originalPrompt"]
        result["proposedPromptDigest"] = result["originalPromptDigest"]
        result["stageRecords"] = [{"stage": "OMNI", "executionEnabled": False}]
        result["unresolvedQuestions"] = ["Clarify the intended outcome and scope before execution."]
        return receipt

    app._op.compile_prompt_proposal = clarification

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._selected_model = "muse-glimmer:30b-mlx"
            app.query_one("#enhancement-select").value = "AUTO"
            app.query_one("#prompt").text = "Do it."
            app.action_enhance()
            assert app._prompt_proposal["status"] == "clarification_required"
            assert app._enhancement_ready is False
            app.action_approve_prompt()
            assert not app._op.proposal_approval_requests
            assert not app._approval_receipt
            assert "clarif" in str(app.query_one("#output").render()).lower()

    asyncio.run(run())


def test_tui_human_review_closes_awaiting_provider_result_without_rerun(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._current_run = {
                "provider": "openrouter",
                "model": "deepseek/deepseek-v4-flash-0731",
                "status": "accepted",
                "driverRunId": "dr-ui-review",
                "missionId": "m-ui",
                "taskId": "t-ui",
                "taskState": "awaiting_verification",
            }
            app.query_one("#verification-note").value = "Visible result satisfies the acceptance criterion."
            app._sync_review_controls()
            app.action_review_result("accept")
            for _ in range(40):
                await asyncio.sleep(0.02)
                if app._current_run.get("taskState") == "succeeded":
                    break
            review_calls = [call for call in app._op.client.calls if call[0] == "submit_provider_result_review"]
            assert len(review_calls) == 1
            assert review_calls[0][1] == {
                "driverRunId": "dr-ui-review",
                "disposition": "accept",
                "note": "Visible result satisfies the acceptance criterion.",
            }
            assert app._current_run["taskState"] == "succeeded"
            assert not any(call[0] == "run_approved_hermes_inspection" for call in app._op.client.calls)
            assert app.query_one("#verify-accept").disabled
            assert app.query_one("#verify-reject").disabled

    asyncio.run(run())
