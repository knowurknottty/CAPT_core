"""Read-only capability/lease projections for operator surfaces (CAPT-UPG-015).

Capability authority remains entirely in CapabilityAggregate/RuntimeService.
These helpers only shape authoritative aggregate snapshots for display.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


def project_capability_lease(state: Mapping[str, Any], now: Optional[str] = None) -> Dict[str, Any]:
    lease = state.get("lease") or {}
    grant_max = state.get("maxUses")
    lease_max = lease.get("maxUses")
    effective_max = lease_max if lease_max is not None else grant_max
    consumed = int(state.get("usesConsumed") or 0)
    remaining = None if effective_max is None else max(0, int(effective_max) - consumed)
    reservations = list(state.get("reservations") or [])
    open_reservations = [r for r in reservations if r.get("state") == "open"]
    reconciliation = [r for r in reservations if r.get("state") == "awaiting_reconciliation"]
    valid_from = lease.get("validFrom") or state.get("validFrom")
    valid_until = lease.get("validUntil") or state.get("validUntil")
    temporal = "unknown"
    if now and valid_from and valid_until:
        if now < valid_from:
            temporal = "not_yet_valid"
        elif now > valid_until:
            temporal = "expired_by_clock"
        else:
            temporal = "within_validity_window"
    revocation = state.get("revocation")
    return {
        "grantId": state.get("grantId"),
        "capabilityId": state.get("capabilityId"),
        "subjectActorId": state.get("subjectActorId"),
        "grantState": state.get("grantState"),
        "grantOperations": list(state.get("operations") or []),
        "grantScope": state.get("scope"),
        "leaseId": lease.get("leaseId"),
        "leaseState": lease.get("state") or "absent",
        "missionId": lease.get("missionId"),
        "taskId": lease.get("taskId"),
        "executionContextId": lease.get("executionContextId"),
        "leaseOperations": list(lease.get("operations") or []),
        "leaseScope": lease.get("scope"),
        "validFrom": valid_from,
        "validUntil": valid_until,
        "temporalProjection": temporal,
        "maxUses": effective_max,
        "usesConsumed": consumed,
        "remainingUses": remaining,
        "openReservations": open_reservations,
        "reconciliationRequiredReservations": reconciliation,
        "consumptionCount": len(state.get("consumptions") or []),
        "revoked": revocation is not None,
        "revocation": revocation,
        "authority": "projection_only",
    }


def project_capability_leases(states: Iterable[Mapping[str, Any]], now: Optional[str] = None) -> List[Dict[str, Any]]:
    return [project_capability_lease(state, now=now) for state in states]


def render_capability_leases(rows: Iterable[Mapping[str, Any]]) -> str:
    rows = list(rows)
    if not rows:
        return "Capability leases\n-----------------\n<none>"
    lines = ["Capability leases (authoritative-state projection)", "-----------------------------------------------"]
    for row in rows:
        remaining = "unbounded" if row.get("remainingUses") is None else str(row.get("remainingUses"))
        lease_id = row.get("leaseId") or "<no lease>"
        lines.append(
            "%s | grant=%s/%s | lease=%s | uses=%s/%s | open=%d | reconcile=%d" % (
                row.get("grantId") or "?",
                row.get("grantState") or "?",
                row.get("capabilityId") or "?",
                "%s:%s" % (lease_id, row.get("leaseState") or "?"),
                row.get("usesConsumed") or 0,
                remaining,
                len(row.get("openReservations") or []),
                len(row.get("reconciliationRequiredReservations") or []),
            )
        )
        if row.get("revoked"):
            rev = row.get("revocation") or {}
            lines.append("  REVOKED: %s" % (rev.get("reason") or "reason unavailable"))
        if row.get("leaseScope"):
            lines.append("  scope=%s" % row.get("leaseScope"))
    return "\n".join(lines)
