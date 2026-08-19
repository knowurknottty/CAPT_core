"""Provider capability classification (UI Foundation).

Separates PROVIDER REGISTRATION from PROVIDER SUPPORT. A provider template in
providers.json does NOT mean a provider is fully supported. Each provider is
classified across explicit capability axes so the UI never overstates what a
provider can actually do.

Axes:
    REGISTERED                    - a config record exists (template or user-added)
    DISCOVERABLE                  - local discovery implemented (endpoint probe)
    HEALTH_PROBE_IMPLEMENTED      - a real health/latency probe exists
    MODEL_LIST_IMPLEMENTED        - models enumerable from a real API
    MODEL_EXECUTION_IMPLEMENTED   - a real request/response adapter exists
    GOVERNED_EXECUTION_PROVEN     - through CAPT governed mission on real models
    CROSS_MODEL_PROVEN            - real Model A -> shutdown -> Model B continuity
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List



@dataclass
class ProviderCapabilities:
    id: str
    name: str
    kind: str
    transport: str
    registered: bool = True
    discoverable: bool = False
    health_probe: bool = False
    model_list: bool = False
    model_execution: bool = False
    governed_execution_proven: bool = False
    cross_model_proven: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d["support_level"] = self.support_level
        return d

    @property
    def support_level(self) -> str:
        """Honest single label of how much is actually implemented."""
        if not self.registered:
            return "UNREGISTERED"
        if self.cross_model_proven:
            return "CROSS_MODEL_PROVEN"
        if self.governed_execution_proven:
            return "GOVERNED_EXECUTION_PROVEN"
        if self.model_execution:
            return "MODEL_EXECUTION_IMPLEMENTED"
        if self.model_list and self.health_probe:
            return "HEALTH_AND_MODEL_LIST"
        if self.health_probe:
            return "HEALTH_PROBE"
        return "REGISTERED_ONLY"


# The authoritative capability matrix. A template existing alone must not
# upgrade a provider's support level. Adapters implement real behavior; until
# implemented, axes stay False and support_level stays REGISTERED_ONLY.
CAPABILITY_MATRIX: List[ProviderCapabilities] = [
    ProviderCapabilities("openrouter", "OpenRouter", "cloud", "openai_compatible",
                         discoverable=False, health_probe=True, model_list=True,
                         model_execution=False, notes="OpenAI-compatible /models probe; requires API key"),
    ProviderCapabilities("ollama", "Ollama", "local", "ollama",
                         discoverable=True, health_probe=True, model_list=True,
                         model_execution=False, notes="native /api/tags discovery + OpenAI-compat probe"),
    ProviderCapabilities("lmstudio", "LM Studio", "local", "openai_compatible",
                         discoverable=True, health_probe=True, model_list=True,
                         model_execution=False, notes="OpenAI-compatible /v1/models probe"),
    ProviderCapabilities("mlx", "MLX / mlx_lm", "local", "native",
                         registered=False, discoverable=False, health_probe=False, model_list=False,
                         model_execution=False, notes="legacy placeholder retired until a real native adapter exists"),
    ProviderCapabilities("vllm", "vLLM", "hybrid", "openai_compatible",
                         discoverable=False, health_probe=True, model_list=True,
                         model_execution=False, notes="OpenAI-compatible endpoint"),
    ProviderCapabilities("llamacpp", "llama.cpp-server", "local", "openai_compatible",
                         discoverable=True, health_probe=True, model_list=True,
                         model_execution=False, notes="OpenAI-compatible endpoint"),
    ProviderCapabilities("hermes", "Hermes", "local", "subprocess",
                         discoverable=False, health_probe=False, model_list=False,
                         model_execution=False, notes="subprocess compatibility; bounded driver, not a chat provider"),
]


def capability_for(provider_id: str) -> ProviderCapabilities:
    for cap in CAPABILITY_MATRIX:
        if cap.id == provider_id:
            return cap
    return ProviderCapabilities(provider_id, provider_id, "unknown", "unknown",
                                registered=False, notes="unknown/community provider")


def full_matrix() -> List[Dict[str, object]]:
    return [c.to_dict() for c in CAPABILITY_MATRIX]


def level_of(provider_id: str) -> str:
    return capability_for(provider_id).support_level
