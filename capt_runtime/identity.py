"""Identity & Authority Plane (ADR-DT-PLANE-CONV).

Thin validation and authority-chain enforcement. This module does NOT own
governance policy or capability issuance — those live in ``authority.py`` and
``capability.py``. It separates:

  authentication      -> is this principal attestation valid?
  identity proof      -> does the attestation match the claimed principal?
  delegation          -> is the delegation bounded and non-widening?
  authorization       -> does the principal hold a capability for the act?
  governance          -> does policy permit the act for this actor kind?
  capability issuance -> (delegated to capability.py)

A session token alone must never become unrestricted authority.

The driver-identity discipline is reused from the existing
``DriverRegistry.SpoofedDriverIdentity`` guard and ``hermes.probe_hermes_identity``
executable probe.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import require
from .errors import AuthorityViolation


def validate_principal(principal: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a Principal contract (identity establishment)."""
    return require("Principal", principal)


def validate_session(session: Dict[str, Any], now_iso: str) -> Dict[str, Any]:
    """Validate a SessionIdentity and reject expired sessions.

    A session token is NOT unrestricted authority: it only binds a principal
    to a time box. Authority still requires a capability grant.
    """
    s = require("SessionIdentity", session)
    if s["expiresAt"] <= now_iso:
        raise AuthorityViolation("session %s is expired" % s["sessionId"])
    return s


def validate_delegation(delegation: Dict[str, Any], delegator_scope: str) -> Dict[str, Any]:
    """Validate a Delegation and reject authority widening.

    A delegate may receive a NARROWER scope than the delegator holds, never a
    wider one.
    """
    d = require("Delegation", delegation)
    if _scope_broader(d["scope"], delegator_scope):
        raise AuthorityViolation(
            "delegation %s widens delegator scope %r -> %r"
            % (d["delegationId"], delegator_scope, d["scope"])
        )
    return d


def validate_revocation(revocation: Dict[str, Any]) -> Dict[str, Any]:
    return require("RevocationRecord", revocation)


def is_revoked(target_id: str, revocations: List[Dict[str, Any]]) -> bool:
    """Return True if the target principal/delegation/session is revoked."""
    return any(r.get("targetId") == target_id for r in revocations)


def verify_authority_chain(
    chain: Dict[str, Any],
    root_principal_id: str,
    revocations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Verify an AuthorityChain is unbroken and free of revocation.

    Each entry must delegate from the previous entry's delegate to the next
    delegate, starting at the root principal. Any revoked link fails.
    """
    c = require("AuthorityChain", chain)
    entries: List[Dict[str, Any]] = c["entries"]
    if not entries:
        raise AuthorityViolation("empty authority chain")
    expected_delegator = root_principal_id
    for i, entry in enumerate(entries):
        if entry["delegatorId"] != expected_delegator:
            raise AuthorityViolation(
                "chain link %d delegator %r != expected %r"
                % (i, entry["delegatorId"], expected_delegator)
            )
        if is_revoked(entry["delegationId"], revocations) or is_revoked(
            entry["delegateId"], revocations
        ):
            raise AuthorityViolation("chain link %d is revoked" % i)
        expected_delegator = entry["delegateId"]
    return c


def _scope_broader(candidate: str, baseline: str) -> bool:
    """Heuristic scope comparison: a candidate is broader if it is not a
    sub-scope of the baseline. Exact-match or more-specific is allowed."""
    if candidate == baseline:
        return False
    # A narrower scope is a strict prefix path of the baseline (e.g. "a.b" within "a.b.c").
    return not baseline.startswith(candidate)
