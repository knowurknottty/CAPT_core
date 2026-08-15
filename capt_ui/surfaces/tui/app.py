"""CAPT TUI — Textual operator console (UI Foundation Phase 5).

Uses the shared `capt_ui.operator` layer. Rendering only; no runtime logic.
Panels: Runtime / Mission / Memory / Evidence / Provider / Approvals / Logs.
Keyboard-first. Talks to the same RuntimeClient as CLI and Desktop.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Select, Static, TextArea

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from capt_ui.operator.bootstrap import resolve_runtime, runtime_available  # noqa: E402
from capt_ui.operator.contract import Verbosity  # noqa: E402
from capt_ui.operator.models import ModelManager  # noqa: E402
from capt_ui.operator.providers import ProviderManager  # noqa: E402
from capt_ui.operator.runtime import Operator  # noqa: E402
from capt_ui.operator.verbosity import CaveCAPT  # noqa: E402


class StatusBar(Static):
    """Top line: runtime health, active model, provider, context, verbosity."""

    status = reactive({})

    def render(self) -> str:
        s = self.status
        health = s.get("health", "unknown").upper()
        return (
            f"CAPT ▸ Runtime {health} ▸ Model {s.get('model', '?')} "
            f"[{s.get('kind', 'UNKNOWN')}] ▸ Context {s.get('context_used', 0)}/"
            f"{s.get('context_limit', 0)} ▸ Approvals {s.get('approvals', 0)}"
        )


class MissionPanel(Static):
    missions = reactive([])

    def render(self) -> str:
        if not self.missions:
            return "Mission\n────────\n<none>"
        lines = ["Mission", "────────"]
        for m in self.missions[:6]:
            lines.append("  %s  %s" % (m.get("state", "?"), m.get("objective", "")[:40]))
        return "\n".join(lines)


class MemoryPanel(Static):
    state = reactive({})

    def render(self) -> str:
        d = self.state
        return (
            "Memory / Context\n────────────────\n"
            "active: %s\nretrieval steps: %s\nsafe limit: %s"
            % (d.get("active", "?"), d.get("retrievalTriggerSteps", "?"),
               d.get("modelSafeLimitSteps", "?"))
        )


class EvidencePanel(Static):
    result = reactive({})

    def render(self) -> str:
        v = self.result.get("verification", {})
        kind = v.get("status", {}).get("kind", "unknown") if isinstance(v, dict) else "unknown"
        return "Evidence\n────────\nverification: %s\nclaimguard: %s" % (
            kind, self.result.get("claimguard", {}).get("verdict", "?"))


class ProviderPanel(Static):
    text = reactive("")

    def render(self) -> str:
        return self.text or "Providers\n─────────\n<none>"


class ApprovalPanel(Static):
    rows = reactive([])

    def render(self) -> str:
        if not self.rows:
            return "Approvals\n─────────\n<none pending>"
        lines = ["Approvals", "─────────"]
        for a in self.rows[:5]:
            lines.append("  ! %s %s [%s]" % (a.request_id[:8], a.operation, a.state))
        lines.append("  [a]pprove / [d]eny per request")
        return "\n".join(lines)


class LogPanel(Static):
    logs = reactive([])

    def render(self) -> str:
        if not self.logs:
            return "Logs\n────\nCapture boundary is CLI/Desktop log. TUI mirrors last runtime events."
        lines = ["Logs", "────"]
        for ev in self.logs[:8]:
            p = ev.get("payload", {})
            lines.append("  %s %s" % (ev.get("globalSequence"), p.get("eventType")))
        return "\n".join(lines)


class CaptTUI(App):
    """CAPT operator console."""

    TITLE = "CAPT"
    SUB_TITLE = "operator console"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("m", "show_mission", "Mission"),
        Binding("p", "show_provider", "Providers"),
        Binding("a", "show_approvals", "Approvals"),
        Binding("y", "approve", "Approve"),
        Binding("n", "deny", "Deny"),
        Binding("v", "cyclev", "Verbosity"),
        Binding("f5", "show_evidence", "Evidence"),
        Binding("f6", "show_memory", "Memory"),
        Binding("f7", "show_logs", "Logs"),
        Binding("e", "show_runtime", "Runtime"),
    ]

    def __init__(self, operator: Optional[Operator] = None) -> None:
        super().__init__()
        self._operator = operator
        self._op = operator
        self._providers: ProviderManager | None = None
        self._models: ModelManager | None = None
        self._verbosity: CaveCAPT | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield StatusBar("connecting…", id="status")
            with Horizontal():
                with Vertical(id="left", classes="panel-col"):
                    yield MissionPanel(id="mission")
                    yield MemoryPanel(id="memory")
                    yield EvidencePanel(id="evidence")
                with Vertical(id="center", classes="panel-col"):
                    yield Static("Run a governed provider inference", id="run-title")
                    yield Select([( "Ollama", "ollama"), ("OpenRouter", "openrouter")], value="ollama", id="provider-select")
                    yield Select([], id="model-select")
                    yield TextArea("", id="prompt", language=None)
                    with Horizontal():
                        yield Button("RUN", id="run", variant="success")
                        yield Button("CHECKPOINT", id="checkpoint")
                    yield Static("Output\n──────\n<none>", id="output")
                    yield ProviderPanel(id="provider")
                    yield ApprovalPanel(id="approvals")
                with Vertical(id="right", classes="panel-col"):
                    yield LogPanel(id="logs")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh()

    # -- refresh -----------------------------------------------------------
    def action_refresh(self) -> None:
        if self._op is None:
            sock, token = resolve_runtime()
            if not (sock and token):
                self.update_status("runtime unavailable")
                return
            try:
                self._op = Operator(sock, token)
                self._op.connect()
            except Exception as exc:  # noqa: BLE001
                self.update_status("connect failed: %s" % str(exc)[:80])
                return
        self._providers = ProviderManager()
        self._models = ModelManager(providers=self._providers)
        self._verbosity = CaveCAPT()
        try:
            dash = self._op.dashboard()
        except Exception as exc:  # noqa: BLE001
            self.update_status("dashboard failed: %s" % str(exc)[:80])
            return
        active = self._models.active()
        st = dash.status
        self.query_one("#status", StatusBar).status = {
            "health": st.health.value, "model": active.model_id or "?",
            "kind": active.kind, "context_used": st.context_used,
            "context_limit": active.context, "approvals": st.approvals_pending,
        }
        self.query_one("#mission", MissionPanel).missions = dash.missions
        self.query_one("#evidence", EvidencePanel).result = {
            "verification": dash.verification,
            "claimguard": self._op.claimguard("mission evidence reviewed") if self._op.connected else {},
        }
        self.query_one("#memory", MemoryPanel).state = self._op.memory_policy()
        self.query_one("#approvals", ApprovalPanel).rows = dash.approvals
        self.query_one("#logs", LogPanel).logs = dash.events
        prov_lines = []
        for p in self._providers.list():
            mark = "●" if p.selected else "○"
            prov_lines.append("  %s %s [%s] %s" % (
                mark, p.name, self._providers.label(p), p.health.value))
        self.query_one("#provider", ProviderPanel).text = (
            "Providers\n─────────\n" + "\n".join(prov_lines[:8]))
        self._refresh_models("ollama")
        self.update_status("connected")

    def _refresh_models(self, provider_id: str) -> None:
        if not self._providers:
            return
        provider = self._providers.get(provider_id)
        models = []
        try:
            if provider_id == "ollama":
                provider = self._providers.test("ollama")
                models = provider.models
            else:
                from capt_ui.operator.openrouter_models import available_text_models
                models = [entry.model_id for entry in available_text_models()]
        except Exception as exc:  # noqa: BLE001
            self.query_one("#output", Static).update("Output\n──────\nProvider unavailable: %s" % str(exc)[:120])
        select = self.query_one("#model-select", Select)
        options = [(m, m) for m in models] or [("<unavailable>", "")]
        select.set_options(options)
        select.value = options[0][1]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-select":
            self._refresh_models(str(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "checkpoint":
            if self._op:
                try:
                    self._op.client.command("checkpoint_runtime", {}, "tui-checkpoint")
                    self.notify("Checkpoint accepted")
                except Exception as exc:  # noqa: BLE001
                    self.notify("Checkpoint failed: %s" % str(exc)[:120], severity="error")
            return
        if event.button.id != "run" or not self._op:
            return
        provider = str(self.query_one("#provider-select", Select).value)
        model = str(self.query_one("#model-select", Select).value)
        prompt = self.query_one("#prompt", TextArea).text.strip()
        if not prompt or not model:
            self.notify("Select an available model and enter a prompt.", severity="error")
            return
        try:
            import uuid
            receipt = self._op.client.command("run_approved_hermes_inspection", {"provider": provider, "model": model, "objective": prompt, "targetRoot": str(Path.cwd())}, "tui-run-" + uuid.uuid4().hex)
            result = receipt.get("result", {})
            observation = (result.get("observations") or [{}])[0].get("summary", "")
            self.query_one("#output", Static).update("Output\n──────\n%s" % observation)
            self.notify("Run %s" % receipt.get("status", "unknown"))
            self.action_refresh()
        except Exception as exc:  # noqa: BLE001
            self.query_one("#output", Static).update("Output\n──────\nRun failed: %s" % str(exc)[:240])


    def update_status(self, msg: str) -> None:
        self.query_one("#status", StatusBar).status = {"health": msg}

    # -- navigation (progressive disclosure via binding) ------------------
    def action_show_runtime(self) -> None:
        self.action_refresh()

    def action_show_mission(self) -> None:
        self.bell()

    def action_show_provider(self) -> None:
        self.action_refresh()

    def action_show_approvals(self) -> None:
        self.action_refresh()

    def action_show_evidence(self) -> None:
        self.action_refresh()

    def action_show_memory(self) -> None:
        self.action_refresh()

    def action_show_logs(self) -> None:
        self.action_refresh()

    def action_cyclev(self) -> None:
        if self._verbosity:
            self._verbosity.toggle(1)
            self.notify("CaveCAPT verbosity: %s" % self._verbosity.value.label)
            self.action_refresh()

    # -- governed approval handling (same runtime command as Desktop/CLI) --
    def _pending_request(self):
        if not self._op or not self._op.connected:
            return None
        try:
            dash = self._op.dashboard()
        except Exception:  # noqa: BLE001
            return None
        for a in dash.approvals:
            if a.state in ("pending", "open"):
                return a
        return None

    def action_approve(self) -> None:
        req = self._pending_request()
        if req is None or self._op is None:
            self.notify("No pending approval request to approve.")
            return
        try:
            self._op.decide_approval(req.request_id, "approve")
            self.notify("Approved %s (%s)" % (req.request_id[:8], req.operation))
        except Exception as exc:  # noqa: BLE001
            self.notify("Approve failed: %s" % str(exc)[:80], severity="error")
        self.action_refresh()

    def action_deny(self) -> None:
        req = self._pending_request()
        if req is None or self._op is None:
            self.notify("No pending approval request to deny.")
            return
        try:
            self._op.decide_approval(req.request_id, "deny")
            self.notify("Denied %s (%s)" % (req.request_id[:8], req.operation))
        except Exception as exc:  # noqa: BLE001
            self.notify("Deny failed: %s" % str(exc)[:80], severity="error")
        self.action_refresh()


def main() -> int:
    app = CaptTUI()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())