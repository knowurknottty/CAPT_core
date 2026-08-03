"""Genuine OpenHarness external driver package (Gate A).

Public surface: ``OpenHarnessExternalDriver`` and ``DESCRIPTOR``.

This package is isolated from base CAPT: it imports only frozen CAPT contracts
(``..drivers.require``) and standard library. It shells out to the real ``oh``
binary; it does NOT import the openharness Python package. Base CAPT runtime
remains importable and usable when OpenHarness is absent.
"""

from __future__ import annotations

from .adapter import OpenHarnessExternalDriver
from .lifecycle import DESCRIPTOR
from .errors import (
    OpenHarnessExternalDriverError,
    OpenHarnessExecutionError,
    OpenHarnessLifecycleError,
    OpenHarnessNetworkViolation,
    OpenHarnessUnsafeEnvironmentError,
)

__all__ = [
    "OpenHarnessExternalDriver",
    "DESCRIPTOR",
    "OpenHarnessExternalDriverError",
    "OpenHarnessExecutionError",
    "OpenHarnessLifecycleError",
    "OpenHarnessNetworkViolation",
    "OpenHarnessUnsafeEnvironmentError",
]
