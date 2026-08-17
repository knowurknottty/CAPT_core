"""Dogfood regression tests for CAPT's Textual provider workbench."""

from __future__ import annotations

import asyncio
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


class _Operator:
    def __init__(self):
        self.client = _Client()
        self.connected = True
        self.approval_requests = []
        self.approval_decisions = []

    def dashboard(self):
        return Dashboard(status=OperatorStatus(health=RuntimeHealth.HEALTHY), verification={})

    def request_prompt_approval(self, payload):
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


def _app(monkeypatch):
    import capt_ui.surfaces.tui.app as tui

    monkeypatch.setattr(tui, "ProviderManager", _Providers)
    monkeypatch.setattr(tui, "available_text_models", lambda: []) if hasattr(tui, "available_text_models") else None
    return tui.CaptTUI(operator=_Operator())


def test_provider_switch_invalidates_model_and_rebinds(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_model = "muse-glimmer:30b-mlx"
            app._selected_provider = "openrouter"
            app._refresh_models("openrouter", preserve_model=False)
            assert app._selected_model == "deepseek/deepseek-v4-flash-0731"
            assert "muse-glimmer:30b-mlx" not in app._model_inventory["openrouter"]
            app._selected_provider = "ollama"
            app._selected_model = ""
            app._refresh_models("ollama", preserve_model=False)
            assert app._selected_model == "muse-glimmer:30b-mlx"

    asyncio.run(run())


def test_model_filter_cannot_change_command_selection_to_other_provider(monkeypatch):
    app = _app(monkeypatch)

    async def run():
        async with app.run_test():
            app._selected_provider = "ollama"
            app._refresh_models("ollama", preserve_model=False)
            app.query_one("#model-filter").value = "qwen"
            app._apply_model_filter()
            assert app._selected_model == "qwen3.6-fable-fusion:latest"
            app._selected_provider = "openrouter"
            app._selected_model = ""
            app._refresh_models("openrouter", preserve_model=False)
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
