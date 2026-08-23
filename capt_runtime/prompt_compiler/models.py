"""Immutable models for governed prompt compilation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from ..contracts import digest


class PromptStageName(str, Enum):
    OMNI = "OMNI"
    META = "META"
    FORGE = "FORGE"
    SIGMA = "SIGMA"


_VALID_ENGINES = frozenset({"OFF", "AUTO", *(stage.value for stage in PromptStageName)})
_VALID_MODES = frozenset({"normal", "software-development"})
_MAX_PROMPT_CHARS = 65_536
_MAX_LIST_ITEMS = 32
_MAX_ITEM_CHARS = 2_048

def _bounded_text(value: Any, name: str, *, max_chars: int = _MAX_ITEM_CHARS) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    if len(text) > max_chars:
        raise ValueError(f"{name} exceeds bound")
    return text


def _bounded_strings(value: Any, name: str) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list")
    if len(value) > _MAX_LIST_ITEMS:
        raise ValueError(f"{name} exceeds bound")
    return tuple(_bounded_text(item, name) for item in value)


@dataclass(frozen=True)
class PromptCompileRequest:
    original_prompt: str
    target_root: str = ""
    requested_engine: str = "AUTO"
    mode: str = "normal"
    requested_capabilities: Tuple[str, ...] = ()
    execution_provider: str = ""
    execution_model: str = ""
    requested_context_budget: int = 0
    remote_compilation_authorized: bool = False

    def __post_init__(self) -> None:
        prompt = _bounded_text(
            self.original_prompt,
            "original_prompt",
            max_chars=_MAX_PROMPT_CHARS,
        )
        engine = str(self.requested_engine).upper()
        mode = str(self.mode).lower()
        if engine not in _VALID_ENGINES:
            raise ValueError("unknown prompt enhancement engine")
        if mode not in _VALID_MODES:
            raise ValueError("unknown prompt compilation mode")
        capabilities = _bounded_strings(
            self.requested_capabilities,
            "requested_capabilities",
        )
        object.__setattr__(self, "original_prompt", prompt)
        object.__setattr__(self, "requested_engine", engine)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "requested_capabilities", capabilities)


@dataclass(frozen=True)
class CompilerProvider:
    provider_id: str
    model: str
    endpoint_class: str

@dataclass(frozen=True)
class PromptStageRecord:
    stage: PromptStageName
    version: str
    execution_enabled: bool
    input_digest: str
    output_digest: str
    provider_id: str = ""
    model: str = ""
    endpoint_class: str = ""
    resource_usage: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class PromptCompileProposal:
    status: str
    original_prompt: str
    proposed_prompt: str
    stage_chain: Tuple[PromptStageName, ...]
    stage_records: Tuple[PromptStageRecord, ...]
    requested_capabilities: Tuple[str, ...]
    unresolved_questions: Tuple[str, ...] = ()
    rationale: str = ""

    @property
    def original_prompt_digest(self) -> str:
        return digest(self.original_prompt)

    @property
    def proposed_prompt_digest(self) -> str:
        return digest(self.proposed_prompt)
