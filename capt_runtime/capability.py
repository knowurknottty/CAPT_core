"""Read-only capability model for M0-B driver dispatch (ADR-0122).

CAPT owns all capability authority. A driver holds NO authority: it is granted a
scoped, time-boxed *lease* that enumerates exactly which read-only operations it
may perform, over which paths, within which budget. Before any driver call that
could cross an external boundary, CAPT re-validates the lease.

This module encodes the allow/deny lists and the pre-dispatch verification that
the mission requires. It is deliberately small and side-effect free so it can be
exercised exhaustively by tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .errors import CapabilityViolation

# Operations a read-only M0-B driver MAY be granted.
ALLOWED_OPERATIONS = frozenset(
    {
        "repository.read",
        "filesystem.read",
        "artifact.create",
        "analysis.execute",
    }
)

# Operations a read-only M0-B driver MUST NEVER be granted.
DENIED_OPERATIONS = frozenset(
    {
        "repository.write",
        "filesystem.write",
        "git.commit",
        "git.push",
        "process.mutate",
        "package.install",
        "deployment",
        "credential.use",
        "network.access",
    }
)

# The contract-level work-order operation vocabulary (camelCase, see
# ExecutionDriverWorkOrder.operations) maps onto the capability-model vocabulary
# used by leases. CAPT translates at the trust boundary so the lease check stays
# in one canonical vocabulary.
_OPERATION_ALIASES = {
    "RepositoryRead": "repository.read",
    "FilesystemRead": "filesystem.read",
    "ArtifactCreate": "artifact.create",
    "AnalysisOnly": "analysis.execute",
    "RepositoryWrite": "repository.write",
    "FilesystemWrite": "filesystem.write",
    "GitCommit": "git.commit",
    "GitPush": "git.push",
}


def canonical_operation(op: str) -> str:
    """Map a contract-level operation name to the capability-model vocabulary."""
    return _OPERATION_ALIASES.get(op, op)


def is_allowed_operation(op: str) -> bool:
    return op in ALLOWED_OPERATIONS


def is_denied_operation(op: str) -> bool:
    return op in DENIED_OPERATIONS


def verify_lease(
    lease: Dict[str, Any],
    *,
    now: str,
    driver_id: str,
    mission_id: str,
    task_id: str,
    operations: List[str],
    resource_path: Optional[str] = None,
    budget: Optional[Dict[str, Any]] = None,
) -> None:
    """Re-validate a capability lease immediately before an external driver call.

    Raises CapabilityViolation on any gap. Pure / no side effects.
    """
    if not lease:
        raise CapabilityViolation("no capability lease supplied")

    # 1. Identity must match the work order.
    if lease.get("driverId") and lease["driverId"] != driver_id:
        raise CapabilityViolation(
            "lease driverId %r does not match work order driver %r"
            % (lease.get("driverId"), driver_id)
        )

    # 2. Mission / task scope must match.
    if lease.get("missionId") and lease["missionId"] != mission_id:
        raise CapabilityViolation("lease mission mismatch")
    if lease.get("taskId") and lease["taskId"] != task_id:
        raise CapabilityViolation("lease task mismatch")

    # 3. Lease must be active (not revoked, not expired, not pending).
    status = lease.get("status", "active")
    if status != "active":
        raise CapabilityViolation("lease is not active (status=%s)" % status)
    if lease.get("revoked"):
        raise CapabilityViolation("lease has been revoked")

    valid_from = lease.get("validFrom")
    valid_until = lease.get("validUntil")
    if valid_from and now < valid_from:
        raise CapabilityViolation("lease not yet valid")
    if valid_until and now > valid_until:
        raise CapabilityViolation("lease expired")

    # 4. Every requested operation must be in the allowed set and granted.
    # Canonicalize contract-level op names (RepositoryRead -> repository.read) so
    # the lease vocabulary is the single source of truth.
    granted = {canonical_operation(o) for o in lease.get("operations", [])}
    for raw_op in operations:
        op = canonical_operation(raw_op)
        if op in DENIED_OPERATIONS:
            raise CapabilityViolation("operation %r is denied for M0-B" % raw_op)
        if op not in ALLOWED_OPERATIONS:
            raise CapabilityViolation("operation %r is not a known read-only op" % raw_op)
        if op not in granted:
            raise CapabilityViolation(
                "operation %r not covered by lease" % raw_op
            )

    # 5. Resource / path scope must match.
    scope = lease.get("scope")
    if resource_path is not None:
        if scope is None:
            raise CapabilityViolation("lease has no scope for path check")
        allowed_paths = scope.get("allowedPaths", [])
        if not any(resource_path == p or resource_path.startswith(p + "/") for p in allowed_paths):
            raise CapabilityViolation(
                "path %r outside lease scope %s" % (resource_path, allowed_paths)
            )

    # 6. Budget validity.
    if budget is not None:
        lease_budget = lease.get("budget")
        if lease_budget is None:
            raise CapabilityViolation("lease carries no budget but one was required")
        if budget.get("maxSeconds", 0) > lease_budget.get("maxSeconds", 0):
            raise CapabilityViolation("requested budget exceeds lease budget")


def check_work_order_operations(operations: List[str]) -> None:
    """Reject structurally unsafe operations before dispatch.

    The work order uses contract-level op names (RepositoryWrite, GitCommit, ...).
    These map to denied capability-model ops and are rejected regardless of any
    lease claim (they are structurally unsafe for M0-B).
    """
    bad = [op for op in operations if canonical_operation(op) in DENIED_OPERATIONS]
    if bad:
        raise CapabilityViolation(
            "work order contains write/git operations rejected before dispatch: %s"
            % ", ".join(bad)
        )
