"""Reasoning-effort normalization and provider wire serialization."""
from __future__ import annotations
from typing import Any

SUPPORTED_REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")


class ReasoningConfigurationError(ValueError):
    """A requested reasoning control cannot be represented safely."""


def normalize_reasoning_effort(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ReasoningConfigurationError("REASONING_EFFORT_MUST_BE_STRING")
    effort = value.strip().lower()
    if not effort:
        return ""
    # Legacy operator/config vocabulary used max; preserve it as the semantic
    # alias for the current highest portable level rather than breaking stored prefs.
    if effort == "max":
        effort = "xhigh"
    if effort not in SUPPORTED_REASONING_EFFORTS:
        raise ReasoningConfigurationError("REASONING_EFFORT_UNSUPPORTED:" + effort)
    return effort


def openai_reasoning_fields(provider_id: str, base_url: str, effort: Any) -> dict[str, Any]:
    """Map an explicit effort onto the provider's OpenAI-compatible wire contract."""
    normalized = normalize_reasoning_effort(effort)
    if not normalized:
        return {}
    provider = str(provider_id or "").strip().lower()
    endpoint = str(base_url or "").strip().lower()
    if provider == "ollama":
        raise ReasoningConfigurationError("REASONING_EFFORT_UNSUPPORTED_PROVIDER:ollama")
    if provider == "openrouter" or "openrouter.ai" in endpoint:
        return {"reasoning": {"effort": normalized}}
    return {"reasoning_effort": normalized}



def legacy_cohort_configuration_reasoning_effort(configuration_id: Any) -> str:
    """Return an effort only for the historical explicit effort aliases.

    A cohort configuration ID is otherwise an opaque identity (e.g.
    ouro-repair-v1), not a model reasoning option. Never reject a valid
    council because an arbitrary configuration ID is not a provider knob.
    """
    if not isinstance(configuration_id, str):
        return ""
    hint = configuration_id.strip().lower()
    if hint in SUPPORTED_REASONING_EFFORTS or hint == "max":
        return normalize_reasoning_effort(hint)
    return ""
