"""CAPT runtime aggregates with exclusive state ownership (ADR-0103)."""

from .capability import CapabilityAggregate, scope_contains
from .claim_driver import ClaimAggregate, DriverRunAggregate
from .human_approval import HumanApprovalAggregate
from .mission_task import MissionAggregate, TaskAggregate

ALL_AGGREGATES = (
    MissionAggregate,
    TaskAggregate,
    CapabilityAggregate,
    DriverRunAggregate,
    ClaimAggregate,
    HumanApprovalAggregate,
)

__all__ = [
    "ALL_AGGREGATES",
    "CapabilityAggregate",
    "ClaimAggregate",
    "DriverRunAggregate",
    "HumanApprovalAggregate",
    "MissionAggregate",
    "TaskAggregate",
    "scope_contains",
]
