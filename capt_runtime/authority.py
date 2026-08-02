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
    "create_mission": frozenset({HUMAN, SYSTEM}),
    "plan_tasks": frozenset({COGNITION, SYSTEM}),
    "transition_task": frozenset({EXECUTION, SYSTEM}),
    "record_evidence": frozenset({VERIFICATION, EXECUTION, SYSTEM}),
    "produce_verification": frozenset({VERIFICATION}),
    "propose_claim": frozenset({COGNITION, EXECUTION, SYSTEM}),
    "decide_claim": frozenset({CLAIM_AUTHORITY}),
    "create_checkpoint": frozenset({SYSTEM}),
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
