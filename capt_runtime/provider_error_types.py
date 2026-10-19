"""Bounded OpenRouter error typing; never return upstream messages or request data.

OpenRouter documents stable values at
https://openrouter.ai/docs/api-reference/errors-and-debugging
Do not persist arbitrary metadata, provider codes, or messages.
"""
from __future__ import annotations

from typing import Any

_SAFE_ERROR_TYPES = frozenset({
    "context_length_exceeded", "max_tokens_exceeded", "token_limit_exceeded",
    "string_too_long", "authentication", "permission_denied",
    "payment_required", "rate_limit_exceeded", "provider_overloaded",
    "provider_unavailable", "invalid_request", "invalid_prompt",
    "not_found", "precondition_failed", "payload_too_large",
    "unprocessable", "content_policy_violation", "refusal",
    "invalid_image", "image_too_large", "image_too_small",
    "unsupported_image_format", "image_not_found", "image_download_failed",
    "server", "timeout", "unmapped",
})


def safe_openrouter_error_type(value: Any) -> str | None:
    """Only known canonical codes; never pass through an arbitrary string."""
    return value if isinstance(value, str) and value in _SAFE_ERROR_TYPES else None


def openrouter_error_type(payload: Any) -> str | None:
    """Read only error.metadata.error_type from a bounded JSON document."""
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    metadata = error.get("metadata")
    if not isinstance(metadata, dict):
        return None
    return safe_openrouter_error_type(metadata.get("error_type"))


def openrouter_embedded_error(payload: Any) -> tuple[bool, str | None]:
    """Detect both HTTP-200 top-level and choice-level provider errors.

    The returned value is a Boolean and an allowlisted enum. All potentially
    sensitive text, code and metadata remain unobserved by the caller.
    """
    if not isinstance(payload, dict):
        return (False, None)
    error = payload.get("error")
    if isinstance(error, dict):
        return (True, openrouter_error_type(payload))
    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            if choice.get("finish_reason") != "error":
                continue
            nested = choice.get("error")
            if isinstance(nested, dict):
                return (True, openrouter_error_type({"error": nested}))
    return (False, None)
