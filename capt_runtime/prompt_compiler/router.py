"""Deterministic routing for Prompt Intelligence stages."""
from __future__ import annotations

import re
from typing import Tuple

from .models import PromptCompileRequest, PromptStageName


class PromptRoute(tuple):
    def __new__(cls, stages: Tuple[PromptStageName, ...], rationale: str) -> "PromptRoute":
        value = tuple.__new__(cls, stages)
        value.rationale = rationale
        return value

    @property
    def stage_chain(self) -> Tuple[PromptStageName, ...]:
        return tuple(self)


def _underspecified(prompt: str) -> bool:
    words = prompt.split()
    if len(words) < 4:
        return True
    lower = prompt.lower()
    signals = (
        "answer", "build", "code", "file", "fix", "implement", "plan",
        "report", "research", "review", "test", "write",
    )
    return not any(signal in lower for signal in signals)


def _software_work(prompt: str) -> bool:
    lower = prompt.lower()
    tokens = set(re.findall(r"[a-z0-9_+-]+", lower))
    token_signals = {
        "implement", "code", "debug", "fix", "repo", "repository", "build",
        "refactor", "test", "tests", "software", "app", "api", "function",
        "class", "module", "package", "compile", "compiler",
    }
    phrase_signals = ("pull request", "source code", "test suite", "bug fix")
    return bool(tokens & token_signals) or any(phrase in lower for phrase in phrase_signals)

def _reconciliation_work(prompt: str) -> bool:
    lower = prompt.lower()
    return any(signal in lower for signal in ("compare", "reconcile", "merge", "alternatives", "synthesize"))


def route_stages(request: PromptCompileRequest) -> PromptRoute:
    if request.requested_engine == "OFF":
        return PromptRoute((), "Prompt Intelligence is disabled by operator policy.")
    if request.mode == "software-development":
        return PromptRoute(
            (
                PromptStageName.OMNI,
                PromptStageName.META,
                PromptStageName.FORGE,
                PromptStageName.SIGMA,
            ),
            "Software-development mode selects OMNI/META plus advisory FORGE/SIGMA routing metadata.",
        )
    if request.requested_engine != "AUTO":
        stage = PromptStageName(request.requested_engine)
        return PromptRoute((stage,), "Stage selected explicitly by operator policy.")
    if _underspecified(request.original_prompt):
        return PromptRoute(
            (PromptStageName.OMNI,),
            "Input is underspecified; clarification is required before an execution contract can be drafted.",
        )
    if _software_work(request.original_prompt):
        return PromptRoute(
            (PromptStageName.OMNI, PromptStageName.META, PromptStageName.FORGE, PromptStageName.SIGMA),
            "Software work is routed through OMNI/META intent compilation plus bounded FORGE repository analysis and SIGMA reconciliation.",
        )
    if _reconciliation_work(request.original_prompt):
        return PromptRoute(
            (PromptStageName.OMNI, PromptStageName.META, PromptStageName.SIGMA),
            "Reconciliation work adds SIGMA after OMNI/META to preserve alternatives, dissent, and tradeoffs.",
        )
    return PromptRoute(
        (PromptStageName.OMNI, PromptStageName.META),
        "Substantive request is routed through OMNI intent completeness and META execution-contract analysis.",
    )
