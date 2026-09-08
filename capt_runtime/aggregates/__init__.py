"""CAPT runtime aggregates with exclusive state ownership (ADR-0103)."""

from .artifact_promotion import ArtifactPromotionAggregate
from .bot import BotAggregate
from .capability import CapabilityAggregate, scope_contains
from .claim_driver import ClaimAggregate, DriverRunAggregate
from .cognitive_candidate import CognitiveCandidateAggregate
from .cohort_state import CohortAggregate
from .lab_board import LabBoardAggregate
from .skill_candidate import SkillCandidateAggregate
from .replay_fork import ReplayForkAggregate
from .human_approval import HumanApprovalAggregate
from .mission_task import MissionAggregate, TaskAggregate
from .tool_execution import ToolExecutionAggregate

ALL_AGGREGATES = (
    MissionAggregate,
    TaskAggregate,
    CapabilityAggregate,
    DriverRunAggregate,
    ClaimAggregate,
    BotAggregate,
    CognitiveCandidateAggregate,
    SkillCandidateAggregate,
    LabBoardAggregate,
    CohortAggregate,
    ReplayForkAggregate,
    HumanApprovalAggregate,
    ArtifactPromotionAggregate,
    ToolExecutionAggregate,
)

__all__ = [
    "ALL_AGGREGATES",
    "ArtifactPromotionAggregate",
    "BotAggregate",
    "CapabilityAggregate",
    "ClaimAggregate",
    "CognitiveCandidateAggregate",
    "CohortAggregate",
    "LabBoardAggregate",
    "ReplayForkAggregate",
    "SkillCandidateAggregate",
    "DriverRunAggregate",
    "HumanApprovalAggregate",
    "MissionAggregate",
    "TaskAggregate",
    "ToolExecutionAggregate",
    "scope_contains",
]
