"""Inspectable, local prompt-enhancement contracts for CAPT operator surfaces.

This module is deliberately presentation-side and deterministic.  It proposes a
bounded draft; RuntimeService remains the sole authority for dispatch, evidence,
and lifecycle state.  The proposal can require explicit human approval.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

ENGINES = ("OFF", "AUTO", "OMNI", "META", "FORGE", "SIGMA")
RESPONSE_MODES = ("MAX", "SPOCK", "CAVE CAPT", "MIN")
CONTEXT_BUDGETS = tuple(range(32_000, 256_001, 32_000))


@dataclass(frozen=True)
class PromptProposal:
    engine: str
    optimized_prompt: str
    rationale: str
    questions: List[str]


def inspect_prompt(raw: str, requested_engine: str = "AUTO") -> PromptProposal:
    """Return a bounded, explainable proposal without inventing user intent."""
    text = raw.strip()
    issues: List[str] = []
    lower = text.lower()
    if len(text.split()) < 4:
        issues.append("What outcome should the work produce?")
    if not any(token in lower for token in ("test", "report", "file", "code", "plan", "answer", "research", "fix", "build")):
        issues.append("What artifact or success criterion should CAPT use?")
    requested = requested_engine.upper()
    if requested not in ENGINES:
        raise ValueError("unknown prompt enhancement engine")
    if requested == "OFF":
        return PromptProposal("OFF", text, "Enhancement disabled by operator.", issues)
    if requested == "AUTO":
        if issues:
            engine, rationale = "OMNI", "Input is underspecified; OMNI makes missing execution constraints visible."
        elif any(word in lower for word in ("fix", "implement", "debug", "test", "security", "repo", "code")):
            engine, rationale = "FORGE", "Implementation/research signals require acceptance and evidence constraints."
        elif any(word in lower for word in ("compare", "reconcile", "merge", "alternatives", "synthesize")):
            engine, rationale = "SIGMA", "Multiple alternatives or constraints benefit from explicit reconciliation."
        else:
            engine, rationale = "META", "The prompt is substantive; META preserves intent while clarifying output contract."
    else:
        engine = requested
        rationale = "Engine selected explicitly by operator."
    if issues:
        return PromptProposal(engine, text, rationale, issues)
    suffix = {
        "OMNI": "\n\nState the target, constraints, and a verifiable success criterion before acting.",
        "META": "\n\nPreserve the stated intent. Return the requested artifact in an inspectable format and label uncertainty.",
        "FORGE": "\n\nDefine scope, acceptance tests, authority boundaries, and evidence before claiming completion.",
        "SIGMA": "\n\nReconcile constraints explicitly; choose the smallest solution that satisfies them and identify unresolved tradeoffs.",
    }[engine]
    return PromptProposal(engine, text + suffix, rationale, [])


class PromptPreferences:
    """Small local preference store; it contains no provider credentials or prompts."""
    def __init__(self, config_dir: Optional[Path] = None) -> None:
        base = config_dir or Path(os.environ.get("CAPT_SOLO_HOME") or os.environ.get("CAPT_STATE_DIR") or Path.home() / ".capt") / "ui"
        base.mkdir(parents=True, exist_ok=True)
        self._file = base / "prompt-preferences.json"
        self._data: Dict[str, object] = {"responseMode": "SPOCK", "contextBudget": 32_000, "humanVerificationRequired": True}
        try:
            loaded = json.loads(self._file.read_text())
            if isinstance(loaded, dict):
                self._data.update(loaded)
        except Exception:
            pass
        self._validate()

    def _validate(self) -> None:
        if self._data.get("responseMode") not in RESPONSE_MODES:
            self._data["responseMode"] = "SPOCK"
        if self._data.get("contextBudget") not in CONTEXT_BUDGETS:
            self._data["contextBudget"] = 32_000
        self._data["humanVerificationRequired"] = bool(self._data.get("humanVerificationRequired", True))

    @property
    def response_mode(self) -> str:
        return str(self._data["responseMode"])

    @property
    def context_budget(self) -> int:
        return int(self._data["contextBudget"])

    @property
    def human_verification_required(self) -> bool:
        return bool(self._data["humanVerificationRequired"])

    def set(self, *, response_mode: str, context_budget: int, human_verification_required: bool) -> None:
        self._data = {"responseMode": response_mode, "contextBudget": context_budget, "humanVerificationRequired": human_verification_required}
        self._validate()
        self._file.write_text(json.dumps(self._data, indent=2, sort_keys=True))
