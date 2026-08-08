"""CaveCAPT verbosity system (UI-2 / Phase 4).

One shared implementation of the four verbosity profiles
(Minimal / Normal / Detailed / Diagnostic). Every surface (CLI, TUI, Desktop),
logs, notifications, and evidence summaries consume this single engine — there
is no duplicated implementation.

Verbosity affects PRESENTATION / EXPLANATION only. It never weakens governance,
evidence, policy, or verification.

Semantics from the canonical UI/UX spec:
- MINIMAL   — final answer / essential operator prompts only.
- NORMAL    — useful progress, decisions, approvals, important evidence
              summaries. (default)
- DETAILED  — richer runtime explanation, memory/context actions, verification
              summaries.
- DIAGNOSTIC— engineering-level detail: IDs, policy/evidence/runtime
              diagnostics, EventStore, ClaimGuard, timing, structured traces.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contract import Verbosity


class CaveCAPT:
    """Shared verbosity preference provider + explanation renderer."""

    DEFAULT = Verbosity.NORMAL

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        cfg = config_dir or self._default_config_dir()
        cfg.mkdir(parents=True, exist_ok=True)
        self._file = cfg / "verbosity.json"
        self._value = Verbosity(self._read() or self.DEFAULT.value)

    @staticmethod
    def _default_config_dir() -> Path:
        override = os.environ.get("CAPT_SOLO_HOME") or os.environ.get("CAPT_STATE_DIR")
        if override:
            return Path(override).expanduser() / "ui"
        return Path.home() / ".capt" / "ui"

    def _read(self) -> Optional[str]:
        try:
            return json.loads(self._file.read_text()).get("verbosity")
        except Exception:  # noqa: BLE001
            return None

    # -- preference -------------------------------------------------------
    @property
    def value(self) -> Verbosity:
        return self._value

    def set(self, verbosity: Verbosity) -> Verbosity:
        self._value = Verbosity(verbosity.value)
        self._file.write_text(json.dumps({"verbosity": self._value.value}, indent=2))
        return self._value

    def toggle(self, direction: int = 1) -> Verbosity:
        order = Verbosity.all()
        idx = order.index(self._value)
        return self.set(order[(idx + direction) % len(order)])

    # -- uniform explanation redaction ------------------------------------
    def explain(self, *, message: str, level: Verbosity, normal: str = "",
                detailed: str = "", diagnostic: str = "", **fields: Any) -> str:
        """Return the appropriately-detailed explanation for a message at the
        given level. Used identically by every surface and by logs/evidence
        summaries so wording is consistent."""
        rank = {"minimal": 0, "normal": 1, "detailed": 2, "diagnostic": 3}
        r = rank[level.value]
        if r <= 0:
            return message
        if r >= 3:
            base = diagnostic or detailed or normal
            if fields:
                return "%s %s" % (base, json.dumps(fields, default=str))
            return base or message
        if r == 2:
            return detailed or normal or message
        return normal or message

    # -- build a minimal/normal/detailed/diagnostic text bundle ------------
    def render_status(self, status: Dict[str, Any]) -> str:
        v = self._value
        head = "Runtime %s | Model %s [%s]" % (
            status.get("health", "unknown").upper(),
            status.get("model", "?"),
            status.get("kind", "UNKNOWN"),
        )
        if v is Verbosity.MINIMAL:
            return head
        parts = [head]
        if v in (Verbosity.DETAILED, Verbosity.DIAGNOSTIC):
            parts.append("runtime=%s ver=%s integrity=%s" % (
                status.get("runtime_version", "?"), status.get("runtime_version", "?"),
                status.get("integrity", "?")))
        if v is Verbosity.DIAGNOSTIC:
            parts.append("head=%s approvals=%s context=%s/%s" % (
                status.get("head_sequence"), status.get("approvals_pending", 0),
                status.get("context_used", 0), status.get("context_limit", 0)))
        return " | ".join(p for p in parts if p)


def parse_verbosity(text: str) -> Verbosity:
    return Verbosity(text.strip().lower())