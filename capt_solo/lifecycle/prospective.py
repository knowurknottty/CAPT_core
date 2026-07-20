"""CAPT Solo v0.3 — Prospective Memory.

Future intentions, deferred tasks, blockers, retry conditions,
deadlines, release gates, and unresolved commitments.

Prospective memory is LOCAL project memory, NOT an external
scheduler. It surfaces during project bootstrap, session begin/resume,
context build, and release review. It does NOT create calendar
reminders or background tasks.

Public operations:
    prospective.create(...)
    prospective.list(...)
    prospective.resolve(...)
    prospective.expire(...)
    prospective.surface_for(...)   # bootstrap / session / release
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.memory.engine import MemoryEngine

PROSPECTIVE_KINDS = [
    "task", "blocker", "retry", "follow_up", "release_gate",
    "deferred_decision", "dependency", "deadline", "watch_condition",
]

PROSPECTIVE_STATUSES = [
    "pending", "blocked", "ready", "in_progress",
    "resolved", "cancelled", "expired",
]


@dataclass
class ProspectiveIntent:
    intent_id: str
    description: str
    kind: str
    status: str
    priority: str
    namespace: str
    source_session: Optional[str]
    source_memory: Optional[str]
    prerequisites: List[str]
    blocking_conditions: List[str]
    target_condition: str
    due_date: Optional[float]
    retry_after: str
    evidence: str
    ctp_refs: List[str]
    created_at: float
    updated_at: float
    resolved_at: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "description": self.description,
            "kind": self.kind,
            "status": self.status,
            "priority": self.priority,
            "namespace": self.namespace,
            "source_session": self.source_session,
            "source_memory": self.source_memory,
            "prerequisites": self.prerequisites,
            "blocking_conditions": self.blocking_conditions,
            "target_condition": self.target_condition,
            "due_date": self.due_date,
            "retry_after": self.retry_after,
            "evidence": self.evidence,
            "ctp_refs": self.ctp_refs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolved_at": self.resolved_at,
        }


class ProspectiveStore:
    """Prospective memory backed by SQLite (same DB as memories)."""

    def __init__(self, engine: MemoryEngine) -> None:
        self._eng = engine

    # ----- create -------------------------------------------------
    def create(
        self, description: str, *, kind: str = "task",
        status: str = "pending", priority: str = "normal",
        namespace: str = "default", source_session: Optional[str] = None,
        source_memory: Optional[str] = None,
        prerequisites: Optional[List[str]] = None,
        blocking_conditions: Optional[List[str]] = None,
        target_condition: str = "", due_date: Optional[float] = None,
        retry_after: str = "", evidence: str = "",
        ctp_refs: Optional[List[str]] = None,
    ) -> str:
        if not description:
            raise MemoryError_("description must be non-empty")
        if kind not in PROSPECTIVE_KINDS:
            raise MemoryError_(f"unknown prospective kind: {kind}")
        if status not in PROSPECTIVE_STATUSES:
            raise MemoryError_(f"unknown prospective status: {status}")
        iid = uuid.uuid4().hex
        now = time.time()
        self._eng._conn.execute(
            """INSERT INTO prospective_memories
               (intent_id, description, kind, status, priority, namespace,
                source_session, source_memory, prerequisites,
                blocking_conditions, target_condition, due_date,
                retry_after, evidence, ctp_refs, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (iid, description, kind, status, priority, namespace,
             source_session, source_memory,
             json.dumps(prerequisites or []),
             json.dumps(blocking_conditions or []),
             target_condition, due_date,
             retry_after, evidence, json.dumps(ctp_refs or []),
             now, now),
        )
        self._eng._conn.commit()
        return iid

    # ----- list ----------------------------------------------------
    def list(
        self, *, namespace: Optional[str] = None,
        status: Optional[str] = None, kind: Optional[str] = None,
    ) -> List[ProspectiveIntent]:
        sql = "SELECT * FROM prospective_memories"
        where = []
        params: List[Any] = []
        if namespace:
            where.append("namespace=?")
            params.append(namespace)
        if status:
            where.append("status=?")
            params.append(status)
        if kind:
            where.append("kind=?")
            params.append(kind)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC"
        return [self._row_to_intent(r)
                for r in self._eng._conn.execute(sql, params).fetchall()]

    def get(self, intent_id: str) -> Optional[ProspectiveIntent]:
        row = self._eng._conn.execute(
            "SELECT * FROM prospective_memories WHERE intent_id=?",
            (intent_id,)).fetchone()
        return self._row_to_intent(row) if row else None

    # ----- resolve / expire ----------------------------------------
    def resolve(
        self, intent_id: str, *, reason: str = "",
        actor: str = "unknown", ctp_tx_id: Optional[str] = None,
    ) -> bool:
        it = self.get(intent_id)
        if it is None:
            raise MemoryError_(f"intent not found: {intent_id}")
        now = time.time()
        self._eng._conn.execute(
            "UPDATE prospective_memories SET status='resolved', "
            "resolved_at=?, updated_at=? WHERE intent_id=?",
            (now, now, intent_id))
        self._eng._conn.commit()
        return True

    def expire(self, intent_id: str, *, reason: str = "") -> bool:
        it = self.get(intent_id)
        if it is None:
            raise MemoryError_(f"intent not found: {intent_id}")
        self._eng._conn.execute(
            "UPDATE prospective_memories SET status='expired', "
            "updated_at=? WHERE intent_id=?",
            (time.time(), intent_id))
        self._eng._conn.commit()
        return True

    def cancel(self, intent_id: str, *, reason: str = "") -> bool:
        it = self.get(intent_id)
        if it is None:
            raise MemoryError_(f"intent not found: {intent_id}")
        self._eng._conn.execute(
            "UPDATE prospective_memories SET status='cancelled', "
            "updated_at=? WHERE intent_id=?",
            (time.time(), intent_id))
        self._eng._conn.commit()
        return True

    def set_status(self, intent_id: str, status: str, *, reason: str = "") -> bool:
        """Explicitly move an intent to a valid status (e.g. blocked -> ready)."""
        if status not in PROSPECTIVE_STATUSES:
            raise MemoryError_(f"unknown prospective status: {status}")
        it = self.get(intent_id)
        if it is None:
            raise MemoryError_(f"intent not found: {intent_id}")
        self._eng._conn.execute(
            "UPDATE prospective_memories SET status=?, updated_at=? "
            "WHERE intent_id=?",
            (status, time.time(), intent_id))
        self._eng._conn.commit()
        return True

    # ----- surfacing ------------------------------------------------
    def surface_for(
        self, context: str, *, namespace: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return open intents relevant to a context (bootstrap/session/release).

        Surfaces: pending/blocked/ready/in_progress, not resolved/
        cancelled/expired. Optionally filtered by namespace.

        For the recognized surfacing contexts (bootstrap, session, release),
        ALL open intents in the namespace are surfaced — token overlap is not
        required, because the point is to remind the agent of unfinished work
        at the start of a session or release. For arbitrary queries, token
        overlap is used as a relevance filter.
        """
        active = self.list(namespace=namespace, status=None)
        ctx = (context or "").lower()
        surfacing_trigger = any(
            t in ctx for t in ("bootstrap", "session", "release", "begin", "resume"))
        out = []
        for it in active:
            if it.status in ("resolved", "cancelled", "expired"):
                continue
            if surfacing_trigger:
                out.append(it.to_dict())
                continue
            # arbitrary query: require token overlap
            ctx_tokens = set(ctx.split())
            desc_tokens = set(it.description.lower().split())
            if ctx_tokens & desc_tokens:
                out.append(it.to_dict())
        return out

    # ----- internals ------------------------------------------------
    @staticmethod
    def _row_to_intent(row) -> ProspectiveIntent:
        return ProspectiveIntent(
            intent_id=row["intent_id"],
            description=row["description"],
            kind=row["kind"],
            status=row["status"],
            priority=row["priority"],
            namespace=row["namespace"],
            source_session=row["source_session"],
            source_memory=row["source_memory"],
            prerequisites=json.loads(row["prerequisites"]),
            blocking_conditions=json.loads(row["blocking_conditions"]),
            target_condition=row["target_condition"],
            due_date=row["due_date"],
            retry_after=row["retry_after"],
            evidence=row["evidence"],
            ctp_refs=json.loads(row["ctp_refs"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            resolved_at=row["resolved_at"],
        )
