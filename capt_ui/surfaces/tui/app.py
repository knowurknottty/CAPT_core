"""CAPT Textual operator console.

The console is a RuntimeService client. It owns only interaction state: current
provider/model selection, prompt-edit state, focus, and command receipts.
RuntimeService and EventStore remain authoritative for approvals, mission/task
state, DriverRuns, evidence, verification, and ClaimGuard truth.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Checkbox, Footer, Header, Input, Select, Static, TextArea

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from capt_ui.operator.bootstrap import resolve_runtime  # noqa: E402
from capt_ui.operator.providers import ProviderManager  # noqa: E402
from capt_ui.operator.runtime import Operator  # noqa: E402
from capt_ui.operator.verbosity import CaveCAPT  # noqa: E402
from capt_ui.operator.prompt_intelligence import (  # noqa: E402
    CONTEXT_BUDGETS,
    ENGINES,
    RESPONSE_MODES,
    PromptPreferences,
    inspect_prompt,
)


class StatusBar(Static):
    """Top line deliberately reports live selection, not stale preferences."""

    status = reactive({})

    def render(self) -> str:
        s = self.status
        health = s.get("health", "unknown").upper()
        model = s.get("model") or "none selected"
        provider = s.get("provider") or "none selected"
        run = s.get("run") or "idle"
        return f"CAPT | Runtime {health} | Selected {provider}/{model} | Run {run}"


class MissionPanel(Static):
    missions = reactive([])

    def render(self) -> str:
        if not self.missions:
            return "Mission\n-------\n<none>"
        lines = [
            "Mission history (authoritative projection)",
            "----------------------------------------",
        ]
        for mission in self.missions[:6]:
            lines.append(
                "  %s  %s"
                % (mission.get("state", "?"), mission.get("objective", "")[:48])
            )
        return "\n".join(lines)


class EvidencePanel(Static):
    result = reactive({})

    def render(self) -> str:
        result = self.result
        verification = result.get("verification", {})
        status = (
            verification.get("status", {}).get("kind", "unknown")
            if isinstance(verification, dict)
            else "unknown"
        )
        current = result.get("current", "No current run receipt")
        return (
            "Current run / evidence\n----------------------\n%s\n"
            "Latest verification: %s\n%s"
            % (current, status, result.get("note", "Projection may include historical state."))
        )


class ProviderPanel(Static):
    text = reactive("")

    def render(self) -> str:
        return self.text or "Provider health\n---------------\n<none>"


class LogPanel(Static):
    logs = reactive([])

    def render(self) -> str:
        if not self.logs:
            return "Logs\n----\n<none>"
        lines = ["Recent authoritative events", "---------------------------"]
        for event in self.logs[:8]:
            payload = event.get("payload", {})
            lines.append(
                "  %s %s"
                % (event.get("globalSequence", "?"), payload.get("eventType", "?"))
            )
        return "\n".join(lines)


class CaptTUI(App):
    """Keyboard-first governed provider console."""

    TITLE = "CAPT"
    SUB_TITLE = "operator console"
    CSS = """
    #workbench { height: auto; }
    #left, #center, #right { width: 1fr; padding: 1; }
    #model-filter, #prompt, #provider-select, #model-select { margin: 1 0; }
    #output, #current-run { height: auto; min-height: 5; }
    Button { margin-right: 1; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("p", "focus_provider", "Provider"),
        Binding("m", "focus_model", "Model"),
        Binding("/", "focus_model_filter", "Search models"),
        Binding("ctrl+enter", "run", "Run"),
        Binding("c", "checkpoint", "Checkpoint"),
        Binding("f5", "refresh", "Refresh evidence"),
        Binding("f6", "focus_prompt", "Prompt"),
        Binding("f7", "focus_logs", "Logs"),
        Binding("v", "cyclev", "Verbosity"),
    ]

    def __init__(self, operator: Optional[Operator] = None) -> None:
        super().__init__()
        self._op = operator
        self._providers: ProviderManager | None = None
        self._verbosity: CaveCAPT | None = None
        self._selected_provider = "ollama"
        self._selected_model = ""
        self._model_inventory: dict[str, list[str]] = {}
        self._model_generation = 0
        self._current_run: dict[str, Any] = {}
        self._run_busy = False
        self._prompt_preferences: PromptPreferences | None = None
        self._enhancement_ready = False
        self._approval_receipt: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield StatusBar(id="status")
            with Horizontal(id="workbench"):
                with Vertical(id="left"):
                    yield MissionPanel(id="mission")
                    yield EvidencePanel(id="evidence")
                with Vertical(id="center"):
                    yield Static("Governed provider run", id="run-title")
                    yield Select(
                        [("Ollama", "ollama"), ("OpenRouter", "openrouter")],
                        value="ollama",
                        id="provider-select",
                    )
                    yield Input(
                        placeholder="Filter models. Tab selects the model list.",
                        id="model-filter",
                    )
                    with Horizontal():
                        yield Select([], id="model-select")
                        yield Select(
                            [(mode, mode) for mode in RESPONSE_MODES],
                            value="SPOCK",
                            id="response-mode",
                        )
                        yield Select(
                            [
                                ("%sk" % (budget // 1000), str(budget))
                                for budget in CONTEXT_BUDGETS
                            ],
                            value="32000",
                            id="context-budget",
                        )
                        yield Select(
                            [(engine, engine) for engine in ENGINES],
                            value="AUTO",
                            id="enhancement-select",
                        )
                        yield Checkbox(
                            "Human result verification",
                            value=True,
                            id="human-verification",
                        )
                    yield TextArea("", id="prompt")
                    with Horizontal():
                        yield Button("ENHANCE", id="enhance")
                        yield Button("APPROVE", id="approve")
                        yield Button("RUN", id="run", variant="success")
                        yield Button("CHECKPOINT", id="checkpoint")
                    yield Static(
                        "Current run\n-----------\nNo run submitted.",
                        id="current-run",
                    )
                    yield Static("Output\n------\n<none>", id="output")
                with Vertical(id="right"):
                    yield ProviderPanel(id="provider")
                    yield LogPanel(id="logs")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh()
        self.query_one("#provider-select", Select).focus()

    def action_refresh(self) -> None:
        if self._op is None:
            sock, token = resolve_runtime()
            if not (sock and token):
                self._set_status("runtime unavailable")
                return
            try:
                self._op = Operator(sock, token)
                self._op.connect()
            except Exception as exc:  # noqa: BLE001
                self._set_status("connect failed: %s" % str(exc)[:80])
                return
        if self._providers is None:
            self._providers = ProviderManager()
            self._verbosity = CaveCAPT()
            self._prompt_preferences = PromptPreferences()
            self.query_one("#response-mode", Select).value = (
                self._prompt_preferences.response_mode
            )
            self.query_one("#context-budget", Select).value = str(
                self._prompt_preferences.context_budget
            )
            self.query_one("#human-verification", Checkbox).value = (
                self._prompt_preferences.human_verification_required
            )
        try:
            dashboard = self._op.dashboard()
        except Exception as exc:  # noqa: BLE001
            self._set_status("dashboard failed: %s" % str(exc)[:80])
            return
        self.query_one("#mission", MissionPanel).missions = dashboard.missions
        self.query_one("#logs", LogPanel).logs = dashboard.events
        self._refresh_provider_health()
        self._refresh_models(self._selected_provider, preserve_model=True)
        self._render_evidence(dashboard.verification)
        self._set_status(dashboard.status.health.value)

    def _set_status(self, health: str) -> None:
        self.query_one("#status", StatusBar).status = {
            "health": health,
            "provider": self._selected_provider,
            "model": self._selected_model,
            "run": "running"
            if self._run_busy
            else self._current_run.get("status", "idle"),
        }

    def _refresh_provider_health(self) -> None:
        if not self._providers:
            return
        lines = [
            "Provider health (availability only)",
            "-----------------------------------",
        ]
        for provider in self._providers.list():
            marker = ">" if provider.id == self._selected_provider else " "
            lines.append(
                "%s %s [%s] %s"
                % (
                    marker,
                    provider.name,
                    self._providers.label(provider),
                    provider.health.value,
                )
            )
        self.query_one("#provider", ProviderPanel).text = "\n".join(lines)

    def _refresh_models(self, provider_id: str, *, preserve_model: bool) -> None:
        """Scope inventory to provider and reject stale selections immediately."""
        if not self._providers:
            return
        generation = self._model_generation = self._model_generation + 1
        models: list[str] = []
        error = ""
        try:
            if provider_id == "ollama":
                provider = self._providers.test("ollama")
                models = list(provider.models)
            elif provider_id == "openrouter":
                from capt_ui.operator.openrouter_models import available_text_models

                models = [
                    entry.model_id for entry in available_text_models() if entry.model_id
                ]
            else:
                error = "Provider execution is not implemented for %s." % provider_id
        except Exception as exc:  # noqa: BLE001
            error = "Provider inventory unavailable: %s" % str(exc)[:120]
        if generation != self._model_generation or provider_id != self._selected_provider:
            return
        self._model_inventory[provider_id] = models
        if not preserve_model:
            self.query_one("#model-filter", Input).value = ""
        if not preserve_model or self._selected_model not in models:
            self._selected_model = models[0] if models else ""
        self._apply_model_filter()
        if error:
            self._show_output(error)
        self._refresh_provider_health()
        self._set_status("connected" if self._op and self._op.connected else "unknown")

    def _apply_model_filter(self) -> None:
        raw = self.query_one("#model-filter", Input).value.strip().lower()
        models = self._model_inventory.get(self._selected_provider, [])
        visible = [model for model in models if raw in model.lower()]
        options = [(model, model) for model in visible] or [
            ("<no matching model>", "")
        ]
        select = self.query_one("#model-select", Select)
        select.set_options(options)
        if self._selected_model in visible:
            select.value = self._selected_model
        else:
            self._selected_model = visible[0] if visible else ""
            select.value = self._selected_model
        self._set_status("connected" if self._op and self._op.connected else "unknown")

    def _show_output(self, text: str) -> None:
        self.query_one("#output", Static).update("Output\n------\n%s" % text[:2000])

    def _render_evidence(self, verification: dict[str, Any]) -> None:
        current = self._current_run
        if current:
            summary = "Run %s\nProvider/model: %s/%s\nState: %s" % (
                current.get("driverRunId", "unknown"),
                current.get("provider", "?"),
                current.get("model", "?"),
                current.get("status", "unknown"),
            )
        else:
            summary = "No current run receipt"
        self.query_one("#evidence", EvidencePanel).result = {
            "verification": verification,
            "current": summary,
            "note": (
                "Verification shown is the latest authoritative projection. "
                "Correlate by DriverRun ID above."
            ),
        }

    def _invalidate_prompt_approval(self) -> None:
        self._approval_receipt = {}

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-select":
            provider = str(event.value)
            if provider and provider != self._selected_provider:
                self._invalidate_prompt_approval()
                self._selected_provider = provider
                self._selected_model = ""
                self._refresh_models(provider, preserve_model=False)
        elif event.select.id == "model-select":
            model = str(event.value)
            if model and model != self._selected_model:
                self._invalidate_prompt_approval()
                self._selected_model = model
                self._set_status(
                    "connected" if self._op and self._op.connected else "unknown"
                )
        elif event.select.id in ("response-mode", "context-budget"):
            self._invalidate_prompt_approval()
            self._persist_prompt_preferences()
        elif event.select.id == "enhancement-select":
            self._invalidate_prompt_approval()
            self._enhancement_ready = False

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "model-filter":
            self._apply_model_filter()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "prompt":
            self._invalidate_prompt_approval()
            self._enhancement_ready = False

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "human-verification":
            self._invalidate_prompt_approval()
            self._persist_prompt_preferences()

    def _persist_prompt_preferences(self) -> None:
        if self._prompt_preferences is None:
            return
        self._prompt_preferences.set(
            response_mode=str(self.query_one("#response-mode", Select).value),
            context_budget=int(str(self.query_one("#context-budget", Select).value)),
            human_verification_required=self.query_one(
                "#human-verification", Checkbox
            ).value,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self.action_run()
        elif event.button.id == "checkpoint":
            self.action_checkpoint()
        elif event.button.id == "enhance":
            self.action_enhance()
        elif event.button.id == "approve":
            self.action_approve_prompt()

    def action_focus_provider(self) -> None:
        self.query_one("#provider-select", Select).focus()

    def action_focus_model(self) -> None:
        self.query_one("#model-select", Select).focus()

    def action_focus_model_filter(self) -> None:
        self.query_one("#model-filter", Input).focus()

    def action_focus_prompt(self) -> None:
        self.query_one("#prompt", TextArea).focus()

    def action_focus_logs(self) -> None:
        self.query_one("#logs", LogPanel).focus()

    def action_cyclev(self) -> None:
        if self._verbosity:
            self._verbosity.toggle(1)
            self.notify("CaveCAPT verbosity: %s" % self._verbosity.value.label)

    def action_enhance(self) -> None:
        prompt_area = self.query_one("#prompt", TextArea)
        proposal = inspect_prompt(
            prompt_area.text,
            str(self.query_one("#enhancement-select", Select).value),
        )
        self._invalidate_prompt_approval()
        self._enhancement_ready = False
        if proposal.questions:
            self._show_output(
                "Clarification required before optimization:\n- "
                + "\n- ".join(proposal.questions)
            )
            return
        with prompt_area.prevent(TextArea.Changed):
            prompt_area.text = proposal.optimized_prompt
        self._enhancement_ready = True
        self._show_output(
            "Proposed %s enhancement: %s\n"
            "Review the exact visible prompt, then APPROVE before RUN."
            % (proposal.engine, proposal.rationale)
        )

    def action_approve_prompt(self) -> None:
        if not self._op:
            self.notify("Runtime unavailable.", severity="error")
            return
        prompt = self.query_one("#prompt", TextArea).text.strip()
        if not prompt or not self._selected_model:
            self._show_output(
                "Approval rejected locally: select an available model and enter a prompt."
            )
            return
        engine = str(self.query_one("#enhancement-select", Select).value)
        if engine != "OFF" and not self._enhancement_ready:
            self._show_output(
                "Approval blocked locally: ENHANCE first, review the resulting prompt, then APPROVE."
            )
            self.notify("Enhance and review before approval.", severity="warning")
            return

        payload = {
            "provider": self._selected_provider,
            "model": self._selected_model,
            "objective": prompt,
            "targetRoot": str(Path.cwd()),
            "promptEnhancement": engine,
            "responseMode": str(self.query_one("#response-mode", Select).value),
            "requestedContextBudget": int(str(self.query_one("#context-budget", Select).value)),
            "humanVerificationRequired": self.query_one("#human-verification", Checkbox).value,
        }
        try:
            request_receipt = self._op.request_prompt_approval(
                payload, "tui-approval-" + uuid.uuid4().hex
            )
            if request_receipt.get("status") == "rejected":
                detail = request_receipt.get("detail") or request_receipt.get("error")
                raise RuntimeError("prompt approval request rejected: %s" % detail)
            planned = request_receipt.get("result", request_receipt)
            required = (
                "requestId",
                "missionId",
                "taskId",
                "driverRunId",
                "promptAssemblyDigest",
            )
            if any(not planned.get(key) for key in required):
                raise RuntimeError("runtime returned incomplete prompt approval receipt")
            decision = self._op.decide_approval(
                str(planned["requestId"]),
                "approve",
                note="Approved exact TUI model-visible prompt assembly.",
            )
            if decision.get("status") == "rejected":
                detail = decision.get("detail") or decision.get("error")
                raise RuntimeError("prompt approval decision rejected: %s" % detail)
            state = decision.get("result", {}).get("state")
            if state not in (None, "approved"):
                raise RuntimeError("runtime did not record prompt approval as approved")
            self._approval_receipt = dict(planned)
            self._show_output(
                "Runtime approval recorded.\nRequest: %s\nPromptAssembly: %s\n"
                "Any prompt or run-setting edit invalidates this local receipt."
                % (
                    planned["requestId"],
                    str(planned["promptAssemblyDigest"])[:28],
                )
            )
            self.notify("Exact prompt assembly approved by operator.")
        except Exception as exc:  # noqa: BLE001
            self._invalidate_prompt_approval()
            self._show_output("Approval failed: %s" % str(exc)[:240])
            self.notify("Prompt approval failed", severity="error")

    def action_checkpoint(self) -> None:
        if not self._op:
            self.notify("Runtime unavailable.", severity="error")
            return
        try:
            self._op.checkpoint()
            self.notify("Checkpoint accepted")
            self.action_refresh()
        except Exception as exc:  # noqa: BLE001
            self.notify(
                "Checkpoint failed: %s" % str(exc)[:120], severity="error"
            )

    def action_run(self) -> None:
        if self._run_busy:
            self.notify("A governed run is already active.", severity="warning")
            return
        if not self._op:
            self.notify("Runtime unavailable.", severity="error")
            return
        prompt = self.query_one("#prompt", TextArea).text.strip()
        if not prompt or not self._selected_model:
            self._show_output(
                "Run rejected locally: select an available model and enter a prompt."
            )
            self.notify("Select an available model and enter a prompt.", severity="error")
            return
        if not self._approval_receipt:
            self._show_output(
                "Run blocked locally: RuntimeService approval for this exact prompt "
                "assembly is required. APPROVE before RUN."
            )
            self.notify("Durable prompt approval required.", severity="warning")
            return

        engine = str(self.query_one("#enhancement-select", Select).value)
        verification_required = self.query_one("#human-verification", Checkbox).value
        approval = dict(self._approval_receipt)
        self._invalidate_prompt_approval()  # single-use in the TUI; replay stays runtime-governed
        self._run_busy = True
        self.query_one("#run", Button).disabled = True
        self._current_run = {
            "provider": self._selected_provider,
            "model": self._selected_model,
            "status": "submitting",
            "approvalRequestId": approval.get("requestId", ""),
        }
        self._show_current_run()
        self._set_status("connected")
        self._dispatch_run(
            self._selected_provider,
            self._selected_model,
            prompt,
            engine,
            str(self.query_one("#response-mode", Select).value),
            int(str(self.query_one("#context-budget", Select).value)),
            verification_required,
            approval,
        )

    @work(thread=True, exclusive=True)
    def _dispatch_run(
        self,
        provider: str,
        model: str,
        prompt: str,
        engine: str,
        response_mode: str,
        context_budget: int,
        verification_required: bool,
        approval: dict[str, Any],
    ) -> None:
        """Run the blocking socket operation off the Textual event loop."""
        receipt: dict[str, Any] | None = None
        error = ""
        try:
            assert self._op is not None
            receipt = self._op.client.command(
                "run_approved_hermes_inspection",
                {
                    "provider": provider,
                    "model": model,
                    "objective": prompt,
                    "targetRoot": str(Path.cwd()),
                    "promptEnhancement": engine,
                    "responseMode": response_mode,
                    "requestedContextBudget": context_budget,
                    "humanVerificationRequired": verification_required,
                    "approvalRequestId": approval["requestId"],
                    "missionId": approval["missionId"],
                    "taskId": approval["taskId"],
                    "driverRunId": approval["driverRunId"],
                },
                "tui-run-" + uuid.uuid4().hex,
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)[:240]
        self.call_from_thread(self._finish_run, provider, model, receipt, error)

    def _finish_run(
        self,
        provider: str,
        model: str,
        receipt: dict[str, Any] | None,
        error: str,
    ) -> None:
        self._run_busy = False
        self.query_one("#run", Button).disabled = False
        approval_request_id = self._current_run.get("approvalRequestId", "")
        if error:
            self._current_run = {
                "provider": provider,
                "model": model,
                "status": "failed",
                "approvalRequestId": approval_request_id,
            }
            self._show_output("Run failed: %s" % error)
            self.notify("Run failed", severity="error")
        else:
            receipt = receipt or {}
            result = receipt.get("result", {}) if isinstance(receipt, dict) else {}
            observation = (result.get("observations") or [{}])[0].get("summary", "")
            status = str(receipt.get("status", "unknown"))
            self._current_run = {
                "provider": provider,
                "model": model,
                "status": status,
                "approvalRequestId": approval_request_id,
                "driverRunId": result.get("driverRunId", ""),
                "missionId": result.get("missionId", ""),
                "taskId": result.get("taskId", ""),
                "outcome": result.get("outcome", ""),
                "cognitiveProvenance": result.get("cognitiveProvenance", {}),
            }
            self._show_output(
                observation
                or (
                    "Run %s. %s"
                    % (status, result.get("outcome", "No output observation."))
                )
            )
            self.notify(
                "Run %s" % status,
                severity="information" if status == "accepted" else "warning",
            )
        self._show_current_run()
        self.action_refresh()

    def _show_current_run(self) -> None:
        current = self._current_run
        text = "Current run\n-----------\nProvider/model: %s/%s\nState: %s" % (
            current.get("provider", "?"),
            current.get("model", "?"),
            current.get("status", "idle"),
        )
        if current.get("approvalRequestId"):
            text += "\nApproval: %s" % current["approvalRequestId"]
        if current.get("driverRunId"):
            text += "\nDriverRun: %s\nMission: %s" % (
                current["driverRunId"],
                current.get("missionId", ""),
            )
        if current.get("outcome"):
            text += "\nOutcome: %s" % current["outcome"]
        provenance = current.get("cognitiveProvenance") or {}
        if provenance:
            effective = provenance.get("effectiveContextBudget")
            effective_label = (
                "%sk" % (int(effective) // 1000) if effective is not None else "unknown"
            )
            text += "\nContext: requested %sk / effective %s" % (
                int(provenance.get("requestedContextBudget", 0)) // 1000,
                effective_label,
            )
            text += "\nPromptAssembly: %s" % str(
                provenance.get("promptAssemblyDigest", "unknown")
            )[:20]
        self.query_one("#current-run", Static).update(text)


def main() -> int:
    CaptTUI().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
