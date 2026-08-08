"""CAPT Desktop surface (UI Foundation Phase 6) — improve, don't rewrite.

Reuses the existing thin Tk client + RuntimeClient. Adds the v0.6 operator
layout from the wireframes: sidebar (Sessions/Missions/Memory/Providers/
Evidence/Settings/Logs/Help), conversation/transcript, dynamic right inspector
(model/provider/mission/checkpoint/ledger/evidence/verification/memory/context/
driver/latency), and an always-visible bottom status bar.

Everything renders from cap_ui.operator (shared) — no duplicated runtime logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from capt_ui.operator.bootstrap import resolve_runtime  # noqa: E402
from capt_ui.operator.models import ModelManager  # noqa: E402
from capt_ui.operator.providers import ProviderManager  # noqa: E402
from capt_ui.operator.runtime import Operator  # noqa: E402
from capt_ui.operator.verbosity import CaveCAPT  # noqa: E402


class DesktopSurface:
    """Framework-agnostic desktop view-model over the shared operator layer.

    Kept separate from the Tk GUI so the same logic can drive a SwiftUI client
    later (per the v0.6 spec) and can be verified headless.
    """

    def __init__(self, operator: Operator | None = None) -> None:
        self._op = operator
        self._providers = ProviderManager()
        self._models = ModelManager(providers=self._providers)
        self._verbosity = CaveCAPT()
        self.connected = False

    def connect(self) -> dict:
        if self._op is None:
            sock, token = resolve_runtime()
            if not (sock and token):
                raise RuntimeError("CAPT runtime not running (no socket/token)")
            self._op = Operator(sock, token)
        self._op.connect()
        self.connected = True
        return self.identity()

    def identity(self) -> dict:
        return self._op.client.identity() if self._op else {}

    def dashboard(self):
        return self._op.dashboard() if self._op else None

    def sidebar_items(self) -> list:
        """Sidebar items with active markers."""
        return [
            ("Sessions", "1"),
            ("Missions", len(self.dashboard().missions) if self.dashboard() else 0),
            ("Memory", "active" if (self._op and self._op.memory_policy()) else "off"),
            ("Providers", len(self._providers.list())),
            ("Evidence", len(self.dashboard().evidence.artifacts) if self.dashboard() else 0),
            ("Settings", ""),
            ("Logs", ""),
            ("Help", ""),
        ]

    def inspector(self) -> dict:
        """Dynamic right-inspector fields (no hidden state)."""
        op = self._op
        d = op.dashboard() if op and op.connected else None
        active = self._models.active()
        active_provider = self._providers.get(active.provider_id)
        return {
            "current model": active.model_id or "—",
            "provider": active.provider_name or "—",
            "provider kind": active.kind,
            "mission": (d.missions[0].get("objective", "") if d and d.missions else "—"),
            "checkpoint": "available" if (d and d.status.checkpoint_available) else "—",
            "ledger": (d.ledger_chain_digest or "—")[:16] if d else "—",
            "evidence": (len(d.evidence.artifacts) if d and d.evidence else 0),
            "verification": ((d.verification or {}).get("status", {}).get("kind") if d else "—"),
            "memory": "active" if (op and op.memory_policy()) else "off",
            "context": (d.status.context_used if d else 0),
            "context limit": (active.context or 0),
            "driver": active_provider.transport if active_provider else "—",
            "latency": ("%sms" % active_provider.latency_ms) if (active_provider and active_provider.latency_ms) else "—",
        }

    def status_line(self) -> str:
        """Always-visible bottom status bar."""
        op = self._op
        active = self._models.active()
        d = op.dashboard() if op and op.connected else None
        parts = [
            "Runtime %s" % (d.status.health.value if d else "stopped"),
            "Connected" if self.connected else "Disconnected",
            "Healthy" if (d and d.status.integrity == "ok") else "",
            "Checkpoint %s" % ("✓" if (d and d.status.checkpoint_available) else "—"),
            "Context %s/%s" % (d.status.context_used if d else 0, active.context or 0),
            "Provider %s" % active.provider_name or "—",
            "Model %s" % active.model_id or "—",
            "Memory %s" % ("on" if (op and op.memory_policy()) else "off"),
            "EventStore %s" % (d.status.head_sequence if d else 0),
            "Verbosity %s" % self._verbosity.value.label,
        ]
        return "  ▸  ".join(p for p in parts if p)


def headless_projection() -> str:
    """Headless textual projection of the desktop surface (for verification)."""
    surf = DesktopSurface()
    surf.connect()
    out = []
    out.append("=== CAPT Desktop Operator Surface ===")
    out.append("SIDEBAR: " + ", ".join("%s(%s)" % (n, c) for n, c in surf.sidebar_items()))
    out.append("--- RIGHT INSPECTOR ---")
    for k, v in surf.inspector().items():
        out.append("  %-16s %s" % (k, v))
    out.append("--- STATUS ---")
    out.append(surf.status_line())
    return "\n".join(out)


if __name__ == "__main__":
    print(headless_projection())
