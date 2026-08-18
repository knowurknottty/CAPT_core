"""Capability revocation hardening for CAPT-UPG-015.

This is the next composition-owned RuntimeService refinement. It does not add
an authority plane; it fail-closes target binding before delegating to the
existing authoritative RuntimeService.revoke() transition.
"""
from __future__ import annotations

from typing import Any, Dict

from .aggregates.capability import CapabilityAggregate
from .errors import AuthorityViolation
from .steered_service import SteeredRuntimeService


class LeaseRuntimeService(SteeredRuntimeService):
    """Canonical service with exact grant/lease revocation target binding."""

    def revoke(
        self, grant_id: str, revocation: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        stream = CapabilityAggregate.stream_id(grant_id)
        current = self.store.require_state(stream)
        target_kind = revocation.get("targetKind")
        target_id = revocation.get("targetId")

        if target_kind == "grant":
            if target_id != grant_id:
                raise AuthorityViolation(
                    "revocation targetId %r does not match grant %r" % (target_id, grant_id)
                )
        elif target_kind == "lease":
            lease = current.get("lease")
            if lease is None:
                raise AuthorityViolation("cannot revoke lease: grant has no active lease record")
            if target_id != lease.get("leaseId"):
                raise AuthorityViolation(
                    "revocation targetId %r does not match active lease %r"
                    % (target_id, lease.get("leaseId"))
                )
        else:
            # Schema validation in super() also rejects this; keeping the
            # semantic boundary explicit makes malformed callers fail closed.
            raise AuthorityViolation("unknown revocation target kind %r" % target_kind)

        return super().revoke(grant_id, revocation, metadata)
