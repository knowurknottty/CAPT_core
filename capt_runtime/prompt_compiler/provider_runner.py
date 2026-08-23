"""Local-first compiler-provider policy and bounded analysis-only dispatch."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from ..errors import AuthorityViolation
from .models import CompilerProvider, PromptCompileRequest, PromptStageName
from .stages import StructuredStageResult


class PromptCompilerProviderPolicy:
    def resolve(
        self,
        *,
        local_available: bool,
        remote_allowed: bool = False,
        requested_remote: str = "",
        local_provider: str = "local",
        local_model: str = "",
    ) -> CompilerProvider:
        if local_available:
            return CompilerProvider(local_provider, local_model, "local")
        if requested_remote and not remote_allowed:
            raise AuthorityViolation("REMOTE_COMPILATION_NOT_AUTHORIZED")
        if requested_remote and remote_allowed:
            return CompilerProvider(requested_remote, "", "remote")
        raise AuthorityViolation("NO_PERMITTED_COMPILER_PROVIDER")


class BoundedPromptCompilerRunner:
    """Dispatch one structured, analysis-only compiler stage."""

    def __init__(self, transport: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> None:
        self._transport = transport

    def run(
        self,
        request: PromptCompileRequest,
        stage: PromptStageName,
        *,
        current_prompt: str,
    ) -> StructuredStageResult:
        payload = {
            "stage": stage.value,
            "analysisOnly": True,
            "originalPrompt": request.original_prompt,
            "currentPrompt": current_prompt,
            "targetRoot": request.target_root,
            "mode": request.mode,
            "allowedCapabilities": list(request.requested_capabilities),
        }
        output = self._transport(payload)
        result = StructuredStageResult.from_model_output(output)
        if result.stage != stage:
            raise ValueError("compiler stage response identity mismatch")
        return result
