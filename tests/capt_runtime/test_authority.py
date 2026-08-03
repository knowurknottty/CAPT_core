"""Conformance tests: authority plane separation (spec invariants 1-5)."""

from __future__ import annotations

import pytest

from capt_runtime import authority
from capt_runtime.errors import AuthorityViolation


def test_plane_separation():
    """I3: each act is permitted for exactly the intended plane."""
    # Governance may issue grants and evaluate policy.
    authority.require_authority("issue_grant", "governance_kernel")
    authority.require_authority("evaluate_policy", "governance_kernel")
    # Execution may transition tasks but NOT issue grants.
    authority.require_authority("transition_task", "execution_plane")
    # Cognition may plan tasks but NOT decide claims.
    authority.require_authority("plan_tasks", "cognitive_plane")
    # Verification may produce verification but NOT decide claims.
    authority.require_authority("produce_verification", "verification_plane")
    # Claim authority may decide claims but NOT issue grants.
    authority.require_authority("decide_claim", "claim_authority")


def test_cognition_cannot_issue_grant():
    with pytest.raises(AuthorityViolation):
        authority.require_authority("issue_grant", "cognitive_plane")


def test_execution_cannot_bypass_governance():
    with pytest.raises(AuthorityViolation):
        authority.require_authority("evaluate_policy", "execution_plane")


def test_verification_cannot_mutate_execution():
    with pytest.raises(AuthorityViolation):
        authority.require_authority("transition_task", "verification_plane")


def test_claimguard_cannot_fabricate_verification():
    with pytest.raises(AuthorityViolation):
        authority.require_authority("produce_verification", "claim_authority")


def test_unknown_actor_denied():
    with pytest.raises(AuthorityViolation):
        authority.require_authority("issue_grant", "rogue_plane")
