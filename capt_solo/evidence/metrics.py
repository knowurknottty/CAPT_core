"""Long-Session Efficiency Controls and Anti-Loop Guards.

Tracks operational metrics for 444-turn missions and detects/halts loops:
- repeated equivalent verification;
- repeated identical file reads without state change;
- repeated failed mutation with unchanged input;
- repeated re-explanation to a guard;
- repeated creation of duplicate mission states;
- repeated memory promotion attempts for the same candidate;
- repeated self-modification proposals;
- repeated blocked commands through alternate phrasing.

Optimizes for maximum verified progress per unit of execution, not low tool usage.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class EfficiencyMetrics:
    total_tool_calls: int = 0
    repeated_reads: int = 0
    repeated_verification_requests: int = 0
    evidence_reuse_count: int = 0
    full_suite_runs_avoided: int = 0
    targeted_test_runs: int = 0
    failed_mutation_retries: int = 0
    context_reconstruction_events: int = 0
    redundant_file_inspections: int = 0
    stale_checkpoint_detections: int = 0
    unresolved_blockers: int = 0
    self_modification_attempts: int = 0
    invalidation_events: int = 0
    evidence_records_reused: int = 0
    evidence_records_invalidated: int = 0

    def snapshot(self) -> Dict[str, int]:
        return self.__dict__


class AntiLoopGuard:
    def __init__(self, max_repeats: int = 3) -> None:
        self._max = max_repeats
        self._seen: Dict[str, int] = defaultdict(int)
        self.metrics = EfficiencyMetrics()

    def _key(self, category: str, signature: str) -> str:
        return f"{category}:{signature}"

    def observe(self, category: str, signature: str) -> Tuple[bool, str]:
        """Record an occurrence. Returns (is_loop, message).

        If the same (category, signature) repeats beyond max_repeats, returns
        is_loop=True with a non-progress explanation. Otherwise records and
        returns is_loop=False.
        """
        key = self._key(category, signature)
        self._seen[key] += 1
        count = self._seen[key]
        if count > self._max:
            return True, (
                f"Loop detected: '{category}' signature repeated {count} times "
                f"with no state change. Non-progress condition. Choose a materially "
                f"different safe action or stop; do not bypass policy or user denial.")
        return False, f"observed ({count}/{self._max})"

    # Convenience helpers per mission spec.
    def repeated_verification(self, vsi_signature: str) -> Tuple[bool, str]:
        self.metrics.repeated_verification_requests += 1
        return self.observe("verification", vsi_signature)

    def repeated_read(self, path_signature: str) -> Tuple[bool, str]:
        self.metrics.repeated_reads += 1
        return self.observe("read", path_signature)

    def repeated_failed_mutation(self, mutation_signature: str) -> Tuple[bool, str]:
        self.metrics.failed_mutation_retries += 1
        return self.observe("failed_mutation", mutation_signature)

    def repeated_blocked_command(self, command_signature: str) -> Tuple[bool, str]:
        return self.observe("blocked_command", command_signature)

    def repeated_selfmod_proposal(self, proposal_signature: str) -> Tuple[bool, str]:
        self.metrics.self_modification_attempts += 1
        return self.observe("selfmod_proposal", proposal_signature)

    def repeated_promotion(self, candidate_signature: str) -> Tuple[bool, str]:
        return self.observe("promotion", candidate_signature)

    def repeated_checkpoint(self, mission_signature: str) -> Tuple[bool, str]:
        return self.observe("checkpoint", mission_signature)

    def record_reuse(self, n: int = 1) -> None:
        self.metrics.evidence_reuse_count += 1
        self.metrics.evidence_records_reused += n

    def record_full_suite_avoided(self) -> None:
        self.metrics.full_suite_runs_avoided += 1

    def reset_category(self, category: str) -> None:
        for k in list(self._seen):
            if k.startswith(f"{category}:"):
                del self._seen[k]
