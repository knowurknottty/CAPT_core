"""Authority planes and the structural separation between them.

Spec invariants 1-5 require that governance, cognition, execution,
verification, and claim authority remain distinct. Encoding the rules here —
rather than as review guidance — is what makes them testable.
"""

from __future__ import annotations

from typing import Dict, FrozenSet

from .errors import AuthorityViolation

GOVERNANCE = "governance_kernel"
COGNITION = "cognitive_plane"
EXECUTION = "execution_plane"
VERIFICATION = "verification_plane"
CLAIM_AUTHORITY = "claim_authority"
HUMAN = "human"
SYSTEM = "system"
EXTERNAL_DRIVER = "external_driver"

# Which actor kinds may author which authoritative act. Deny by default:
# an act not listed here has no permitted author at all.
_PERMITTED: Dict[str, FrozenSet[str]] = {
    "evaluate_policy": frozenset({GOVERNANCE}),
    "issue_grant": frozenset({GOVERNANCE}),
    "revoke": frozenset({GOVERNANCE, HUMAN}),
    "activate_lease": frozenset({GOVERNANCE}),
    "reserve_use": frozenset({EXECUTION}),
    "finalize_use": frozenset({EXECUTION}),
    "prepare_tool_execution": frozenset({EXECUTION, SYSTEM}),
    "transition_tool_execution": frozenset({EXECUTION, SYSTEM}),
    "reserve_sandbox_lease": frozenset({EXECUTION, SYSTEM}),
    "transition_sandbox_lease": frozenset({EXECUTION, SYSTEM}),
    "create_mission": frozenset({HUMAN, SYSTEM}),
    # Mission and driver-run lifecycle were previously UNGATED: the service
    # methods validated CommandMetadata but called require_authority() for no
    # act, so any authenticated actor could move a mission or a driver run.
    # Permitted kinds are DERIVED from actual call sites, not invented:
    #   create_driver_run / transition_driver_run -> execution_plane at every
    #     production and recovery call site (SYSTEM covers reconcile paths)
    #   transition_mission -> no production caller at all; the only caller is a
    #     test using actor_kind="human" (SYSTEM covers lifecycle advancement)
    # Review these three if a governance/cognition caller is ever added.
    "transition_mission": frozenset({HUMAN, SYSTEM}),
    "create_driver_run": frozenset({EXECUTION, SYSTEM}),
    # HUMAN is required here even though every DIRECT caller is execution_plane:
    # cancel_driver_run permits {EXECUTION, HUMAN, SYSTEM} and DELEGATES to this
    # act to write the 'cancelled' transition, and the M1 operator surface issues
    # commands as actor_kind="human". An internal transition reachable from a
    # public act must permit at least the union of its callers' permitted kinds,
    # or the operator-facing cancel is refused one layer down.
    "transition_driver_run": frozenset({EXECUTION, HUMAN, SYSTEM}),
    "record_driver_dispatch_boundary": frozenset({EXECUTION, SYSTEM}),
    "plan_tasks": frozenset({COGNITION, SYSTEM}),
    "transition_task": frozenset({EXECUTION, SYSTEM}),
    "submit_result": frozenset({EXECUTION, SYSTEM}),
    "request_human_approval": frozenset({EXECUTION, GOVERNANCE, SYSTEM}),
    "submit_human_approval_decision": frozenset({HUMAN}),
    "submit_human_claim_review": frozenset({HUMAN}),
    "consume_human_approval": frozenset({EXECUTION, SYSTEM}),
    "cancel_task": frozenset({EXECUTION, HUMAN, SYSTEM}),
    "cancel_driver_run": frozenset({EXECUTION, HUMAN, SYSTEM}),
    "record_evidence": frozenset({VERIFICATION, EXECUTION, SYSTEM}),
    "produce_verification": frozenset({VERIFICATION}),
    "propose_claim": frozenset({COGNITION, EXECUTION, SYSTEM}),
    "decide_claim": frozenset({CLAIM_AUTHORITY}),
    "create_checkpoint": frozenset({SYSTEM}),
    # Verification/ClaimGuard do not own filesystem adoption. A bounded
    # promotion transaction separates preparation, human/governance
    # authorization, and the consequential atomic filesystem step.
    "prepare_artifact_promotion": frozenset({EXECUTION, SYSTEM}),
    "authorize_artifact_promotion": frozenset({HUMAN, GOVERNANCE, SYSTEM}),
    "adopt_artifact_promotion": frozenset({EXECUTION, SYSTEM}),
    "discard_artifact_promotion": frozenset({EXECUTION, HUMAN, SYSTEM}),
    "persist_cohort": frozenset({COGNITION, SYSTEM}),
    "admit_council_plan": frozenset({SYSTEM}),
    "record_council_analysis": frozenset({COGNITION, SYSTEM}),
    "steer_cohort": frozenset({HUMAN}),
    "create_replay_fork": frozenset({HUMAN}),
    "register_bot": frozenset({HUMAN, SYSTEM}),
    "propose_cognitive_candidate": frozenset({COGNITION, SYSTEM}),
    "decide_cognitive_candidate": frozenset({HUMAN, GOVERNANCE}),
    "create_skill_candidate": frozenset({COGNITION, HUMAN, SYSTEM}),
    "transition_skill_candidate": frozenset({COGNITION, HUMAN, GOVERNANCE, SYSTEM}),
    "create_lab_board_item": frozenset({COGNITION, EXECUTION, HUMAN, SYSTEM}),
    "transition_lab_board_item": frozenset({COGNITION, EXECUTION, HUMAN, GOVERNANCE, SYSTEM}),
    "assign_delegate": frozenset({COGNITION, HUMAN, SYSTEM}),
    "transition_delegate_assignment": frozenset({COGNITION, HUMAN, GOVERNANCE, SYSTEM}),
    "bind_cloudflare_resource_adoption": frozenset({EXECUTION, SYSTEM}),
}


def permitted_actors(act: str) -> FrozenSet[str]:
    return _PERMITTED.get(act, frozenset())


def require_authority(act: str, actor_kind: str) -> None:
    """Raise AuthorityViolation unless actor_kind may perform act."""
    allowed = _PERMITTED.get(act)
    if allowed is None:
        raise AuthorityViolation(
            "unknown authoritative act %r; no actor may perform it" % act
        )
    if actor_kind not in allowed:
        raise AuthorityViolation(
            "actor kind %r may not perform %r (permitted: %s)"
            % (actor_kind, act, ", ".join(sorted(allowed)))
        )


def known_acts() -> FrozenSet[str]:
    return frozenset(_PERMITTED)
