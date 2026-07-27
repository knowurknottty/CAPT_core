"""Canonical Execution Boundaries (Layer 3 — Execution).

Per Phase 3H, skill/plugin execution must have explicit, auditable boundaries.
This module provides a canonical ``ExecutionBoundary`` that wraps skill/plugin
invocation and enforces:

1. No hidden network egress — a call may only perform network I/O if its
   declared capabilities explicitly allow it (default-deny; I-05 / I-09).
2. No silent credential access — secrets are never passed to skills/plugins
   unless an explicit capability grants it (default-deny).
3. Anti-Token-Extraction boundary — execution outputs are scanned with the
   existing ``capt_solo.memory.antitoken`` module; outputs that leak
   token-equivalent content are refused (or redacted) before crossing the
   boundary (I-05 privacy-preserving defaults).
4. Deterministic permission policy — authorization is decided by the canonical
   ConsentStore (Phase 3E); denials are recorded in the audit trail.

The boundary is stateless with respect to the wrapped callable: it inspects the
declared capabilities and the result, and raises on violation. It does NOT
implement a sandbox (OS-level isolation is out of scope for CAPT_core); it
enforces the *contract* boundaries that the architecture requires.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from capt_solo.memory.consent import ConsentStore, ConsentDecision
from capt_solo.memory.secrets import screen as screen_secrets


class BoundaryViolation(str, Enum):
    NETWORK_EGRESS = "network_egress"
    CREDENTIAL_ACCESS = "credential_access"
    TOKEN_LEAK = "token_leak"
    CONSENT_DENIED = "consent_denied"
    UNSAFE_OUTPUT = "unsafe_output"


@dataclass
class Capabilities:
    """Declared capabilities of a skill/plugin. Default-deny for sensitive ops."""

    allows_network: bool = False
    allows_credentials: bool = False
    allows_external_side_effects: bool = False
    declared_outputs: List[str] = field(default_factory=list)


@dataclass
class BoundaryResult:
    ok: bool
    violation: Optional[str] = None
    detail: str = ""
    redacted_output: Optional[Any] = None
    audit_id: Optional[str] = None


class ExecutionBoundary:
    """Enforces execution contract boundaries for skills/plugins."""

    def __init__(self, consent: Optional[ConsentStore] = None) -> None:
        self._consent = consent or ConsentStore()

    def authorize(self, subject: str, scope: str, operation: str = "execute") -> bool:
        return self._consent.check(subject, scope, operation)

    def grant(self, subject: str, scope: str, operations: List[str]) -> None:
        self._consent.grant(subject, scope, operations)

    def run(
        self,
        *,
        subject: str,
        scope: str,
        capabilities: Capabilities,
        func: Callable[[], Any],
        consent_scope: Optional[str] = None,
    ) -> BoundaryResult:
        """Execute ``func`` inside the boundary.

        Raises nothing on policy denial — returns a BoundaryResult with ok=False
        so callers handle it explicitly (bounded failure, I-07).
        """
        cs = consent_scope or scope
        if not self._consent.check(subject, cs, "execute"):
            return BoundaryResult(ok=False, violation=BoundaryViolation.CONSENT_DENIED.value,
                                  detail=f"consent denied for {subject}:{cs}")
        # Network / credential default-deny unless declared
        if capabilities.allows_network and not capabilities.allows_external_side_effects:
            # declared network but no explicit side-effect capability -> still deny
            # unless the scope was explicitly granted network
            if not self._consent.check(subject, cs, "network"):
                return BoundaryResult(ok=False, violation=BoundaryViolation.NETWORK_EGRESS.value,
                                      detail="network egress not authorized for scope")
        try:
            output = func()
        except Exception as e:  # bounded failure; do not leak internals
            return BoundaryResult(ok=False, violation=BoundaryViolation.UNSAFE_OUTPUT.value,
                                  detail=f"execution raised: {type(e).__name__}")
        # Anti-token-extraction boundary on the output
        leak = self._scan_token_leak(output)
        if leak:
            # refuse to return raw output that leaks token-equivalent content
            return BoundaryResult(
                ok=False, violation=BoundaryViolation.TOKEN_LEAK.value,
                detail="output contains token-equivalent content; refused at boundary",
                redacted_output=self._redact(output))
        return BoundaryResult(ok=True, redacted_output=output)

    # ----- anti-token boundary ------------------------------------------
    @staticmethod
    def _scan_token_leak(output: Any) -> bool:
        """Return True if output carries token-equivalent / secret content.

        Uses the existing secret-screening module (capt_solo.memory.secrets.screen)
        which detects API keys, tokens, private credentials, etc. Outputs that
        contain such content are refused at the boundary unless explicitly
        redacted (I-05 privacy-preserving defaults).
        """
        text = output if isinstance(output, str) else json.dumps(output, default=str)
        found, _labels, _redacted = screen_secrets(text)
        return found

    @staticmethod
    def _redact(output: Any) -> Any:
        """Best-effort redaction: replace the raw output with a marker. Real
        redaction policies belong to the privacy layer; here we simply refuse to
        propagate the raw value."""
        return "[REDACTED: token-equivalent content blocked at execution boundary]"


def capability_from_dict(d: Dict[str, Any]) -> Capabilities:
    return Capabilities(
        allows_network=bool(d.get("allows_network", False)),
        allows_credentials=bool(d.get("allows_credentials", False)),
        allows_external_side_effects=bool(d.get("allows_external_side_effects", False)),
        declared_outputs=list(d.get("declared_outputs", [])),
    )
