"""CAPT Solo v0.4 — Proof Engine.

Everything CAPT claims must reference evidence. This module defines the
Evidence object, the evidence store (SQLite-backed, local-first), and proof
aggregation: a capability may require N successful runs, M passing integration
suites, K human approvals, etc. before entering a Verified state.

Evidence types (non-exhaustive, extensible):
    test_pass          - a passing test
    ctp_receipt        - a committed CTP transaction receipt
    command_output     - captured stdout/stderr of a command
    artifact_hash      - a SHA-256 of a verified file/artifact
    procedure_run      - a successful procedure execution
    migration_ok       - migration verification passed
    human_approval     - explicit human sign-off
    static_analysis    - lint/typecheck/parse passed
    integration_pass   - an integration test suite passed

Every Evidence carries: id, type, producer, timestamp, hash, provenance,
trust, expiration, scope, associated artifacts.

Proof aggregation:
    A ProofRequirement lists (evidence_type, min_count). A Capability aggregates
    its collected evidence and reports satisfied / unsatisfied requirements.

No evidence is ever fabricated. If a requirement is unsatisfied, the capability
stays below Verified and ClaimGuard downgrades language accordingly.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_


# Evidence types known to the engine. Extensible via register_evidence_type.
KNOWN_EVIDENCE_TYPES = {
    "test_pass", "ctp_receipt", "command_output", "artifact_hash",
    "procedure_run", "migration_ok", "human_approval", "static_analysis",
    "integration_pass",
}

# Default expiration (seconds) for evidence — 90 days. Evidence older than this
# is treated as stale and excluded from aggregation unless explicitly renewed.
DEFAULT_EVIDENCE_TTL = 90 * 24 * 3600


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Evidence:
    """A single piece of supporting evidence for a claim or capability."""

    id: str
    type: str
    producer: str
    timestamp: float
    hash: str
    provenance: str
    trust: float
    expiration: float
    scope: str
    artifacts: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Evidence":
        from capt_solo.foundry.columns import decode_list, decode_dict
        # Accept both in-memory shape (id, list artifacts) and DB row shape
        # (evidence_id, JSON-string artifacts/payload).
        return cls(
            id=d.get("evidence_id") or d["id"], type=d["type"], producer=d["producer"],
            timestamp=d["timestamp"], hash=d["hash"], provenance=d["provenance"],
            trust=d["trust"], expiration=d["expiration"], scope=d["scope"],
            artifacts=decode_list(d.get("artifacts"), field="artifacts"),
            payload=decode_dict(d.get("payload"), field="payload"),
        )

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return now > self.expiration

    def is_valid(self, now: Optional[float] = None) -> bool:
        return not self.is_expired(now) and self.trust > 0.0


@dataclass
class ProofRequirement:
    """A requirement: at least `min_count` evidence of `type` in `scope`."""

    type: str
    min_count: int
    scope: Optional[str] = None
    min_trust: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProofAggregate:
    """Result of aggregating evidence against requirements."""

    satisfied: bool
    satisfied_requirements: List[Dict[str, Any]] = field(default_factory=list)
    unsatisfied_requirements: List[Dict[str, Any]] = field(default_factory=list)
    evidence_count: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProofEngine:
    """SQLite-backed evidence store + aggregation.

    All evidence is persisted with CTP transaction linkage when available.
    No evidence is fabricated; aggregation only counts real stored evidence.
    """

    def __init__(self, conn) -> None:
        self._conn = conn

    # ----- record -------------------------------------------------------
    def record(
        self, type: str, producer: str, hash: str, provenance: str,
        scope: str = "default", *, trust: float = 1.0,
        artifacts: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        ttl: float = DEFAULT_EVIDENCE_TTL,
        ctp_tx_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Evidence:
        if type not in KNOWN_EVIDENCE_TYPES:
            raise MemoryError_(f"unknown evidence type: {type}")
        if trust < 0.0 or trust > 1.0:
            raise MemoryError_(f"trust out of range: {trust}")
        now = timestamp if timestamp is not None else time.time()
        # deduplicate: identical (type, producer, hash, scope, provenance) within
        # validity is one piece of evidence, not N. Return existing if present.
        existing = self._conn.execute(
            """SELECT evidence_id FROM proof_evidence
               WHERE type=? AND producer=? AND hash=? AND scope=? AND provenance=?
                 AND expiration > ?
               ORDER BY timestamp DESC LIMIT 1""",
            (type, producer, hash, scope, provenance, now)).fetchone()
        if existing is not None:
            return self.get(existing["evidence_id"])
        ev = Evidence(
            id=uuid.uuid4().hex, type=type, producer=producer, timestamp=now,
            hash=hash, provenance=provenance, trust=trust,
            expiration=now + ttl, scope=scope,
            artifacts=list(artifacts or []), payload=dict(payload or {}))
        self._conn.execute(
            """INSERT OR REPLACE INTO proof_evidence
               (evidence_id, type, producer, timestamp, hash, provenance,
                trust, expiration, scope, artifacts, payload, ctp_tx_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ev.id, ev.type, ev.producer, ev.timestamp, ev.hash, ev.provenance,
             ev.trust, ev.expiration, ev.scope, json.dumps(ev.artifacts),
             json.dumps(ev.payload), ctp_tx_id))
        self._conn.commit()
        return ev

    def record_from_text(
        self, type: str, producer: str, text: str, provenance: str,
        scope: str = "default", **kwargs,
    ) -> Evidence:
        """Convenience: hash arbitrary text content as the evidence hash."""
        return self.record(type, producer, sha256_of(text), provenance,
                           scope, **kwargs)

    # ----- query --------------------------------------------------------
    def get(self, evidence_id: str) -> Optional[Evidence]:
        row = self._conn.execute(
            "SELECT * FROM proof_evidence WHERE evidence_id=?",
            (evidence_id,)).fetchone()
        return Evidence.from_dict(dict(row)) if row else None

    def list_by_scope(self, scope: str, *, valid_only: bool = True,
                      now: Optional[float] = None) -> List[Evidence]:
        now = now if now is not None else time.time()
        rows = self._conn.execute(
            "SELECT * FROM proof_evidence WHERE scope=? ORDER BY timestamp DESC",
            (scope,)).fetchall()
        out = [Evidence.from_dict(dict(r)) for r in rows]
        if valid_only:
            out = [e for e in out if e.is_valid(now)]
        return out

    def list_by_type(self, type: str, *, valid_only: bool = True,
                     now: Optional[float] = None) -> List[Evidence]:
        now = now if now is not None else time.time()
        rows = self._conn.execute(
            "SELECT * FROM proof_evidence WHERE type=? ORDER BY timestamp DESC",
            (type,)).fetchall()
        out = [Evidence.from_dict(dict(r)) for r in rows]
        if valid_only:
            out = [e for e in out if e.is_valid(now)]
        return out

    # ----- requirements -------------------------------------------------
    def set_requirements(self, scope: str,
                         requirements: List[ProofRequirement]) -> None:
        # replace existing requirements for this scope
        self._conn.execute(
            "DELETE FROM proof_requirements WHERE scope=?", (scope,))
        for req in requirements:
            self._conn.execute(
                """INSERT OR REPLACE INTO proof_requirements
                   (scope, type, min_count, min_trust)
                   VALUES (?,?,?,?)""",
                (scope, req.type, req.min_count, req.min_trust))
        self._conn.commit()

    def get_requirements(self, scope: str) -> List[ProofRequirement]:
        rows = self._conn.execute(
            "SELECT type, min_count, scope, min_trust FROM proof_requirements "
            "WHERE scope=?", (scope,)).fetchall()
        return [ProofRequirement(r["type"], r["min_count"], r["scope"],
                                 r["min_trust"]) for r in rows]

    # ----- aggregation --------------------------------------------------
    def aggregate(self, capability_id: str, *,
                  evidence: Optional[List[Evidence]] = None,
                  now: Optional[float] = None) -> ProofAggregate:
        """Aggregate stored evidence against the capability's requirements."""
        now = now if now is not None else time.time()
        reqs = self.get_requirements(capability_id)
        if evidence is None:
            # gather all valid evidence across scopes (requirements may scope)
            rows = self._conn.execute(
                "SELECT * FROM proof_evidence").fetchall()
            evidence = [Evidence.from_dict(dict(r)) for r in rows]
        valid = [e for e in evidence if e.is_valid(now)]
        by_type: Dict[str, int] = {}
        for e in valid:
            by_type[e.type] = by_type.get(e.type, 0) + 1

        satisfied_reqs = []
        unsatisfied_reqs = []
        all_satisfied = True
        for req in reqs:
            # count valid evidence of this type (and scope if specified)
            count = 0
            for e in valid:
                if e.type != req.type:
                    continue
                if req.scope and e.scope != req.scope:
                    continue
                if e.trust < req.min_trust:
                    continue
                count += 1
            entry = {"type": req.type, "min_count": req.min_count,
                     "scope": req.scope, "have": count}
            if count >= req.min_count:
                satisfied_reqs.append(entry)
            else:
                unsatisfied_reqs.append(entry)
                all_satisfied = False
        return ProofAggregate(
            satisfied=all_satisfied,
            satisfied_requirements=satisfied_reqs,
            unsatisfied_requirements=unsatisfied_reqs,
            evidence_count=len(valid),
            by_type=by_type,
        )

    # ----- persistence helpers -----------------------------------------
    def export_evidence(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        if scope:
            rows = self._conn.execute(
                "SELECT * FROM proof_evidence WHERE scope=?", (scope,)).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM proof_evidence").fetchall()
        return [Evidence.from_dict(dict(r)).to_dict() for r in rows]

    def import_evidence(self, items: List[Dict[str, Any]]) -> int:
        n = 0
        for d in items:
            ev = Evidence.from_dict(d)
            self._conn.execute(
                """INSERT OR IGNORE INTO proof_evidence
                   (evidence_id, type, producer, timestamp, hash, provenance,
                    trust, expiration, scope, artifacts, payload, ctp_tx_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ev.id, ev.type, ev.producer, ev.timestamp, ev.hash,
                 ev.provenance, ev.trust, ev.expiration, ev.scope,
                 json.dumps(ev.artifacts), json.dumps(ev.payload), None))
            n += 1
        self._conn.commit()
        return n
