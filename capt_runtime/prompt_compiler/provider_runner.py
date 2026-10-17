"""Local-first compiler-provider policy and bounded analysis-only dispatch."""
from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Optional

from ..errors import AuthorityViolation
from ..resource_governor import TokenCostGovernor
from .models import CompilerProvider, PromptCompileRequest, PromptStageName
from .stages import (
    StructuredStageResult,
    stage_instructions,
    stage_response_schema,
)


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
        if requested_remote and remote_allowed:
            return CompilerProvider(requested_remote, "", "remote")
        if local_available:
            return CompilerProvider(local_provider, local_model, "local")
        if requested_remote and not remote_allowed:
            raise AuthorityViolation("REMOTE_COMPILATION_NOT_AUTHORIZED")
        raise AuthorityViolation("NO_PERMITTED_COMPILER_PROVIDER")


class BoundedPromptCompilerRunner:
    """Dispatch one structured compiler stage under the existing resource governor."""

    def __init__(
        self,
        transport: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        *,
        governor: Optional[TokenCostGovernor] = None,
        max_estimated_prompt_tokens_per_request: Optional[int] = None,
    ) -> None:
        self._transport = transport
        self._governor = governor
        if max_estimated_prompt_tokens_per_request is not None and (
            isinstance(max_estimated_prompt_tokens_per_request, bool)
            or not isinstance(max_estimated_prompt_tokens_per_request, int)
            or max_estimated_prompt_tokens_per_request <= 0
        ):
            raise ValueError("COMPILER_PROMPT_TOKEN_BOUND_INVALID")
        self._max_prompt_tokens = max_estimated_prompt_tokens_per_request

    @staticmethod
    def _estimate_tokens(value: Any) -> int:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return max(1, (len(encoded) + 3) // 4)
    def run(
        self,
        stage: PromptStageName,
        request: PromptCompileRequest,
        provider: CompilerProvider,
        *,
        current_prompt: Optional[str] = None,
        stage_context: Optional[Mapping[str, Any]] = None,
    ) -> StructuredStageResult:
        prompt = current_prompt or request.original_prompt
        payload = {
            "stage": stage.value,
            "analysisOnly": True,
            "instructions": stage_instructions(stage),
            "responseSchema": stage_response_schema(),
            "originalPrompt": request.original_prompt,
            "currentPrompt": prompt,
            "targetRoot": request.target_root,
            "mode": request.mode,
            "allowedCapabilities": list(request.requested_capabilities),
            "compilerProvider": {
                "provider": provider.provider_id,
                "model": provider.model,
                "endpointClass": provider.endpoint_class,
            },
        }
        if stage_context is not None:
            payload["stageContext"] = dict(stage_context)
        prompt_tokens = self._estimate_tokens(payload)
        if self._max_prompt_tokens is not None and prompt_tokens > self._max_prompt_tokens:
            # This is an independent per-request input bound. Never convert a
            # failed bound into a fallback with unreported omitted evidence.
            raise ValueError(
                f"COMPILER_STAGE_CONTEXT_LIMIT: {prompt_tokens} estimated input tokens "
                f"> {self._max_prompt_tokens} per-request budget; "
                "reduce/partition the stage evidence or select a verified wider-context model"
            )
        if self._governor is not None:
            self._governor.check_pre_dispatch(prompt_tokens)
        output = self._transport(payload)
        if self._governor is not None:
            self._governor.record_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=self._estimate_tokens(output),
                cost_usd=0.0,
            )
        result = StructuredStageResult.from_model_output(output)
        if result.stage != stage:
            raise ValueError("compiler stage response identity mismatch")
        return result
