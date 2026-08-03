"""ExecutionDriver interface (M0-B, ADR-0120).

The driver is an UNTRUSTED external process. It receives a narrow
`ExecutionDriverWorkOrder` + `ContextSlice` and returns untrusted outputs. It
never receives GovernanceKernel, PolicyEngine, ClaimGuard, CapabilityAggregate,
EventLedger, or any aggregate-mutation authority.

This module defines the structural trust boundary. The Protocol is the contract
surface; the concrete adapter (openharness.py) is the only place an external
process is contacted.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from ..contracts import require


@runtime_checkable
class ExecutionDriver(Protocol):
    """Narrow, untrusted-external-driver contract.

    The driver describes itself, and (when invoked) submits/inspects/cancels/
    resumes/reconciles a run. It reports untrusted observations; CAPT decides
    everything authoritative.
    """

    def describe(self) -> Dict[str, Any]:
        """Return an ExecutionDriverDescriptor (driver-authored, untrusted identity)."""
        ...

    async def submit(self, work_order: Dict[str, Any]) -> Dict[str, Any]:
        """Begin a run. Returns a handle with externalRunId (untrusted)."""
        ...

    async def inspect(self, run_id: str) -> Dict[str, Any]:
        """Return current DriverRunState (untrusted driver view)."""
        ...

    async def cancel(self, run_id: str, reason: str) -> None:
        """Request cancellation. CAPT owns the authoritative terminal state."""
        ...

    async def resume(
        self, run_id: str, resume_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Resume a suspended run. CAPT-authored input only."""
        ...

    async def reconcile(self, run_id: str) -> Dict[str, Any]:
        """Return a DriverReconciliationResult-shaped view (untrusted)."""
        ...


def validate_work_order(work_order: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a work order against the generated contract before dispatch."""
    return require("ExecutionDriverWorkOrder", work_order)


def validate_descriptor(descriptor: Dict[str, Any]) -> Dict[str, Any]:
    return require("ExecutionDriverDescriptor", descriptor)
