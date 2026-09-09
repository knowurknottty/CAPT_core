"""Runtime-owned orchestration for prompt compilation."""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

from ..contracts import digest
from ..errors import AuthorityViolation
from .models import (
    CompilerProvider,
    PromptCompileProposal,
    PromptCompileRequest,
    PromptStageName,
    PromptStageRecord,
    PromptVerificationContract,
)
from .provider_runner import BoundedPromptCompilerRunner
from .router import PromptRoute, route_stages
from .stages import StructuredStageResult, render_execution_prompt
from .repository_intelligence import stage_repository_context


class PromptCompiler:
    def __init__(
        self,
        *,
        runner: Optional[BoundedPromptCompilerRunner] = None,
        provider: Optional[CompilerProvider] = None,
        remote_compilation_authorized: bool = False,
    ) -> None:
        self._runner = runner
        self._provider = provider
        self._remote_compilation_authorized = bool(remote_compilation_authorized)

    def admit_stage_result(
        self,
        request: PromptCompileRequest,
        result: StructuredStageResult,
    ) -> StructuredStageResult:
        allowed = set(request.requested_capabilities)
        requested = set(result.requested_capabilities)
        if not requested.issubset(allowed):
            raise AuthorityViolation("prompt stage capability escalation refused")
        return result

    def compile(self, request: PromptCompileRequest) -> PromptCompileProposal:
        route = route_stages(request)
        if not route:
            return self._proposal(
                request,
                route,
                status="ready_for_approval",
                proposed_prompt=request.original_prompt,
                stage_records=(),
                requested_capabilities=request.requested_capabilities,
            )

        if self._requires_clarification(route):
            return self._proposal(
                request,
                route,
                status="clarification_required",
                proposed_prompt=request.original_prompt,
                stage_records=self._disabled_records(request, route),
                requested_capabilities=(),
                unresolved_questions=("Clarify the intended outcome and scope before execution.",),
            )
        if self._runner is None or self._provider is None:
            return self._proposal(
                request,
                route,
                status="compiler_unavailable",
                proposed_prompt=request.original_prompt,
                stage_records=self._disabled_records(request, route),
                requested_capabilities=request.requested_capabilities,
            )

        if (
            self._provider.endpoint_class == "remote"
            and not request.remote_compilation_authorized
            and not self._remote_compilation_authorized
        ):
            raise AuthorityViolation("REMOTE_COMPILATION_NOT_AUTHORIZED")

        current_prompt = request.original_prompt
        records = []
        unresolved = []
        acceptance_criteria = ()
        for stage in route:
            stage_context = None
            if stage in (PromptStageName.FORGE, PromptStageName.SIGMA):
                stage_context = stage_repository_context(
                    request.target_root, request.original_prompt, list(acceptance_criteria) or [request.original_prompt]
                )
            result = self._runner.run(
                stage, request, self._provider, current_prompt=current_prompt, stage_context=stage_context
            )
            self.admit_stage_result(request, result)
            next_prompt = render_execution_prompt(request.original_prompt, result)
            records.append(self._record(stage, current_prompt, next_prompt, True))
            unresolved.extend(result.ambiguities)
            acceptance_criteria = result.success_criteria
            current_prompt = next_prompt

        # Model-generated ambiguities are advisory review notes, not approval vetoes.
        # True clarification blockers are handled before model execution by
        # _requires_clarification(route), where CAPT can prove the operator
        # objective/scope is too underspecified to bind safely.
        status = "ready_for_approval"
        return self._proposal(
            request,
            route,
            status=status,
            proposed_prompt=current_prompt,
            stage_records=tuple(records),
            requested_capabilities=request.requested_capabilities,
            unresolved_questions=tuple(unresolved),
            verification_contract=PromptVerificationContract(acceptance_criteria),
        )

    @staticmethod
    def _requires_clarification(route: PromptRoute) -> bool:
        return (
            route.stage_chain == (PromptStageName.OMNI,)
            and "clarification" in route.rationale.lower()
        )

    def _record(
        self,
        stage: PromptStageName,
        input_prompt: str,
        output_prompt: str,
        execution_enabled: bool,
    ) -> PromptStageRecord:
        provider = self._provider or CompilerProvider("", "", "")
        return PromptStageRecord(
            stage=stage,
            version="1",
            execution_enabled=execution_enabled,
            input_digest=digest(input_prompt),
            output_digest=digest(output_prompt),
            provider_id=provider.provider_id,
            model=provider.model,
            endpoint_class=provider.endpoint_class,
        )

    def _disabled_records(
        self,
        request: PromptCompileRequest,
        route: Iterable[PromptStageName],
    ) -> Tuple[PromptStageRecord, ...]:
        return tuple(
            self._record(stage, request.original_prompt, request.original_prompt, False)
            for stage in route
        )

    @staticmethod
    def _proposal(
        request: PromptCompileRequest,
        route: PromptRoute,
        *,
        status: str,
        proposed_prompt: str,
        stage_records: Tuple[PromptStageRecord, ...],
        requested_capabilities: Tuple[str, ...],
        unresolved_questions: Tuple[str, ...] = (),
        verification_contract: PromptVerificationContract = PromptVerificationContract(),
    ) -> PromptCompileProposal:
        return PromptCompileProposal(
            status=status,
            original_prompt=request.original_prompt,
            proposed_prompt=proposed_prompt,
            stage_chain=route.stage_chain,
            stage_records=stage_records,
            requested_capabilities=requested_capabilities,
            verification_contract=verification_contract,
            unresolved_questions=unresolved_questions,
            rationale=route.rationale,
        )
