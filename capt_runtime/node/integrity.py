"""Specific CAPT Node integrity failures; no generic error channel."""

from __future__ import annotations


class NodeIntegrityViolation(RuntimeError):
    """Base class for a typed CAPT Node integrity failure."""

    def __init__(self, code: str, *, operation_id: str | None = None) -> None:
        if not code or code in {"error", "unknown", "generic"}:
            raise ValueError("integrity violation requires a specific code")
        self.code = code
        self.operation_id = operation_id
        suffix = f" operation={operation_id}" if operation_id else ""
        super().__init__(f"{code}{suffix}")


class OperationDigestMismatch(NodeIntegrityViolation):
    """An operation ID was reused with different request content."""


class GenericStateViolation(NodeIntegrityViolation):
    """A semantically generic state attempted to enter the Node ledger."""
