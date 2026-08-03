"""External driver adapters for CAPT (isolated from base runtime).

This package holds adapters that delegate execution to GENUINE external agent
harnesses (e.g. OpenHarness). Each adapter shells out to the real harness binary
in a sandboxed subprocess; none import the external package at base-runtime import
time, so the absence of an external dependency does not break CAPT imports.
"""

from __future__ import annotations
