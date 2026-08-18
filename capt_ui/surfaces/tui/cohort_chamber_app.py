"""Textual Cohort Deliberation Chamber (CAPT-UPG-018)."""
from __future__ import annotations

import argparse
import os
from typing import Any, Dict, Optional, Sequence

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from capt_ui.operator.cohort_chamber import render_cohort_chamber_text
from capt_ui.operator.runtime import Operator


class CohortChamberTUI(App):
    CSS = """
    #chamber { height: 1fr; padding: 1; overflow-y: auto; }
    #steer { height: auto; padding: 1; border-top: solid $surface-lighten-2; }
    #directive, #reason { margin: 0 1 0 0; }
    """
    BINDINGS = [("r", "refresh", "Refresh"), ("q", "quit", "Quit")]

    def __init__(self, sock: str = "", token_file: str = "", cohort_id: str = "", operator: Optional[Operator] = None) -> None:
        super().__init__()
        self.sock = sock
        self.token_file = token_file
        self.cohort_id = cohort_id
        self._op = operator
        self._owns_operator = operator is None

    @staticmethod
    def view_text(view: Dict[str, Any]) -> str:
        return render_cohort_chamber_text(view)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Loading Cohort state…", id="chamber")
        with Vertical(id="steer"):
            with Horizontal():
                yield Input(placeholder="Steering directive", id="directive")
                yield Input(value="operator steering", placeholder="Reason", id="reason")
                yield Button("Submit governed steer", id="submit-steer", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        if self._op is None:
            self._op = Operator(self.sock, self.token_file)
            self._op.connect()
        self.action_refresh()

    def action_refresh(self) -> None:
        if self._op is None:
            return
        try:
            view = self._op.cohort_chamber(self.cohort_id)
            self.query_one("#chamber", Static).update(self.view_text(view))
        except Exception as exc:  # noqa: BLE001
            self.query_one("#chamber", Static).update("Chamber projection failed: %s" % str(exc)[:240])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "submit-steer":
            return
        self.action_submit_steer()

    def action_submit_steer(self) -> None:
        if self._op is None:
            return
        directive = self.query_one("#directive", Input).value.strip()
        reason = self.query_one("#reason", Input).value.strip()
        if not directive or not reason:
            self.notify("Directive and reason are required.", severity="warning")
            return
        receipt = self._op.steer_deliberation(self.cohort_id, directive, reason=reason)
        if receipt.get("status") not in ("accepted", "idempotent"):
            self.notify("Steering rejected: %s" % str(receipt.get("detail") or receipt.get("error") or receipt)[:180], severity="error")
            return
        self.query_one("#directive", Input).value = ""
        self.notify("Governed steering accepted.", severity="warning")
        self.action_refresh()

    def on_unmount(self) -> None:
        if self._owns_operator and self._op is not None:
            self._op.disconnect()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CAPT Cohort Deliberation Chamber TUI")
    parser.add_argument("--sock", default=os.environ.get("CAPT_RUNTIME_SOCK", ""))
    parser.add_argument("--token-file", default=os.environ.get("CAPT_RUNTIME_TOKEN_FILE", ""))
    parser.add_argument("--cohort-id", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if not args.sock or not args.token_file:
        raise SystemExit("--sock and --token-file (or CAPT_RUNTIME_* env vars) are required")
    CohortChamberTUI(args.sock, args.token_file, args.cohort_id).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
