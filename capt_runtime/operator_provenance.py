"""CAPT-native model-visible request assembly and provenance.

This is a deterministic value builder, not an authority or storage layer.  The
RuntimeService persists the assembled objective; the runner receipt carries the
envelope so a completed governed request can be reconstructed without TUI state.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .contracts import digest

RESPONSE_MODES = ("MAX", "SPOCK", "CAVE CAPT", "MIN")
CONTEXT_BUDGETS = tuple(range(32_000, 256_001, 32_000))


def _section(identity: str, order: int, text: str, source: str) -> Dict[str, Any]:
    return {"identity": identity, "order": order, "source": source,
            "digest": digest({"identity": identity, "text": text}), "text": text}


def effective_context_budget(requested: int, provider_cap: int) -> int:
    """Never claim capacity the selected adapter has not advertised."""
    if requested not in CONTEXT_BUDGETS:
        raise ValueError("REQUESTED_CONTEXT_BUDGET_INVALID")
    return min(requested, provider_cap) if provider_cap > 0 else requested


def build_prompt_assembly(*, human_prompt: str, response_mode: str,
                          enhancement_engine: str, context_pack_digest: str,
                          tool_schema_digest: str) -> Dict[str, Any]:
    if response_mode not in RESPONSE_MODES:
        raise ValueError("RESPONSE_MODE_INVALID")
    mode_instruction = {
        "MAX": "Presentation: maximum useful evidence and caveats.",
        "SPOCK": "Presentation: concise, rigorous, technical, high-signal.",
        "CAVE CAPT": "Presentation: plain language, concrete actions, no false certainty.",
        "MIN": "Presentation: only work item, measurement, and PASS/FAIL unless safety requires more.",
    }[response_mode]
    sections = [
        _section("capt-governance", 10, "CAPT governance remains authoritative; return bounded observations.", "runtime"),
        _section("response-mode", 20, mode_instruction, "operator_preference"),
        _section("human-task", 30, human_prompt, "human_input"),
        _section("context-reference", 40, "ContextPackDigest: %s" % context_pack_digest, "contextpack"),
        _section("tool-surface", 50, "ToolSchemaDigest: %s" % tool_schema_digest, "capability_contract"),
    ]
    rendered = "\n\n".join("[%s]\n%s" % (s["identity"], s["text"]) for s in sections)
    return {"schemaVersion": "1.0.0", "sections": sections,
            "assemblyDigest": digest([{k: s[k] for k in ("identity", "order", "source", "digest")} for s in sections]),
            "modelVisiblePrompt": rendered, "modelVisiblePromptDigest": digest(rendered),
            "enhancementEngine": enhancement_engine}


def build_cognitive_provenance(*, assembly: Dict[str, Any], provider_id: str,
                               model: str, requested_context_budget: int,
                               effective_context_budget_value: int,
                               human_verification_required: bool,
                               correlation: Dict[str, str]) -> Dict[str, Any]:
    """Return redactable provenance; it intentionally contains no credentials."""
    sections: List[Dict[str, Any]] = assembly["sections"]
    return {
        "schemaVersion": "1.0.0",
        "kind": "CognitiveProvenanceEnvelope",
        "originalHumanPromptDigest": next(s["digest"] for s in sections if s["identity"] == "human-task"),
        "promptEnhancement": assembly["enhancementEngine"],
        "promptAssemblyDigest": assembly["assemblyDigest"],
        "modelVisiblePromptDigest": assembly["modelVisiblePromptDigest"],
        "promptAssemblySections": [{k: s[k] for k in ("identity", "order", "source", "digest")} for s in sections],
        "provider": provider_id, "model": model,
        "requestedContextBudget": requested_context_budget,
        "effectiveContextBudget": effective_context_budget_value,
        "humanVerificationRequired": human_verification_required,
        "correlation": dict(correlation),
        "credentialMaterial": "not_recorded",
    }
