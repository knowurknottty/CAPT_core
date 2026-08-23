"""Closed structured stage outputs and execution-prompt rendering."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from .models import PromptStageName, _bounded_strings, _bounded_text


@dataclass(frozen=True)
class StructuredStageResult:
    stage: PromptStageName
    outcome: str
    scope: str
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    constraints: Tuple[str, ...]
    success_criteria: Tuple[str, ...]
    ambiguities: Tuple[str, ...]
    requested_capabilities: Tuple[str, ...] = ()

    @classmethod
    def from_model_output(cls, output: Mapping[str, Any]) -> "StructuredStageResult":
        if not isinstance(output, Mapping):
            raise ValueError("stage output must be an object")
        allowed = {
            "stage", "outcome", "scope", "inputs", "outputs", "constraints",
            "successCriteria", "ambiguities", "requestedCapabilities",
        }
        unknown = set(output) - allowed
        if unknown:
            raise ValueError("unknown keys in stage output: %s" % ", ".join(sorted(unknown)))
        required = allowed - {"requestedCapabilities"}
        missing = required - set(output)
        if missing:
            raise ValueError("missing stage output keys: %s" % ", ".join(sorted(missing)))
        raw_stage = str(output["stage"])
        try:
            stage = PromptStageName(raw_stage)
        except ValueError as exc:
            raise ValueError(f"unknown prompt stage: {raw_stage}") from exc
        return cls(
            stage=stage,
            outcome=_bounded_text(output["outcome"], "outcome"),
            scope=_bounded_text(output["scope"], "scope"),
            inputs=_bounded_strings(output["inputs"], "inputs"),
            outputs=_bounded_strings(output["outputs"], "outputs"),
            constraints=_bounded_strings(output["constraints"], "constraints"),
            success_criteria=_bounded_strings(output["successCriteria"], "successCriteria"),
            ambiguities=_bounded_strings(output["ambiguities"], "ambiguities"),
            requested_capabilities=_bounded_strings(
                output.get("requestedCapabilities", ()),
                "requestedCapabilities",
            ),
        )

def render_execution_prompt(original_prompt: str, result: StructuredStageResult) -> str:
    sections = [
        "Original objective:\n" + original_prompt,
        "Resolved outcome:\n" + result.outcome,
        "Scope:\n" + result.scope,
    ]
    if result.constraints:
        sections.append("Constraints:\n- " + "\n- ".join(result.constraints))
    if result.success_criteria:
        sections.append("Success criteria:\n- " + "\n- ".join(result.success_criteria))
    if result.outputs:
        sections.append("Expected outputs:\n- " + "\n- ".join(result.outputs))
    return "\n\n".join(sections)
