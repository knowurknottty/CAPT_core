"""Authoritative context accounting for the memory trigger system.

CAPT owns the trigger decision. This module measures current context usage,
computes the next 32k trigger boundary, and reports the trigger state. Token
estimation is explicit: when exact tokenization is unavailable the value is
labeled ESTIMATED and the tokenizer/model assumptions are recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .policy import TRIGGER_INTERVAL_TOKENS, MemoryTriggerPolicy

# Estimation assumption: 1 token ~= 4 characters for English/code mixed text.
# This is an ESTIMATE; exact provider token counts override it when available.
_CHARS_PER_TOKEN = 4.0
_ESTIMATION_METHOD = "chars/4.0 (ESTIMATED; no exact tokenizer available)"


def estimate_tokens(text: str) -> int:
    """Estimate token count from characters. Labeled ESTIMATED by callers."""
    if not text:
        return 0
    return max(1, int(round(len(text) / _CHARS_PER_TOKEN)))


@dataclass
class ContextUsage:
    """Measured/estimated context usage across accounted components."""

    system_instructions: int = 0
    policy_constraints: int = 0
    mission_spec: int = 0
    task_graph: int = 0
    current_messages: int = 0
    selected_memory: int = 0
    tool_schemas: int = 0
    driver_instructions: int = 0
    retrieved_documents: int = 0
    artifacts: int = 0
    model_output_reserve: int = 0
    verification_reserve: int = 0
    retry_reserve: int = 0
    transport_overhead: int = 0

    def total(self) -> int:
        return sum(
            getattr(self, f.name)
            for f in self.__dataclass_fields__.values()
            if f.name != "transport_overhead"
        ) + self.transport_overhead

    def to_dict(self) -> Dict[str, int]:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["total"] = self.total()
        return d


@dataclass
class TriggerState:
    """Current trigger evaluation state for a mission/run."""

    retrieval_fired: bool = False
    compression_fired: bool = False
    checkpoint_fired: bool = False
    consolidation_fired: bool = False
    hard_stop: bool = False
    last_context_pack_digest: Optional[str] = None
    last_trigger_boundary: int = 0
    last_evaluated_usage: int = 0


class ContextAccounting:
    """Owns context accounting and trigger-boundary math for one policy."""

    def __init__(self, policy: MemoryTriggerPolicy) -> None:
        self.policy = policy

    def next_trigger_boundary(self, current_usage: int, steps: int) -> int:
        """Next multiple of (steps * 32k) at or above current_usage."""
        interval = steps * TRIGGER_INTERVAL_TOKENS
        if current_usage <= 0:
            return interval
        boundary = ((current_usage + interval - 1) // interval) * interval
        return boundary

    def evaluate(
        self,
        usage: ContextUsage,
        state: TriggerState,
        *,
        measured: bool = False,
        tokenizer: str = _ESTIMATION_METHOD,
        confidence: float = 0.5,
    ) -> Dict[str, Any]:
        """Evaluate which triggers fire at the current usage.

        Returns a structured report. Triggers fire when usage >= the trigger
        boundary AND the trigger has not already fired for that boundary
        (idempotent: repeated evaluation at the same usage does not re-fire).
        """
        current = usage.total()
        policy = self.policy

        def _fires(steps: int, already: bool, last_boundary: int) -> tuple:
            boundary = self.next_trigger_boundary(current, steps)
            fired = current >= boundary and not already
            return boundary, fired

        ret_b, ret_fire = _fires(
            policy.retrieval_trigger_steps, state.retrieval_fired, state.last_trigger_boundary
        )
        cmp_b, cmp_fire = _fires(
            policy.compression_trigger_steps, state.compression_fired, state.last_trigger_boundary
        )
        ckpt_b, ckpt_fire = _fires(
            policy.checkpoint_trigger_steps, state.checkpoint_fired, state.last_trigger_boundary
        )
        cons_b, cons_fire = _fires(
            policy.consolidation_trigger_steps, state.consolidation_fired, state.last_trigger_boundary
        )
        hard_b = self.next_trigger_boundary(current, policy.hard_stop_trigger_steps)
        hard_stop = current >= hard_b

        remaining = max(0, policy.model_safe_limit_tokens() - current)
        next_boundary = min(ret_b, cmp_b, ckpt_b, cons_b, hard_b)

        return {
            "estimationMethod": tokenizer,
            "measured": measured,
            "confidence": confidence,
            "currentUsage": current,
            "reservedBudget": policy.model_safe_limit_tokens(),
            "remainingBudget": remaining,
            "nextTriggerBoundary": next_boundary,
            "triggers": {
                "retrieval": {
                    "steps": policy.retrieval_trigger_steps,
                    "tokens": policy.retrieval_tokens(),
                    "boundary": ret_b,
                    "fires": ret_fire,
                },
                "compression": {
                    "steps": policy.compression_trigger_steps,
                    "tokens": policy.compression_tokens(),
                    "boundary": cmp_b,
                    "fires": cmp_fire,
                },
                "checkpoint": {
                    "steps": policy.checkpoint_trigger_steps,
                    "tokens": policy.checkpoint_tokens(),
                    "boundary": ckpt_b,
                    "fires": ckpt_fire,
                },
                "consolidation": {
                    "steps": policy.consolidation_trigger_steps,
                    "tokens": policy.consolidation_tokens(),
                    "boundary": cons_b,
                    "fires": cons_fire,
                },
                "hardStop": {
                    "steps": policy.hard_stop_trigger_steps,
                    "tokens": policy.hard_stop_tokens(),
                    "boundary": hard_b,
                    "fires": hard_stop,
                },
            },
        }

    def account_components(self, components: Dict[str, str]) -> ContextUsage:
        """Build a ContextUsage from raw text components (estimated tokens)."""
        usage = ContextUsage()
        mapping = {
            "system_instructions": "system_instructions",
            "policy_constraints": "policy_constraints",
            "mission_spec": "mission_spec",
            "task_graph": "task_graph",
            "current_messages": "current_messages",
            "selected_memory": "selected_memory",
            "tool_schemas": "tool_schemas",
            "driver_instructions": "driver_instructions",
            "retrieved_documents": "retrieved_documents",
            "artifacts": "artifacts",
        }
        for key, attr in mapping.items():
            setattr(usage, attr, estimate_tokens(components.get(key, "")))
        usage.model_output_reserve = estimate_tokens(components.get("model_output_reserve", ""))
        usage.verification_reserve = estimate_tokens(components.get("verification_reserve", ""))
        usage.retry_reserve = estimate_tokens(components.get("retry_reserve", ""))
        usage.transport_overhead = estimate_tokens(components.get("transport_overhead", ""))
        return usage
