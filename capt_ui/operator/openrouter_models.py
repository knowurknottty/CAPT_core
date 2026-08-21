"""Operator-approved OpenRouter catalog; unresolved labels never become guessed IDs."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class OpenRouterModel:
    label: str
    model_id: str | None
    text_compatible: bool = True

_APPROVED = (
    "Hy3", "MiMo-V2.5", "Kimi K2.7 Code", "MiniMax M3", "Kimi K3", "MiMo-V2.5-Pro", "Ling-2.6-flash", "Ling-2.6-LT", "Nemotron 3 Ultra (free)", "North Mini Code (free)", "DeepSeek V4 Flash 0731", "Step 3.7 Flash", "DeepSeek V4 Pro 0813", "DeepSeek V4 Pro", "Hy3 preview", "Step 3.5 Flash", "Hunyuan A13B Instruct", "Nemotron 3 Super (free)", "Laguna S 2.1 (free)", "Laguna S 2.1", "Laguna XS 2.1 (free)", "Laguna XS 2.1", "H3", "MiniMax M2.7", "LFM2.5-2.6B (free)", "Lyria 3 Pro Preview", "Lyria 3 Clip Preview", "Ling-3.0-flash", "Ring-2.6-LT", "Nano Banana (Gemini 2.5 Flash Image)", "Uncensored",
)

OPENROUTER_MODELS = tuple(OpenRouterModel(label, "deepseek/deepseek-v4-flash-0731" if label == "DeepSeek V4 Flash 0731" else None, text_compatible=not label.startswith("Lyria") and not label.startswith("Nano Banana")) for label in _APPROVED)

def available_text_models() -> list[OpenRouterModel]:
    return [model for model in OPENROUTER_MODELS if model.model_id and model.text_compatible]
