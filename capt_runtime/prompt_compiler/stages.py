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


_STAGE_INSTRUCTIONS = {
    PromptStageName.OMNI: (
        "Resolve the user's outcome, scope, inputs, outputs, constraints, success criteria, "
        "and ambiguities without changing the objective or inventing authority."
    ),
    PromptStageName.META: (
        "Convert resolved intent into an execution-grade prompt and verification criteria; "
        "preserve unresolved ambiguity and never enlarge capabilities."
    ),
    PromptStageName.FORGE: (
        "Use the bounded repository observation to compile implementation requirements, acceptance criteria, "
        "mutation boundaries, and proof obligations. Treat lexical evidence as advisory and never claim execution or verification."
    ),
    PromptStageName.SIGMA: (
        "Reconcile the current execution contract with bounded repository evidence. Preserve contradictions, dissent, "
        "unresolved tradeoffs, and verification debt; never claim authority, execution, or completion."
    ),
}


def stage_instructions(stage: PromptStageName) -> str:
    return _STAGE_INSTRUCTIONS[stage]


def stage_response_schema() -> dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}, "maxItems": 32}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "stage", "outcome", "scope", "inputs", "outputs", "constraints",
            "successCriteria", "ambiguities",
        ],
        "properties": {
            "stage": {"type": "string", "enum": [stage.value for stage in PromptStageName]},
            "outcome": {"type": "string"},
            "scope": {"type": "string"},
            "inputs": string_array,
            "outputs": string_array,
            "constraints": string_array,
            "successCriteria": string_array,
            "ambiguities": string_array,
            "requestedCapabilities": string_array,
        },
    }
