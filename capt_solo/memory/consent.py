"""Canonical Consent (Layer 3).

Per Phase 3E, a local canonical consent model for memory and knowledge
operations. Default-deny for sensitive operations (I-05). Local audit trail.
No remote consent synchronization in this phase.

Canonical fields:
- scope (e.g. "memory:store:sensitive", "knowledge:export")
- subject identity
- allowed / denied operations
- expiration
- revocation
- provenance
- policy version
- default-deny for sensitive operations
- local audit trail
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConsentDecision(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"


@dataclass
class ConsentRecord:
    consent_id: str
    subject: str
    scope: str
    decision: str           # granted | denied
    operations: List[str]   # allowed (if granted) or denied ops
    policy_version: int
    created_at: float
    expires_at: Optional[float] = None
    revoked: bool = False
    revoked_at: Optional[float] = None
    provenance: str = "unknown"

    def is_active(self, now: Optional[float] = None) -> bool:
        now = now or time.time()
        if self.revoked:
            return False
        if self.expires_at is not None and now > self.expires_at:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass
class ConsentAuditEntry:
    audit_id: str
    subject: str
    scope: str
    operation: str
    allowed: bool
    reason: str
    timestamp: float


class ConsentStore:
    """Local consent ledger with default-deny for sensitive scopes."""

    def __init__(self, policy_version: int = 1) -> None:
        self._policy_version = policy_version
        self._records: Dict[str, ConsentRecord] = {}
        self._audit: List[ConsentAuditEntry] = []

    # ----- grant / revoke ------------------------------------------------
    def grant(
        self,
        subject: str,
        scope: str,
        operations: List[str],
        *,
        expires_at: Optional[float] = None,
        provenance: str = "unknown",
    ) -> ConsentRecord:
        rec = ConsentRecord(
            consent_id=uuid.uuid4().hex,
            subject=subject, scope=scope, decision=ConsentDecision.GRANTED.value,
            operations=list(operations), policy_version=self._policy_version,
            created_at=time.time(), expires_at=expires_at, provenance=provenance,
        )
        self._records[rec.consent_id] = rec
        return rec

    def deny(
        self,
        subject: str,
        scope: str,
        operations: List[str],
        *,
        provenance: str = "unknown",
    ) -> ConsentRecord:
        rec = ConsentRecord(
            consent_id=uuid.uuid4().hex,
            subject=subject, scope=scope, decision=ConsentDecision.DENIED.value,
            operations=list(operations), policy_version=self._policy_version,
            created_at=time.time(), provenance=provenance,
        )
        self._records[rec.consent_id] = rec
        return rec

    def revoke(self, consent_id: str) -> bool:
        rec = self._records.get(consent_id)
        if rec is None:
            return False
        rec.revoked = True
        rec.revoked_at = time.time()
        return True

    # ----- evaluation (default-deny) ------------------------------------
    def check(self, subject: str, scope: str, operation: str,
              now: Optional[float] = None) -> bool:
        allowed = False
        reason = "default-deny: no active grant"
        explicit_deny = False
        for rec in self._records.values():
            if rec.subject != subject or rec.scope != scope:
                continue
            if not rec.is_active(now):
                continue
            if rec.decision == ConsentDecision.DENIED.value:
                if operation in rec.operations or "*" in rec.operations:
                    explicit_deny = True
                    reason = f"explicit deny by {rec.consent_id}"
                    # deny takes precedence; stop scanning
                    break
            elif rec.decision == ConsentDecision.GRANTED.value:
                if operation in rec.operations or "*" in rec.operations:
                    allowed = True
                    reason = f"granted by {rec.consent_id}"
        if explicit_deny:
            allowed = False
        self._audit.append(ConsentAuditEntry(
            audit_id=uuid.uuid4().hex, subject=subject, scope=scope,
            operation=operation, allowed=allowed, reason=reason,
            timestamp=now or time.time()))
        return allowed

    # ----- persistence ---------------------------------------------------
    def export(self) -> Dict[str, Any]:
        return {
            "policy_version": self._policy_version,
            "records": [r.to_dict() for r in self._records.values()],
            "audit": [a.__dict__ for a in self._audit],
        }

    def import_records(self, data: Dict[str, Any]) -> int:
        count = 0
        for r in data.get("records", []):
            rec = ConsentRecord(**r)
            self._records[rec.consent_id] = rec
            count += 1
        return count

    def audit_trail(self, *, subject: Optional[str] = None) -> List[Dict[str, Any]]:
        return [a.__dict__ for a in self._audit
                if subject is None or a.subject == subject]
