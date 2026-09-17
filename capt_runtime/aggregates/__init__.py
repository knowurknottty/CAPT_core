"""CAPT runtime aggregates with exclusive state ownership (ADR-0103)."""

from .artifact_promotion import ArtifactPromotionAggregate
from .bot import BotAggregate
from .capability import CapabilityAggregate, scope_contains
from .claim_driver import ClaimAggregate, DriverRunAggregate
from .cloudflare_resource_binding import CloudflareResourceBindingAggregate
from .cognitive_candidate import CognitiveCandidateAggregate
from .cohort_state import CohortAggregate
from .delegate_assignment import DelegateAssignmentAggregate
from .human_approval import HumanApprovalAggregate
from .lab_board import LabBoardAggregate
from .mission_task import MissionAggregate, TaskAggregate
from .replay_fork import ReplayForkAggregate
from .sandbox_lease import SandboxLeaseAggregate
from .skill_candidate import SkillCandidateAggregate
from .tool_execution import ToolExecutionAggregate

ALL_AGGREGATES = (
    MissionAggregate,
    TaskAggregate,
    CapabilityAggregate,
    DriverRunAggregate,
    ClaimAggregate,
    BotAggregate,
    CognitiveCandidateAggregate,
    CloudflareResourceBindingAggregate,
    DelegateAssignmentAggregate,
    SkillCandidateAggregate,
    LabBoardAggregate,
    CohortAggregate,
    ReplayForkAggregate,
    HumanApprovalAggregate,
    ArtifactPromotionAggregate,
    ToolExecutionAggregate,
    SandboxLeaseAggregate,
)

__all__ = [
    "ALL_AGGREGATES",
    "ArtifactPromotionAggregate",
    "BotAggregate",
    "CapabilityAggregate",
    "ClaimAggregate",
    "CognitiveCandidateAggregate",
    "CloudflareResourceBindingAggregate",
    "DelegateAssignmentAggregate",
    "CohortAggregate",
    "LabBoardAggregate",
    "ReplayForkAggregate",
    "SkillCandidateAggregate",
    "DriverRunAggregate",
    "HumanApprovalAggregate",
    "MissionAggregate",
    "TaskAggregate",
    "ToolExecutionAggregate",
    "SandboxLeaseAggregate",
    "scope_contains",
]
