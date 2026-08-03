"""Adapter-specific errors for the genuine OpenHarness external driver."""

from __future__ import annotations

from typing import Any, Dict, Optional


class OpenHarnessExternalDriverError(Exception):
    """Base error for the external OpenHarness adapter."""


class OpenHarnessExecutionError(OpenHarnessExternalDriverError):
    """The genuine ``oh`` process failed or returned no usable output."""

    def __init__(self, message: str, *, returncode: Optional[int] = None,
                 stderr: str = "") -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class OpenHarnessUnsafeEnvironmentError(OpenHarnessExternalDriverError):
    """Refuse to launch because the sandbox environment could not be made safe."""


class OpenHarnessLifecycleError(OpenHarnessExternalDriverError):
    """Lifecycle operation not supported or failed (e.g. resume on a one-shot run)."""


class OpenHarnessNetworkViolation(OpenHarnessExternalDriverError):
    """The external harness attempted a non-allowlisted network endpoint."""

    def __init__(self, message: str, *, attempted: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.attempted = attempted or {}
