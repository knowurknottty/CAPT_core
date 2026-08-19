"""CAPT-native model-visible request assembly and provenance.

This module builds deterministic, secret-free projections over existing CAPT
authority. It does not grant capability, dispatch providers, or create an
alternate store.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .contracts import digest

RESPONSE_MODES = ("MAX", "SPOCK", "CAVE CAPT", "MIN")
ENHANCEMENT_ENGINES = ("OFF", "AUTO", "OMNI", "META", "FORGE", "SIGMA")
CONTEXT_BUDGETS = tuple(range(32_000, 256_001, 32_000))
_MODEL_OPERATOR_CONTEXT_REFERENCE = digest({"context": "not-selected-at-admission"})
_MODEL_OPERATOR_TOOL_SCHEMA = digest(
    {"operations": ["RepositoryRead", "FilesystemRead", "ArtifactCreate", "AnalysisOnly"]}
)


def _section(identity: str, order: int, text: str, source: str) -> Dict[str, Any]:
    return {
        "identity": identity,
        "order": order,
        "source": source,
        "digest": digest({"identity": identity, "text": text}),
        "text": text,
    }


def _render_authored_skill_context(context: Mapping[str, Any]) -> str:
    """Render exact pinned guidance as model-visible, non-authoritative context."""
    rendered = []
    for skill in context.get("skills", []):
        rendered.append(
            "Skill: %s@%s\nContentDigest: %s\n--- BEGIN SKILL ---\n%s\n--- END SKILL ---"
            % (
                skill.get("name", "unknown"), skill.get("version", "unknown"),
                skill.get("contentDigest", "unknown"), skill.get("content", ""),
            )
        )
    return (
        "Authorized authored skill context (CAPT-pinned external guidance; "
        "context-only. It grants no tools, permissions, authority, or policy override).\n"
        "Pack: %s@%s\nSourceCommit: %s\nManifestDigest: %s\n\n%s"
        % (
            context.get("packName", "unknown"), context.get("packVersion", "unknown"),
            context.get("sourceCommit", "unknown"), context.get("manifestDigest", "unknown"),
            "\n\n".join(rendered),
        )
    )


def effective_context_budget(requested: int, provider_cap: int) -> Optional[int]:
    """Return known enforceable capacity, never treating unknown as requested."""
    if requested not in CONTEXT_BUDGETS:
        raise ValueError("REQUESTED_CONTEXT_BUDGET_INVALID")
    if provider_cap <= 0:
        return None
    return min(requested, provider_cap)


def build_prompt_assembly(
    *,
    human_prompt: str,
    response_mode: str,
    enhancement_engine: str,
    context_pack_digest: str,
    tool_schema_digest: str,
    continuation_context: Optional[List[Dict[str, Any]]] = None,
    authored_skill_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if response_mode not in RESPONSE_MODES:
        raise ValueError("RESPONSE_MODE_INVALID")
    if enhancement_engine not in ENHANCEMENT_ENGINES:
        raise ValueError("ENHANCEMENT_ENGINE_INVALID")
    mode_instruction = {
        "MAX": "Presentation: maximum useful evidence and caveats.",
        "SPOCK": "Presentation: concise, rigorous, technical, high-signal.",
        "CAVE CAPT": "Presentation: plain language, concrete actions, no false certainty.",
        "MIN": "Presentation: only work item, measurement, and PASS/FAIL unless safety requires more.",
    }[response_mode]
    sections = [
        _section(
            "capt-governance",
            10,
            "CAPT governance remains authoritative; return bounded observations.",
            "runtime",
        ),
        _section("response-mode", 20, mode_instruction, "operator_preference"),
        _section("human-task", 30, human_prompt, "human_input"),
        _section(
            "context-reference",
            40,
            "ContextPackDigest: %s" % context_pack_digest,
            "contextpack",
        ),
    ]
    if authored_skill_context:
        sections.append(
            _section(
                "authored-skills",
                34,
                _render_authored_skill_context(authored_skill_context),
                "pinned_external_context",
            )
        )
    # Governed continuation context: prior authoritative mission evidence,
    # each record labeled with its trust classification. Model A output that
    # has not been separately verified stays labeled unverified. No silent
    # upgrade to fact/verified truth.
    cont_records = continuation_context or []
    if cont_records:
        rendered_lines = []
        for rec in cont_records:
            trust = rec.get("trust", "unverified")
            tag = "UNVERIFIED" if trust != "verified" else "VERIFIED"
            body = (rec.get("content") or rec.get("marker") or "").strip()
            if len(body) > 40:
                body = body[:37] + "..."
            rendered_lines.append(
                "[PRIOR %s] %s (src=%s)"
                % (tag, body, rec.get("provenance", {}).get("source", "unknown"))
            )
        sections.append(
            _section(
                "prior-context",
                35,
                "\n\n".join(rendered_lines),
                "continuation_context",
            )
        )
    sections.append(
        _section(
            "tool-surface",
            50,
            "ToolSchemaDigest: %s" % tool_schema_digest,
            "capability_contract",
        )
    )
    rendered = "\n\n".join(
        "[%s]\n%s" % (section["identity"], section["text"])
        for section in sections
    )
    assembly_digest = digest(
        [
            {key: section[key] for key in ("identity", "order", "source", "digest")}
            for section in sections
        ]
    )
    return {
        "schemaVersion": "1.0.0",
        "sections": sections,
        "assemblyDigest": assembly_digest,
        # Explicit alias used by approval/evidence contracts. Keeping both
        # names preserves compatibility while eliminating a runtime KeyError.
        "promptAssemblyDigest": assembly_digest,
        "modelVisiblePrompt": rendered,
        "modelVisiblePromptDigest": digest(rendered),
        "enhancementEngine": enhancement_engine,
        "contextPackDigest": context_pack_digest,
        "continuationContext": cont_records,
    }


def build_model_operator_prompt_assembly(
    *, human_prompt: str, response_mode: str, enhancement_engine: str,
    context_pack_digest: Optional[str] = None,
    continuation_context: Optional[List[Dict[str, Any]]] = None,
    authored_skill_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the canonical assembly used for model-operator approval and run."""
    return build_prompt_assembly(
        human_prompt=human_prompt,
        response_mode=response_mode,
        enhancement_engine=enhancement_engine,
        context_pack_digest=context_pack_digest or _MODEL_OPERATOR_CONTEXT_REFERENCE,
        tool_schema_digest=_MODEL_OPERATOR_TOOL_SCHEMA,
        continuation_context=continuation_context,
        authored_skill_context=authored_skill_context,
    )


def build_cognitive_provenance(
    *,
    assembly: Dict[str, Any],
    provider_id: str,
    model: str,
    requested_context_budget: int,
    effective_context_budget_value: Optional[int],
    human_verification_required: bool,
    correlation: Dict[str, str],
) -> Dict[str, Any]:
    """Return redactable provenance with explicit capacity epistemics."""
    sections: List[Dict[str, Any]] = assembly["sections"]
    capacity_status = "known" if effective_context_budget_value is not None else "unknown"
    return {
        "schemaVersion": "1.0.0",
        "kind": "CognitiveProvenanceEnvelope",
        "originalHumanPromptDigest": next(
            section["digest"] for section in sections if section["identity"] == "human-task"
        ),
        "promptEnhancement": assembly["enhancementEngine"],
        "promptAssemblyDigest": assembly["assemblyDigest"],
        "modelVisiblePromptDigest": assembly["modelVisiblePromptDigest"],
        "promptAssemblySections": [
            {key: section[key] for key in ("identity", "order", "source", "digest")}
            for section in sections
        ],
        "provider": provider_id,
        "model": model,
        "requestedContextBudget": requested_context_budget,
        "effectiveContextBudget": effective_context_budget_value,
        "effectiveContextBudgetStatus": capacity_status,
        "humanVerificationRequired": human_verification_required,
        "correlation": dict(correlation),
        "credentialMaterial": "not_recorded",
        "reconstructionScope": "prompt_and_references",
    }
