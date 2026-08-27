"""CAPT runtime aggregates with exclusive state ownership (ADR-0103)."""

from .artifact_promotion import ArtifactPromotionAggregate
from .capability import CapabilityAggregate, scope_contains
from .claim_driver import ClaimAggregate, DriverRunAggregate
from .cohort_state import CohortAggregate
from .replay_fork import ReplayForkAggregate
from .human_approval import HumanApprovalAggregate
from .mission_task import MissionAggregate, TaskAggregate
from .prompt_proposal import PromptProposalAggregate
from .tool_execution import ToolExecutionAggregate

ALL_AGGREGATES = (
    MissionAggregate,
    TaskAggregate,
    CapabilityAggregate,
    DriverRunAggregate,
    ClaimAggregate,
    CohortAggregate,
    ReplayForkAggregate,
    HumanApprovalAggregate,
    PromptProposalAggregate,
    ArtifactPromotionAggregate,
    ToolExecutionAggregate,
)

__all__ = [
    "ALL_AGGREGATES",
    "ArtifactPromotionAggregate",
    "CapabilityAggregate",
    "ClaimAggregate",
    "CohortAggregate",
    "ReplayForkAggregate",
    "DriverRunAggregate",
    "HumanApprovalAggregate",
    "MissionAggregate",
    "PromptProposalAggregate",
    "TaskAggregate",
    "ToolExecutionAggregate",
    "scope_contains",
]
