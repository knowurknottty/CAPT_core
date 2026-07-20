"""CAPT Solo error hierarchy.

All public operations raise subclasses of :class:`CaptSoloError` so callers
can catch failures predictably. Implementation-specific exceptions are kept
internal and wrapped into these public types at the API boundary.
"""

from __future__ import annotations


class CaptSoloError(Exception):
    """Base class for all CAPT Solo errors."""


class MemoryError_(CaptSoloError):  # noqa: N801 - avoid clash with builtin MemoryError
    """Raised for memory engine failures (store/retrieve/search/export)."""


class TransactionError(CaptSoloError):
    """Raised for CTP transaction failures (commit/rollback/validation)."""


class BusError(CaptSoloError):
    """Raised for KHSB message-bus failures (publish/subscribe/request)."""


class IntegrityError(CaptSoloError):
    """Raised when a storage integrity check fails."""


class ConfigurationError(CaptSoloError):
    """Raised when the runtime is misconfigured or required paths are invalid."""


class IdempotencyError(TransactionError):
    """Raised when an idempotency key is reused with conflicting payloads."""


class MigrationBackupError(CaptSoloError):
    """Raised when a pre-migration backup cannot be created or validated.

    Migration is aborted by default when this occurs. A dev-only override
    (``MemoryEngine.ALLOW_MIGRATION_WITHOUT_BACKUP``) may suppress it, but it
    must never be enabled in normal operation or verification.
    """
