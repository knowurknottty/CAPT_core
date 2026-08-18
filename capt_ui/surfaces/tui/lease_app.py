"""CAPT-UPG-015 lease inspector and governed kill-key TUI.

This is an additive presentation/control subclass. Lease rows are read-only
projections of authoritative capability aggregates. Revocation requests are
submitted through Operator.revoke_capability(); this surface never mutates
capability state directly.
"""
from __future__ import annotations

from typing import Any, Dict, List

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Select, Static

from capt_ui.operator.leases import render_capability_leases
from .epistemic_app import EpistemicCaptTUI


class LeasePanel(Static):
    rows = reactive([])

    def render(self) -> str:
        return render_capability_leases(self.rows)


class LeaseEpistemicCaptTUI(EpistemicCaptTUI):
    """Epistemic CAPT console plus explicit capability lease control."""

    CSS = EpistemicCaptTUI.CSS + """
    #lease-control { height: auto; padding: 1; border-top: solid $surface-lighten-2; }
    #lease-panel { height: auto; min-height: 5; }
    #lease-grant, #lease-target, #lease-reason, #lease-target-kind { margin: 1 0; }
    """

    BINDINGS = list(EpistemicCaptTUI.BINDINGS) + [
        Binding("k", "focus_lease_kill", "Lease kill-key"),
    ]

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Vertical(id="lease-control"):
            yield LeasePanel(id="lease-panel")
            with Horizontal():
                yield Input(placeholder="Grant ID", id="lease-grant")
                yield Select([("Lease", "lease"), ("Grant", "grant")], value="lease", id="lease-target-kind")
                yield Input(placeholder="Exact lease/grant target ID", id="lease-target")
            with Horizontal():
                yield Input(placeholder="Revocation reason (required)", id="lease-reason")
                yield Button("REVOKE / KILL", id="lease-revoke", variant="error")

    def action_refresh(self) -> None:
        super().action_refresh()
        self._refresh_leases()

    def _refresh_leases(self) -> None:
        if self._op is None or not self._op.connected:
            try:
                self.query_one("#lease-panel", LeasePanel).rows = []
            except Exception:  # widget may not yet be mounted during early refresh
                pass
            return
        try:
            rows = self._op.capability_leases()
        except Exception as exc:  # noqa: BLE001
            self.notify("Lease projection failed: %s" % str(exc)[:120], severity="error")
            rows = []
        try:
            self.query_one("#lease-panel", LeasePanel).rows = rows
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "lease-revoke":
            self.action_revoke_capability()
            return
        super().on_button_pressed(event)

    def action_focus_lease_kill(self) -> None:
        self.query_one("#lease-grant", Input).focus()

    def action_revoke_capability(self) -> None:
        if self._op is None:
            self.notify("Runtime unavailable.", severity="error")
            return
        grant_id = self.query_one("#lease-grant", Input).value.strip()
        target_kind = str(self.query_one("#lease-target-kind", Select).value)
        target_id = self.query_one("#lease-target", Input).value.strip()
        reason = self.query_one("#lease-reason", Input).value.strip()
        if not grant_id or target_kind not in ("lease", "grant") or not target_id or not reason:
            self.notify(
                "Revocation requires explicit grant ID, target kind, exact target ID, and reason.",
                severity="warning",
            )
            return
        try:
            receipt = self._op.revoke_capability(
                grant_id,
                target_kind=target_kind,
                target_id=target_id,
                reason=reason,
            )
        except Exception as exc:  # noqa: BLE001
            self.notify("Revocation failed: %s" % str(exc)[:160], severity="error")
            return
        status = str(receipt.get("status", "unknown"))
        classification = str(receipt.get("classification", "unknown"))
        if status in ("accepted", "idempotent"):
            self.notify("Capability revocation %s (%s)" % (status, classification), severity="warning")
            self.query_one("#lease-reason", Input).value = ""
        else:
            detail = receipt.get("detail") or (receipt.get("error") or {}).get("code") or classification
            self.notify("Revocation rejected: %s" % str(detail)[:160], severity="error")
        self._refresh_leases()


def main() -> int:
    LeaseEpistemicCaptTUI().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
