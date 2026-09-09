"""CAPT-owned reservation planner for free-tier-native Cloudflare work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable

from capt_runtime.errors import AuthorityViolation

from .cloudflare_free_router import (
    CloudflareFreeEstimate,
    CloudflareFreeTierRouter,
    CloudflareRouteDecision,
    CloudflareWorkClass,
)
from .cloudflare_usage import CloudflareUsageLedger


@dataclass(frozen=True)
class CloudflareFreePlan:
    route: CloudflareRouteDecision
    reservation: dict[str, str]


class CloudflareFreeExecutionPlanner:
    def __init__(
        self,
        ledger: CloudflareUsageLedger,
        router: CloudflareFreeTierRouter,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.ledger = ledger
        self.router = router
        self.now = now or (lambda: datetime.now(timezone.utc))

    def quota_day(self) -> date:
        current = self.now()
        if current.tzinfo is None or current.utcoffset() is None:
            raise RuntimeError("CLOUDFLARE_QUOTA_CLOCK_MUST_BE_TIMEZONE_AWARE")
        return current.astimezone(timezone.utc).date()

    def reserve(
        self,
        *,
        operation_id: str,
        work_class: CloudflareWorkClass,
        estimate: CloudflareFreeEstimate,
        day: date | None = None,
    ) -> CloudflareFreePlan:
        trusted_day = self.quota_day()
        if day is not None and day != trusted_day:
            raise AuthorityViolation("CLOUDFLARE_QUOTA_DAY_UNTRUSTED")
        usage = self.ledger.snapshot(day=trusted_day)
        route = self.router.route(work_class, estimate, usage=usage)
        reservation = self.ledger.reserve(
            operation_id, work_class.value, estimate, day=trusted_day
        )
        return CloudflareFreePlan(route=route, reservation=reservation)
