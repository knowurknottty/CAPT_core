"""Typed errors for the CAPT runtime.

Each maps to an ErrorEnvelope category in the contract set. Distinct classes
exist so tests can assert the *reason* a write was refused, not merely that
it was refused.
"""

from __future__ import annotations

from typing import List, Optional


class CaptRuntimeError(Exception):
    """Base class. Carries the contract error category."""

    category = "internal"


class ContractViolation(CaptRuntimeError):
    """A payload failed generated-contract validation."""

    category = "validation"

    def __init__(self, type_name: str, errors: List[str]) -> None:
        CaptRuntimeError.__init__(self, "%s: %s" % (type_name, "; ".join(errors)))
        self.type_name = type_name
        self.errors = errors


class AuthorityViolation(CaptRuntimeError):
    """An actor attempted an action reserved to another authority plane."""

    category = "authority"


class ConcurrencyConflict(CaptRuntimeError):
    """Expected aggregate version did not match the stored version."""

    category = "concurrency"

    def __init__(self, stream_id: str, expected: int, actual: int) -> None:
        CaptRuntimeError.__init__(
            self,
            "stale write to %s: expected version %d, actual %d"
            % (stream_id, expected, actual),
        )
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual


class IdempotencyConflict(CaptRuntimeError):
    """An idempotency key was reused with a different operation fingerprint."""

    category = "idempotency"


class IntegrityViolation(CaptRuntimeError):
    """A digest check failed: ledger, payload, or checkpoint."""

    category = "integrity"


class NotFound(CaptRuntimeError):
    category = "not_found"


class IllegalTransition(CaptRuntimeError):
    """A state machine rejected a transition."""

    category = "illegal_transition"

    def __init__(self, subject: str, from_state: str, to_state: str) -> None:
        CaptRuntimeError.__init__(
            self, "%s cannot transition %s -> %s" % (subject, from_state, to_state)
        )
        self.subject = subject
        self.from_state = from_state
        self.to_state = to_state


class CapabilityDenied(CaptRuntimeError):
    """A lease check failed at the consequential boundary."""

    category = "capability_denied"

    def __init__(self, reason: str, lease_id: Optional[str] = None) -> None:
        CaptRuntimeError.__init__(self, reason)
        self.reason = reason
        self.lease_id = lease_id


class CapabilityViolation(CaptRuntimeError):
    """A read-only capability-model invariant was violated (M0-B)."""

    category = "capability_violation"

    def __init__(self, reason: str) -> None:
        CaptRuntimeError.__init__(self, reason)
        self.reason = reason



class ReconciliationRequired(CaptRuntimeError):
    """An indeterminate operation must be resolved before proceeding."""

    category = "reconciliation_required"


class ConcurrencyError(RuntimeError):
    """Optimistic-concurrency failure: expected aggregate version != actual."""


class IdempotencyError(RuntimeError):
    """A command was replayed with a conflicting fingerprint."""
