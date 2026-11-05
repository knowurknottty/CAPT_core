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
        "answer", "analyze", "audit", "build", "check", "code", "compare",
        "evaluate", "explain", "file", "find", "fix", "identify", "implement",
        "inspect", "list", "map", "match", "plan", "rank", "report", "research",
        "review", "show", "summarize", "test", "write", "craft", "draft", "design", "create", "generate", "compose", "produce",
    )
    return not any(signal in lower for signal in signals)


def _software_work(prompt: str) -> bool:
    # Require actionable engineering intent; mentions of software do not count.
    lower = prompt.lower()
    tokens = set(re.findall(r"[a-z0-9_+-]+", lower))
    # A document *about* software remains a writing task, even if Dev Mode
    # is enabled. A technical noun is not an engineering instruction.
    document_outputs = {
        "whitepaper", "report", "article", "essay", "post", "deck",
        "slides", "presentation", "summary", "overview", "explainer",
        "announcement", "pitch", "memo",
    }
    document_actions = {
        "write", "craft", "draft", "create", "generate", "produce",
        "design", "compose", "prepare",
    }
    if tokens & document_outputs and tokens & document_actions:
        return False
    engineering_targets = {
        "repo", "repository", "code", "software", "app", "api",
        "function", "module", "package", "compiler", "runtime",
        "test", "tests", "bug", "script", "endpoint", "provider",
        "frontend", "backend", "plugin",
    }
    strong_actions = {
        "implement", "debug", "fix", "refactor", "patch",
        "test", "deploy", "compile", "repair", "regress",
    }
    creation_targets = {
        "app", "api", "function", "module", "package", "script",
        "endpoint", "frontend", "backend", "plugin", "tests",
        "test", "repository", "repo",
    }
    creation_actions = {"build", "develop", "create", "write", "code"}
    review_actions = {"review", "audit", "inspect"}
    review_targets = {"repo", "repository", "code", "module", "package"}
    return (
        (bool(tokens & strong_actions) and bool(tokens & engineering_targets))
        or (bool(tokens & creation_actions) and bool(tokens & creation_targets))
        or (bool(tokens & review_actions) and bool(tokens & review_targets))
        or ("pull request" in lower and bool(tokens & review_actions))
    )

def _reconciliation_work(prompt: str) -> bool:
    lower = prompt.lower()
    return any(signal in lower for signal in ("compare", "reconcile", "merge", "alternatives", "synthesize"))


def route_stages(request: PromptCompileRequest) -> PromptRoute:
    if request.requested_engine == "OFF":
        return PromptRoute((), "Prompt Intelligence is disabled by operator policy.")
    development_task = (
        request.mode == "software-development"
        and _software_work(request.original_prompt)
    )
    if request.requested_engine in ("FORGE", "SIGMA") and not development_task:
        raise ValueError("FORGE_SIGMA_REQUIRE_DEVELOPMENT_TASK_AND_MODE")
    if request.requested_engine != "AUTO":
        stage = PromptStageName(request.requested_engine)
        return PromptRoute((stage,), "Stage selected explicitly by operator policy.")
    if _underspecified(request.original_prompt):
        return PromptRoute(
            (PromptStageName.OMNI,),
            "Input is underspecified; clarification is required before an execution contract can be drafted.",
        )
    if development_task:
        return PromptRoute(
            (PromptStageName.OMNI, PromptStageName.META, PromptStageName.FORGE, PromptStageName.SIGMA),
            "Development Mode and an actionable software task select OMNI/META/FORGE/SIGMA.",
        )
    return PromptRoute(
        (PromptStageName.OMNI, PromptStageName.META),
        "Substantive general tasks use OMNI/META only; FORGE/SIGMA require Development Mode and software-development intent.",
    )
