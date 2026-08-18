"""CAPT runtime aggregates with exclusive state ownership (ADR-0103)."""

from .artifact_promotion import ArtifactPromotionAggregate
from .capability import CapabilityAggregate, scope_contains
from .claim_driver import ClaimAggregate, DriverRunAggregate
from .cohort_state import CohortAggregate
from .human_approval import HumanApprovalAggregate
from .mission_task import MissionAggregate, TaskAggregate
from .replay_fork import ReplayForkAggregate

ALL_AGGREGATES = (
    MissionAggregate,
    TaskAggregate,
    CapabilityAggregate,
    DriverRunAggregate,
    ClaimAggregate,
    HumanApprovalAggregate,
    ArtifactPromotionAggregate,
    CohortAggregate,
    ReplayForkAggregate,
)

__all__ = [
    "ALL_AGGREGATES",
    "ArtifactPromotionAggregate",
    "CapabilityAggregate",
    "ClaimAggregate",
    "CohortAggregate",
    "DriverRunAggregate",
    "HumanApprovalAggregate",
    "MissionAggregate",
    "ReplayForkAggregate",
    "TaskAggregate",
    "scope_contains",
]
