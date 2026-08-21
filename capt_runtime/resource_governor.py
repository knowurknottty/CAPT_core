"""Governed AI resource and financial ceiling enforcement for CAPT."""

from __future__ import annotations
import threading
from typing import Any, Dict, Optional


class BudgetCeilingExceeded(RuntimeError):
    pass


class TokenCostGovernor:
    """Thread-safe resource governor enforcing token, cost, and request ceilings."""

    def __init__(
        self,
        *,
        max_tokens_per_session: int = 1_000_000,
        max_cost_usd_per_session: float = 10.0,
        max_requests_per_session: int = 100,
        max_output_tokens_per_request: int = 16_384,
    ) -> None:
        self.max_tokens_per_session = max_tokens_per_session
        self.max_cost_usd_per_session = max_cost_usd_per_session
        self.max_requests_per_session = max_requests_per_session
        self.max_output_tokens_per_request = max_output_tokens_per_request

        self.consumed_tokens: int = 0
        self.consumed_cost_usd: float = 0.0
        self.consumed_requests: int = 0
        self._lock = threading.RLock()

    def check_pre_dispatch(self, estimated_prompt_tokens: int = 0) -> None:
        with self._lock:
            if self.consumed_requests + 1 > self.max_requests_per_session:
                raise BudgetCeilingExceeded(
                    f"REQUEST_CEILING_BREACHED: {self.consumed_requests + 1} > {self.max_requests_per_session}"
                )
            if self.consumed_tokens + estimated_prompt_tokens > self.max_tokens_per_session:
                raise BudgetCeilingExceeded(
                    f"TOKEN_CEILING_BREACHED: {self.consumed_tokens + estimated_prompt_tokens} > {self.max_tokens_per_session}"
                )
            if self.consumed_cost_usd >= self.max_cost_usd_per_session:
                raise BudgetCeilingExceeded(
                    f"COST_CEILING_BREACHED: ${self.consumed_cost_usd:.4f} >= ${self.max_cost_usd_per_session:.2f}"
                )

    def record_usage(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0.0,
    ) -> Dict[str, Any]:
        with self._lock:
            total_tokens = prompt_tokens + completion_tokens
            self.consumed_tokens += total_tokens
            self.consumed_cost_usd += cost_usd
            self.consumed_requests += 1

            receipt = {
                "consumedTokens": self.consumed_tokens,
                "consumedCostUsd": self.consumed_cost_usd,
                "consumedRequests": self.consumed_requests,
                "maxTokens": self.max_tokens_per_session,
                "maxCostUsd": self.max_cost_usd_per_session,
                "maxRequests": self.max_requests_per_session,
            }
            return receipt
