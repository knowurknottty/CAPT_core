"""Typed ToolBroker participation for persistent InversionSandbox lifecycle tools."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from capt_runtime.contracts import require


@dataclass(frozen=True)
class CapabilityLeaseBoundary:
    lease_id: str
    execution_context_id: str
    valid_until: str


@dataclass(frozen=True)
class SandboxLeaseReservation:
    sandbox_lease_id: str
    lease: dict[str, Any]

    def __post_init__(self) -> None:
        require("SandboxLease", self.lease)
        if self.lease["sandboxLeaseId"] != self.sandbox_lease_id:
            raise ValueError("sandbox reservation id disagrees with lease record")


@dataclass(frozen=True)
class SandboxCloseBegin:
    sandbox_lease_id: str
    patch: dict[str, Any]
    already_closed: bool = False


@dataclass(frozen=True)
class SandboxTerminalPatch:
    sandbox_lease_id: str
    patch: dict[str, Any]


@runtime_checkable
class SandboxBrokerHooks(Protocol):
    def validate_sandbox_context(
        self, request: dict[str, Any], *, operator_id: str, session_id: str
    ) -> None: ...

    def reserve_sandbox_lease_record(
        self,
        request: dict[str, Any],
        *,
        execution_id: str,
        operator_id: str,
        session_id: str,
        capability: CapabilityLeaseBoundary,
        now: str,
    ) -> SandboxLeaseReservation | None: ...

    def begin_sandbox_close_patch(
        self,
        request: dict[str, Any],
        *,
        operator_id: str,
        session_id: str,
    ) -> SandboxCloseBegin | None: ...

    def sandbox_created_patch(
        self, request: dict[str, Any], side_effect_identity: str
    ) -> SandboxTerminalPatch | None: ...

    def sandbox_terminal_patch(
        self, request: dict[str, Any], result: dict[str, Any], *, now: str
    ) -> SandboxTerminalPatch | None: ...


@runtime_checkable
class PersistentSandboxExecHooks(Protocol):
    def validate_persistent_exec_context(
        self, request: dict[str, Any], *, operator_id: str, session_id: str
    ) -> None: ...

    def persistent_exec_terminal_patch(
        self, request: dict[str, Any], result: dict[str, Any], *, now: str
    ) -> SandboxTerminalPatch | None: ...
