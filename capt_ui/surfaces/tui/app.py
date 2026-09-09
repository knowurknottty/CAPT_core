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
from textual.css.query import NoMatches
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
    can_focus = True
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


class OutputPanel(Static):
    can_focus = True



class CaptTUI(App):
    """Keyboard-first governed provider console."""

    TITLE = "CAPT"
    SUB_TITLE = "operator console"
    CSS = """
    #workbench { height: auto; }
    #left, #center, #right { width: 1fr; padding: 1; }
    #model-filter, #prompt, #provider-select, #model-select { margin: 1 0; }
    #current-run { height: auto; min-height: 5; }
    #output { height: 1fr; min-height: 8; overflow-y: auto; }
    #logs { overflow-y: auto; }
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
        self._prompt_proposal: dict[str, Any] = {}
        self._approval_receipt: dict[str, Any] = {}
        self._approval_basis: tuple[Any, ...] | None = None

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
                    yield Input(value=str(Path.cwd()), placeholder="Execution target root", id="target-root")
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
                        yield Select(
                            [("Use upgrade", "upgrade"), ("Use original", "original")],
                            value="upgrade",
                            id="proposal-selection",
                        )
                        yield Checkbox(
                            "Human result verification",
                            value=True,
                            id="human-verification",
                        )
                    with Horizontal():
                        yield Select(
                            [("Local network only", "local_only"), ("Allow remote provider", "remote_allowed")],
                            value="local_only",
                            id="network-authority",
                        )
                        yield Checkbox("File mutation", value=False, id="file-mutation")
                        yield Checkbox("Shell execution", value=False, id="shell-authority")
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
                    yield Input(
                        placeholder="Human verification note (optional)",
                        id="verification-note",
                        disabled=True,
                    )
                    with Horizontal():
                        yield Button("VERIFY & ACCEPT", id="verify-accept", disabled=True)
                        yield Button("REJECT RESULT", id="verify-reject", variant="error", disabled=True)
                    yield OutputPanel("Output\n------\n<none>", id="output")
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
        try:
            status_bar = self.query_one("#status", StatusBar)
        except NoMatches:
            # Select/Input events may still drain while Textual is unmounting the
            # screen. Status is presentation-only, so teardown must not turn a
            # stale UI callback into an application failure.
            return
        status_bar.status = {
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
        """Schedule provider inventory work without blocking the Textual event loop."""
        if not self._providers:
            return
        generation = self._model_generation = self._model_generation + 1
        if not preserve_model:
            self.query_one("#model-filter", Input).value = ""
        self._load_models(provider_id, preserve_model, generation)

    @work(thread=True)
    def _load_models(self, provider_id: str, preserve_model: bool, generation: int) -> None:
        models: list[str] = []
        error = ""
        try:
            assert self._providers is not None
            if provider_id == "ollama":
                provider = self._providers.test("ollama")
                models = list(provider.models)
            elif provider_id == "openrouter":
                from capt_ui.operator.openrouter_models import available_text_models

                models = [entry.model_id for entry in available_text_models() if entry.model_id]
            else:
                error = "Provider execution is not implemented for %s." % provider_id
        except Exception as exc:  # noqa: BLE001
            error = "Provider inventory unavailable: %s" % str(exc)
        self.call_from_thread(
            self._apply_model_inventory, provider_id, preserve_model, generation, models, error
        )

    def _apply_model_inventory(
        self, provider_id: str, preserve_model: bool, generation: int,
        models: list[str], error: str,
    ) -> None:
        if generation != self._model_generation or provider_id != self._selected_provider:
            return
        self._model_inventory[provider_id] = models
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
        self.query_one("#output", OutputPanel).update("Output\n------\n%s" % text)

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

    def _current_approval_basis(self) -> tuple[Any, ...]:
        return (
            self._selected_provider,
            self._selected_model,
            self.query_one("#prompt", TextArea).text,
            self.query_one("#target-root", Input).value.strip(),
            str(self.query_one("#enhancement-select", Select).value),
            str(self.query_one("#proposal-selection", Select).value),
            self._prompt_proposal.get("proposalId"),
            self._prompt_proposal.get("revision"),
            str(self.query_one("#response-mode", Select).value),
            int(str(self.query_one("#context-budget", Select).value)),
            self.query_one("#human-verification", Checkbox).value,
            str(self.query_one("#network-authority", Select).value),
            self.query_one("#file-mutation", Checkbox).value,
            self.query_one("#shell-authority", Checkbox).value,
        )

    def _invalidate_prompt_proposal(self) -> None:
        self._prompt_proposal = {}
        self._enhancement_ready = False

    def _invalidate_prompt_approval(self, *, force: bool = False) -> None:
        if (
            not force
            and self._approval_receipt
            and self._approval_basis == self._current_approval_basis()
        ):
            return
        self._approval_receipt = {}
        self._approval_basis = None

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is Select.BLANK or event.value is Select.NULL:
            return
        if event.select.id == "provider-select":
            provider = str(event.value)
            if provider and provider != self._selected_provider:
                self._selected_provider = provider
                self._selected_model = ""
                self._invalidate_prompt_approval()
                self._invalidate_prompt_proposal()
                self._refresh_models(provider, preserve_model=False)
        elif event.select.id == "model-select":
            model = str(event.value)
            if model and model != self._selected_model:
                self._selected_model = model
                self._invalidate_prompt_approval()
                self._invalidate_prompt_proposal()
                self._set_status(
                    "connected" if self._op and self._op.connected else "unknown"
                )
        elif event.select.id in ("response-mode", "context-budget"):
            self._invalidate_prompt_approval()
            if event.select.id == "context-budget":
                self._invalidate_prompt_proposal()
            self._persist_prompt_preferences()
        elif event.select.id == "enhancement-select":
            self._invalidate_prompt_approval()
            self._invalidate_prompt_proposal()
        elif event.select.id == "proposal-selection":
            self._invalidate_prompt_approval()
        elif event.select.id == "network-authority":
            self._invalidate_prompt_approval()
            self._invalidate_prompt_proposal()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "model-filter":
            self._apply_model_filter()
        elif event.input.id == "target-root":
            self._invalidate_prompt_approval()
            self._invalidate_prompt_proposal()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "prompt":
            self._invalidate_prompt_approval()
            self._invalidate_prompt_proposal()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "human-verification":
            self._invalidate_prompt_approval()
            self._persist_prompt_preferences()
        elif event.checkbox.id in ("file-mutation", "shell-authority"):
            self._invalidate_prompt_approval()
            self._invalidate_prompt_proposal()

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
        elif event.button.id == "verify-accept":
            self.action_review_result("accept")
        elif event.button.id == "verify-reject":
            self.action_review_result("reject")

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
        if not self._op:
            self.notify("Runtime unavailable.", severity="error")
            return
        prompt = self.query_one("#prompt", TextArea).text.strip()
        engine = str(self.query_one("#enhancement-select", Select).value)
        target_root = self.query_one("#target-root", Input).value.strip()
        if not prompt or not self._selected_model or not target_root:
            self._show_output("Enhancement rejected locally: prompt, model, and target root are required.")
            return
        if engine == "OFF":
            self._invalidate_prompt_proposal()
            self._show_output("Prompt Intelligence is OFF; the literal operator prompt remains the approval basis.")
            return
        self._invalidate_prompt_approval(force=True)
        try:
            receipt = self._op.compile_prompt_proposal(
                {
                    "originalPrompt": prompt,
                    "targetRoot": target_root,
                    "promptIntelligence": engine,
                    "mode": "normal",
                    "provider": self._selected_provider,
                    "model": self._selected_model,
                    "requestedContextBudget": int(str(self.query_one("#context-budget", Select).value)),
                    "requestedCapabilities": [],
                    "remoteCompilationAuthorized": False,
                },
                "tui-proposal-" + uuid.uuid4().hex,
            )
            if receipt.get("status") == "rejected":
                raise RuntimeError(str(receipt.get("detail") or receipt.get("error") or "proposal rejected"))
            proposal = receipt.get("result", receipt)
            required = ("proposalId", "revision", "originalPrompt", "proposedPrompt")
            if any(proposal.get(key) is None for key in required):
                raise RuntimeError("runtime returned incomplete PromptProposal")
            self._prompt_proposal = dict(proposal)
            proposal_status = str(proposal.get("status") or "")
            executed_stage = any(
                bool(record.get("executionEnabled"))
                for record in (proposal.get("stageRecords") or [])
                if isinstance(record, dict)
            )
            self._enhancement_ready = (
                proposal_status in {"ready_for_approval", "compiler_unavailable"}
                or (proposal_status == "clarification_required" and executed_stage)
            )
            selection = "original" if proposal_status == "compiler_unavailable" else "upgrade"
            self.query_one("#proposal-selection", Select).value = selection
            stages = " -> ".join(proposal.get("stageChain") or []) or "deterministic"
            self._show_output(
                "PromptProposal %s r%s [%s]\nStages: %s\n\n%s"
                % (proposal["proposalId"], proposal["revision"], proposal.get("status", "unknown"), stages, proposal["proposedPrompt"])
            )
        except Exception as exc:  # noqa: BLE001
            self._invalidate_prompt_proposal()
            self._show_output("Enhancement failed: %s" % str(exc))
            self.notify("Prompt Intelligence failed", severity="error")

    def _authority_profile(self) -> dict[str, Any]:
        target_root = self.query_one("#target-root", Input).value.strip()
        return {
            "filesystemScope": "project",
            "filesystemRoot": target_root,
            "fileMutationAllowed": self.query_one("#file-mutation", Checkbox).value,
            "shellAccessAllowed": self.query_one("#shell-authority", Checkbox).value,
            "providerNetworkPolicy": str(self.query_one("#network-authority", Select).value),
        }

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
            if self._prompt_proposal.get("status") == "clarification_required":
                self._show_output(
                    "Approval blocked locally: clarification is required before this PromptProposal can be approved."
                )
                self.notify("Clarification required before approval.", severity="warning")
            else:
                self._show_output(
                    "Approval blocked locally: ENHANCE first, review the resulting prompt, then APPROVE."
                )
                self.notify("Enhance and review before approval.", severity="warning")
            return

        target_root = self.query_one("#target-root", Input).value.strip()
        payload = {
            "provider": self._selected_provider,
            "model": self._selected_model,
            "objective": prompt,
            "targetRoot": target_root,
            "authorityProfile": self._authority_profile(),
            "promptEnhancement": engine,
            "responseMode": str(self.query_one("#response-mode", Select).value),
            "requestedContextBudget": int(str(self.query_one("#context-budget", Select).value)),
            "humanVerificationRequired": self.query_one("#human-verification", Checkbox).value,
        }
        try:
            if engine == "OFF":
                request_receipt = self._op.request_prompt_approval(
                    payload, "tui-approval-" + uuid.uuid4().hex
                )
            else:
                if not self._prompt_proposal or not self._enhancement_ready:
                    raise RuntimeError("governed PromptProposal missing or stale")
                selection = str(self.query_one("#proposal-selection", Select).value)
                request_receipt = self._op.request_prompt_proposal_approval(
                    {
                        "proposalId": self._prompt_proposal["proposalId"],
                        "proposalRevision": int(self._prompt_proposal["revision"]),
                        "selection": selection,
                        "responseMode": payload["responseMode"],
                        "humanVerificationRequired": payload["humanVerificationRequired"],
                        "authorityProfile": payload["authorityProfile"],
                    },
                    "tui-proposal-approval-" + uuid.uuid4().hex,
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
            if state is None:
                state = self._op.approval_state(str(planned["requestId"])).get("state")
            if state != "approved":
                raise RuntimeError("runtime did not record prompt approval as approved")
            self._approval_receipt = dict(planned)
            self._approval_receipt.setdefault("authorityProfile", payload["authorityProfile"])
            if engine == "OFF":
                self._approval_receipt["_selectedObjective"] = prompt
            else:
                selection = str(self.query_one("#proposal-selection", Select).value)
                self._approval_receipt["_selectedObjective"] = (
                    self._prompt_proposal["proposedPrompt"]
                    if selection == "upgrade"
                    else self._prompt_proposal["originalPrompt"]
                )
            self._approval_basis = self._current_approval_basis()
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
            self._invalidate_prompt_approval(force=True)
            self._show_output("Approval failed: %s" % str(exc))
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
                "Checkpoint failed: %s" % str(exc), severity="error"
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
        if approval.get("proposalId"):
            # Prompt Intelligence has already produced and bound the selected
            # bytes. Execution must not re-apply the enhancement engine.
            engine = "OFF"
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
            str(approval.get("_selectedObjective") or prompt),
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
                    "targetRoot": str(
                        approval.get("authorityProfile", {}).get("filesystemRoot")
                        or self.query_one("#target-root", Input).value.strip()
                    ),
                    "authorityProfile": approval.get("authorityProfile", self._authority_profile()),
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
            if isinstance(receipt, dict):
                result = receipt.get("result")
                if isinstance(result, dict) and result.get("taskId"):
                    try:
                        task_state = self._op.client.get_state("task-" + str(result["taskId"]))
                        result["_taskState"] = task_state.get("state", "")
                    except Exception:
                        result["_taskState"] = "indeterminate"
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
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
            status = str(receipt.get("status", "unknown"))
            if status in ("accepted", "idempotent", "rejected"):
                self._invalidate_prompt_approval(force=True)
            result = receipt.get("result", {}) if isinstance(receipt, dict) else {}
            observation = (result.get("observations") or [{}])[0].get("summary", "")
            self._current_run = {
                "provider": provider,
                "model": model,
                "status": status,
                "approvalRequestId": approval_request_id,
                "driverRunId": result.get("driverRunId", ""),
                "missionId": result.get("missionId", ""),
                "taskId": result.get("taskId", ""),
                "outcome": result.get("outcome", ""),
                "taskState": result.get("_taskState", ""),
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
        self._sync_review_controls()
        self.action_refresh()

    def _sync_review_controls(self) -> None:
        enabled = (
            self._current_run.get("taskState") == "awaiting_verification"
            and bool(self._current_run.get("driverRunId"))
            and not self._run_busy
        )
        try:
            self.query_one("#verify-accept", Button).disabled = not enabled
            self.query_one("#verify-reject", Button).disabled = not enabled
            self.query_one("#verification-note", Input).disabled = not enabled
        except NoMatches:
            return

    def action_review_result(self, disposition: str) -> None:
        if disposition not in {"accept", "reject"}:
            self.notify("Invalid review disposition.", severity="error")
            return
        if not self._op or self._current_run.get("taskState") != "awaiting_verification":
            self.notify("No provider result is awaiting human verification.", severity="warning")
            return
        driver_run_id = str(self._current_run.get("driverRunId") or "")
        if not driver_run_id:
            self.notify("Verification DriverRun identity is unavailable.", severity="error")
            return
        note = self.query_one("#verification-note", Input).value.strip()
        self.query_one("#verify-accept", Button).disabled = True
        self.query_one("#verify-reject", Button).disabled = True
        self.query_one("#verification-note", Input).disabled = True
        self._submit_result_review(driver_run_id, disposition, note)

    @work(thread=True)
    def _submit_result_review(self, driver_run_id: str, disposition: str, note: str) -> None:
        receipt: dict[str, Any] | None = None
        error = ""
        try:
            assert self._op is not None
            receipt = self._op.client.command(
                "submit_provider_result_review",
                {"driverRunId": driver_run_id, "disposition": disposition, "note": note},
                "tui-provider-review-" + disposition + "-" + driver_run_id,
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        self.call_from_thread(
            self._finish_result_review, driver_run_id, disposition, receipt, error
        )

    def _finish_result_review(
        self, driver_run_id: str, disposition: str,
        receipt: dict[str, Any] | None, error: str,
    ) -> None:
        if error:
            self._show_output("Human review failed: %s" % error)
            self.notify("Human review failed", severity="error")
            self._sync_review_controls()
            return
        receipt = receipt or {}
        if str(receipt.get("status", "")) == "rejected":
            self._show_output("Human review rejected by RuntimeService: %s" % str(receipt.get("detail") or receipt.get("error") or "unknown"))
            self.notify("Human review rejected", severity="error")
            self._sync_review_controls()
            return
        result = receipt.get("result", {}) if isinstance(receipt, dict) else {}
        self._current_run["taskState"] = str(result.get("taskState") or "")
        self._current_run["status"] = self._current_run["taskState"] or disposition
        self._current_run["claimId"] = str(result.get("claimId") or "")
        self._current_run["verificationId"] = str(result.get("verificationId") or "")
        self._show_output(
            "Human review %s. Claim %s; task %s."
            % (disposition, self._current_run.get("claimId", ""), self._current_run.get("taskState", ""))
        )
        self.notify("Human review %s" % disposition)
        self._show_current_run()
        self._sync_review_controls()
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
        if current.get("taskState"):
            text += "\nVerification: %s" % current["taskState"]
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
