"""MemoryTriggerPolicy model and 32k-step validation (ADR-DT-M1-MEM-001).

The trigger interval is a FIXED 32,768 tokens. Every trigger type has an
independent step count. Effective token thresholds are exact multiples of
32,768. No arbitrary non-32k values are permitted unless an explicit
compatibility mode is documented (not used here).

Precedence (highest authority first):
    constitutional > runtime_policy > model_provider > project_policy
    > operator_selected > driver_preference

A lower-authority layer may NARROW but may not WIDEN a higher-authority bound.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from ..contracts import require

# Fixed trigger interval. Do not change without an ADR.
TRIGGER_INTERVAL_TOKENS = 32_768

# Supported threshold ladder (steps). The architecture supports further 32k
# increments without code changes beyond configuration limits.
SUPPORTED_LADDER_STEPS = [1, 2, 3, 4, 5, 6, 7, 8]  # 32k .. 256k

# Precedence ranking: higher number = higher authority.
_PRECEDENCE = {
    "constitutional": 60,
    "runtime_policy": 50,
    "model_provider": 40,
    "project_policy": 30,
    "operator_selected": 20,
    "driver_preference": 10,
}


class PolicySource:
    CONSTITUTIONAL = "constitutional"
    RUNTIME_POLICY = "runtime_policy"
    MODEL_PROVIDER = "model_provider"
    PROJECT_POLICY = "project_policy"
    OPERATOR_SELECTED = "operator_selected"
    DRIVER_PREFERENCE = "driver_preference"


def precedence_rank(source: str) -> int:
    return _PRECEDENCE.get(source, 0)


def validate_policy_steps(
    name: str,
    steps: int,
    *,
    max_steps: Optional[int] = None,
    min_steps: int = 1,
) -> int:
    """Validate a single trigger step count.

    Rejects zero, negative, non-integer, and over-limit values. The raw value
    MUST already be an integer step count (callers convert tokens -> steps via
    steps = tokens // TRIGGER_INTERVAL_TOKENS and must assert exact multiple).
    """
    if not isinstance(steps, int) or isinstance(steps, bool):
        raise ValueError("%s must be an integer step count, got %r" % (name, steps))
    if steps < min_steps:
        raise ValueError("%s must be >= %d, got %d" % (name, min_steps, steps))
    if max_steps is not None and steps > max_steps:
        raise ValueError(
            "%s=%d exceeds configured safe limit of %d steps" % (name, steps, max_steps)
        )
    return steps


def steps_to_tokens(steps: int) -> int:
    if steps < 1:
        raise ValueError("steps must be >= 1")
    return steps * TRIGGER_INTERVAL_TOKENS


def tokens_to_steps(tokens: int) -> int:
    """Convert a raw token threshold to steps, rejecting non-multiples."""
    if tokens <= 0:
        raise ValueError("token threshold must be positive, got %d" % tokens)
    if tokens % TRIGGER_INTERVAL_TOKENS != 0:
        raise ValueError(
            "token threshold %d is not an exact multiple of %d"
            % (tokens, TRIGGER_INTERVAL_TOKENS)
        )
    return tokens // TRIGGER_INTERVAL_TOKENS


class MemoryTriggerPolicy:
    """CAPT-owned mandatory memory trigger policy.

    The policy is immutable once constructed; updates produce a NEW policy with
    an incremented policyVersion and a new digest. The previous digest is
    recorded for replay/audit.
    """

    def __init__(
        self,
        *,
        policy_version: int = 1,
        retrieval_trigger_steps: int,
        compression_trigger_steps: int,
        checkpoint_trigger_steps: int,
        consolidation_trigger_steps: int,
        hard_stop_trigger_steps: int,
        model_safe_limit_steps: int,
        source: str = PolicySource.RUNTIME_POLICY,
        operator_id: Optional[str] = None,
        previous_policy_digest: Optional[str] = None,
        command_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        # Validate all step counts against the model safe limit.
        max_steps = model_safe_limit_steps
        self.retrieval_trigger_steps = validate_policy_steps(
            "retrieval_trigger_steps", retrieval_trigger_steps, max_steps=max_steps
        )
        self.compression_trigger_steps = validate_policy_steps(
            "compression_trigger_steps", compression_trigger_steps, max_steps=max_steps
        )
        self.checkpoint_trigger_steps = validate_policy_steps(
            "checkpoint_trigger_steps", checkpoint_trigger_steps, max_steps=max_steps
        )
        self.consolidation_trigger_steps = validate_policy_steps(
            "consolidation_trigger_steps",
            consolidation_trigger_steps,
            max_steps=max_steps,
        )
        self.hard_stop_trigger_steps = validate_policy_steps(
            "hard_stop_trigger_steps", hard_stop_trigger_steps, max_steps=max_steps
        )
        self.model_safe_limit_steps = validate_policy_steps(
            "model_safe_limit_steps", model_safe_limit_steps
        )
        if source not in _PRECEDENCE:
            raise ValueError("unknown policy source %r" % source)
        self.source = source
        self.operator_id = operator_id
        self.policy_version = policy_version
        self.previous_policy_digest = previous_policy_digest
        self.command_id = command_id
        self.correlation_id = correlation_id
        self.timestamp = timestamp
        self.policy_digest = self._compute_digest()

    # -- conversions -------------------------------------------------------

    def steps_to_tokens(self, steps: int) -> int:
        return steps * TRIGGER_INTERVAL_TOKENS

    def retrieval_tokens(self) -> int:
        return self.steps_to_tokens(self.retrieval_trigger_steps)

    def compression_tokens(self) -> int:
        return self.steps_to_tokens(self.compression_trigger_steps)

    def checkpoint_tokens(self) -> int:
        return self.steps_to_tokens(self.checkpoint_trigger_steps)

    def consolidation_tokens(self) -> int:
        return self.steps_to_tokens(self.consolidation_trigger_steps)

    def hard_stop_tokens(self) -> int:
        return self.steps_to_tokens(self.hard_stop_trigger_steps)

    def model_safe_limit_tokens(self) -> int:
        return self.steps_to_tokens(self.model_safe_limit_steps)

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "policyVersion": self.policy_version,
            "triggerIntervalTokens": TRIGGER_INTERVAL_TOKENS,
            "retrievalTriggerSteps": self.retrieval_trigger_steps,
            "compressionTriggerSteps": self.compression_trigger_steps,
            "checkpointTriggerSteps": self.checkpoint_trigger_steps,
            "consolidationTriggerSteps": self.consolidation_trigger_steps,
            "hardStopTriggerSteps": self.hard_stop_trigger_steps,
            "modelSafeLimitSteps": self.model_safe_limit_steps,
            "source": self.source,
            "operatorId": self.operator_id,
            "previousPolicyDigest": self.previous_policy_digest,
            "policyDigest": self.policy_digest,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryTriggerPolicy":
        require("MemoryTriggerPolicy", d)
        return cls(
            policy_version=d["policyVersion"],
            retrieval_trigger_steps=d["retrievalTriggerSteps"],
            compression_trigger_steps=d["compressionTriggerSteps"],
            checkpoint_trigger_steps=d["checkpointTriggerSteps"],
            consolidation_trigger_steps=d["consolidationTriggerSteps"],
            hard_stop_trigger_steps=d["hardStopTriggerSteps"],
            model_safe_limit_steps=d["modelSafeLimitSteps"],
            source=d["source"],
            operator_id=d.get("operatorId"),
            previous_policy_digest=d.get("previousPolicyDigest"),
        )

    def _compute_digest(self) -> str:
        canon = (
            "v%d|iv%d|ret%d|cmp%d|ckpt%d|cons%d|hard%d|safe%d|src%s|op%s"
            % (
                self.policy_version,
                TRIGGER_INTERVAL_TOKENS,
                self.retrieval_trigger_steps,
                self.compression_trigger_steps,
                self.checkpoint_trigger_steps,
                self.consolidation_trigger_steps,
                self.hard_stop_trigger_steps,
                self.model_safe_limit_steps,
                self.source,
                self.operator_id or "",
            )
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(canon).hexdigest()

    def with_update(
        self,
        *,
        retrieval_trigger_steps: Optional[int] = None,
        compression_trigger_steps: Optional[int] = None,
        checkpoint_trigger_steps: Optional[int] = None,
        consolidation_trigger_steps: Optional[int] = None,
        hard_stop_trigger_steps: Optional[int] = None,
        model_safe_limit_steps: Optional[int] = None,
        source: Optional[str] = None,
        operator_id: Optional[str] = None,
        command_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> "MemoryTriggerPolicy":
        """Produce a new policy with narrowed/widened steps, enforcing precedence.

        A lower-authority source may NARROW but may not WIDEN a higher-authority
        bound. The model safe limit may only be set by a source at or above
        model_provider precedence; operator_selected / driver_preference cannot
        raise it.
        """
        new_source = source or self.source
        if precedence_rank(new_source) < precedence_rank(self.source):
            # Lower authority cannot widen any bound set by higher authority.
            # It may only narrow. We validate each proposed change.
            pass
        max_steps = model_safe_limit_steps or self.model_safe_limit_steps
        proposed = {
            "retrieval_trigger_steps": retrieval_trigger_steps,
            "compression_trigger_steps": compression_trigger_steps,
            "checkpoint_trigger_steps": checkpoint_trigger_steps,
            "consolidation_trigger_steps": consolidation_trigger_steps,
            "hard_stop_trigger_steps": hard_stop_trigger_steps,
        }
        current = {
            "retrieval_trigger_steps": self.retrieval_trigger_steps,
            "compression_trigger_steps": self.compression_trigger_steps,
            "checkpoint_trigger_steps": self.checkpoint_trigger_steps,
            "consolidation_trigger_steps": self.consolidation_trigger_steps,
            "hard_stop_trigger_steps": self.hard_stop_trigger_steps,
        }
        # Enforce: lower authority may not widen a higher-authority bound.
        if precedence_rank(new_source) < precedence_rank(self.source):
            for k, v in proposed.items():
                if v is not None and v > current[k]:
                    raise ValueError(
                        "%s (authority %s) may not widen %s=%d set by %s"
                        % (new_source, k, k, current[k], self.source)
                    )
        return MemoryTriggerPolicy(
            policy_version=self.policy_version + 1,
            retrieval_trigger_steps=retrieval_trigger_steps
            if retrieval_trigger_steps is not None else self.retrieval_trigger_steps,
            compression_trigger_steps=compression_trigger_steps
            if compression_trigger_steps is not None else self.compression_trigger_steps,
            checkpoint_trigger_steps=checkpoint_trigger_steps
            if checkpoint_trigger_steps is not None else self.checkpoint_trigger_steps,
            consolidation_trigger_steps=consolidation_trigger_steps
            if consolidation_trigger_steps is not None else self.consolidation_trigger_steps,
            hard_stop_trigger_steps=hard_stop_trigger_steps
            if hard_stop_trigger_steps is not None else self.hard_stop_trigger_steps,
            model_safe_limit_steps=max_steps,
            source=new_source,
            operator_id=operator_id or self.operator_id,
            previous_policy_digest=self.policy_digest,
            command_id=command_id,
            correlation_id=correlation_id,
            timestamp=timestamp,
        )


def effective_policy(
    *,
    model_safe_limit_steps: int,
    operator_retrieval_steps: Optional[int] = None,
    operator_compression_steps: Optional[int] = None,
    operator_checkpoint_steps: Optional[int] = None,
    operator_consolidation_steps: Optional[int] = None,
    operator_hard_stop_steps: Optional[int] = None,
    project_retrieval_steps: Optional[int] = None,
    project_compression_steps: Optional[int] = None,
    project_checkpoint_steps: Optional[int] = None,
    project_consolidation_steps: Optional[int] = None,
    project_hard_stop_steps: Optional[int] = None,
) -> MemoryTriggerPolicy:
    """Resolve the effective policy from layered defaults.

    Precedence (narrowing only, highest wins):
        constitutional/runtime > model_provider (safe limit) > project > operator

    Operator-selected values may only NARROW project/model bounds; they cannot
    widen them. The model safe limit is the ceiling for all triggers.
    """
    # Start from model safe limit as the widest allowed.
    retrieval = model_safe_limit_steps
    compression = model_safe_limit_steps
    checkpoint = model_safe_limit_steps
    consolidation = model_safe_limit_steps
    hard_stop = model_safe_limit_steps

    # Project policy narrows.
    if project_retrieval_steps is not None:
        retrieval = min(retrieval, project_retrieval_steps)
    if project_compression_steps is not None:
        compression = min(compression, project_compression_steps)
    if project_checkpoint_steps is not None:
        checkpoint = min(checkpoint, project_checkpoint_steps)
    if project_consolidation_steps is not None:
        consolidation = min(consolidation, project_consolidation_steps)
    if project_hard_stop_steps is not None:
        hard_stop = min(hard_stop, project_hard_stop_steps)

    # Operator selection narrows further (cannot widen).
    if operator_retrieval_steps is not None:
        retrieval = min(retrieval, operator_retrieval_steps)
    if operator_compression_steps is not None:
        compression = min(compression, operator_compression_steps)
    if operator_checkpoint_steps is not None:
        checkpoint = min(checkpoint, operator_checkpoint_steps)
    if operator_consolidation_steps is not None:
        consolidation = min(consolidation, operator_consolidation_steps)
    if operator_hard_stop_steps is not None:
        hard_stop = min(hard_stop, operator_hard_stop_steps)

    return MemoryTriggerPolicy(
        retrieval_trigger_steps=retrieval,
        compression_trigger_steps=compression,
        checkpoint_trigger_steps=checkpoint,
        consolidation_trigger_steps=consolidation,
        hard_stop_trigger_steps=hard_stop,
        model_safe_limit_steps=model_safe_limit_steps,
        source=PolicySource.RUNTIME_POLICY,
    )
