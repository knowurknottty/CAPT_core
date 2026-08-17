"""In-process fail-closed check for exact model text at driver dispatch.

RuntimeService remains the durable authority.  This registry carries the
already-authorized dispatch digest across the final in-process seam from the
command service to a driver.  Standalone driver conformance tests that do not
use the governed model-operator command path have no registered expectation.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional

from .errors import AuthorityViolation

_LOCK = threading.RLock()
_EXPECTED: Dict[str, str] = {}


def register_expected_prompt_digest(driver_run_id: str, prompt_digest: str) -> None:
    if not driver_run_id or not prompt_digest:
        raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DISPATCH_BINDING_MISSING")
    with _LOCK:
        prior = _EXPECTED.get(driver_run_id)
        if prior is not None and prior != prompt_digest:
            raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DISPATCH_BINDING_CONFLICT")
        _EXPECTED[driver_run_id] = prompt_digest


def require_expected_prompt_digest(driver_run_id: str, actual_digest: str) -> Optional[str]:
    """Verify a registered governed run; leave standalone driver calls untouched."""
    with _LOCK:
        expected = _EXPECTED.get(driver_run_id)
    if expected is None:
        return None
    if expected != actual_digest:
        raise AuthorityViolation("MODEL_PROMPT_APPROVAL_DISPATCH_DIGEST_MISMATCH")
    return expected
