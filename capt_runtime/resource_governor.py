"""Governed AI resource and financial ceiling enforcement for CAPT."""

from __future__ import annotations
import threading
from typing import Any, Callable, Dict, Optional


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
        max_output_tokens_per_request: int = 49_152,
        alert_cost_usd: Optional[float] = None,
        on_cost_alert: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.max_tokens_per_session = max_tokens_per_session
        self.max_cost_usd_per_session = max_cost_usd_per_session
        self.max_requests_per_session = max_requests_per_session
        self.max_output_tokens_per_request = max_output_tokens_per_request
        self.alert_cost_usd = alert_cost_usd
        self.on_cost_alert = on_cost_alert
        if alert_cost_usd is not None and (
            alert_cost_usd <= 0 or alert_cost_usd >= max_cost_usd_per_session
        ):
            raise ValueError("COST_ALERT_THRESHOLD_INVALID")

        self.consumed_tokens: int = 0
        self.consumed_cost_usd: float = 0.0
        self.consumed_requests: int = 0
        self.provider_cost_unknown_responses: int = 0
        self._cost_alert_emitted = False
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

    def reserve_provider_request(self, estimated_prompt_tokens: int = 0) -> None:
        """Reserve one physical HTTP attempt atomically before dispatch.

        An interrupted attempt conservatively keeps the request slot consumed,
        even when a response never arrives. This is a local-session ceiling;
        authoritative per-DriverRun count is recorded in EventStore.
        """
        with self._lock:
            self.check_pre_dispatch(estimated_prompt_tokens)
            self.consumed_requests += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "consumedTokens": self.consumed_tokens,
                "consumedCostUsd": self.consumed_cost_usd,
                "consumedRequests": self.consumed_requests,
                "providerCostUnknownResponses": self.provider_cost_unknown_responses,
                "maxTokens": self.max_tokens_per_session,
                "maxCostUsd": self.max_cost_usd_per_session,
                "maxRequests": self.max_requests_per_session,
            }

    def record_usage(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0.0,
        request_already_counted: bool = False,
        cost_known: bool = True,
    ) -> Dict[str, Any]:
        callback = None
        alert = None
        with self._lock:
            total_tokens = prompt_tokens + completion_tokens
            self.consumed_tokens += total_tokens
            self.consumed_cost_usd += cost_usd
            if not request_already_counted:
                self.consumed_requests += 1
            if not cost_known:
                self.provider_cost_unknown_responses += 1

            if (
                self.alert_cost_usd is not None
                and not self._cost_alert_emitted
                and self.consumed_cost_usd >= self.alert_cost_usd
            ):
                self._cost_alert_emitted = True
                alert = {
                    "kind": "spend_threshold_crossed",
                    "thresholdUsd": self.alert_cost_usd,
                    "consumedCostUsd": self.consumed_cost_usd,
                    "maxCostUsd": self.max_cost_usd_per_session,
                    "consumedRequests": self.consumed_requests,
                }
                callback = self.on_cost_alert

            receipt = {
                "consumedTokens": self.consumed_tokens,
                "consumedCostUsd": self.consumed_cost_usd,
                "consumedRequests": self.consumed_requests,
                "providerCostUnknownResponses": self.provider_cost_unknown_responses,
                "maxTokens": self.max_tokens_per_session,
                "maxCostUsd": self.max_cost_usd_per_session,
                "maxRequests": self.max_requests_per_session,
                "costAlert": alert,
            }
        if callback is not None and alert is not None:
            callback(dict(alert))
        return receipt
