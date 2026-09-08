"""CAPT-owned reservation planner for free-tier-native Cloudflare work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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
    def __init__(self, ledger: CloudflareUsageLedger, router: CloudflareFreeTierRouter) -> None:
        self.ledger = ledger
        self.router = router

    def reserve(
        self,
        *,
        operation_id: str,
        work_class: CloudflareWorkClass,
        estimate: CloudflareFreeEstimate,
        day: date,
    ) -> CloudflareFreePlan:
        usage = self.ledger.snapshot(day=day)
        route = self.router.route(work_class, estimate, usage=usage)
        reservation = self.ledger.reserve(operation_id, work_class.value, estimate, day=day)
        return CloudflareFreePlan(route=route, reservation=reservation)
