"""CAPT Solo v0.3 — Session Runtime.

A first-class session subsystem for longitudinal project memory. Sessions
survive process restart (all state is in SQLite). An interrupted
session is detectable (status ``interrupted`` or ``active`` with a stale
last_checkpoint).

Public operations:
    session.begin(...)
    session.checkpoint(...)
    session.status(...)
    session.resume(...)
    session.consolidate(...)
    session.close(...)
    session.abandon(...)

Checkpoints are versioned and immutable after creation. Restart packets
are deterministic and constructed from CSG + AntiToken.

All consequential operations accept an optional ``ctp_tx_id`` so the CTP
journal can link the change to a recoverable transaction.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.memory.antitoken import extract, render, validate
from capt_solo.memory.csg import CSG
from capt_solo.memory.context import build_context
from capt_solo.memory.engine import MemoryEngine
from capt_solo.memory.models import MemoryKind

# Session statuses
SESSION_STATUSES = [
    "active", "paused", "interrupted", "consolidating",
    "completed", "abandoned", "failed",
]

# Checkpoint is immutable after creation (versioned).
CHECKPOINT_VERSION = 1


@dataclass
class Checkpoint:
    checkpoint_id: str
    session_id: str
    version: int
    objective: str
    progress: str
    latest_verified_result: str
    current_hypothesis: str
    pending_transaction: str
    unresolved_failure: str
    files_in_scope: List[str]
    next_action: str
    safety_warning: str
    restart_context: str
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "version": self.version,
            "objective": self.objective,
            "progress": self.progress,
            "latest_verified_result": self.latest_verified_result,
            "current_hypothesis": self.current_hypothesis,
            "pending_transaction": self.pending_transaction,
            "unresolved_failure": self.unresolved_failure,
            "files_in_scope": self.files_in_scope,
            "next_action": self.next_action,
            "safety_warning": self.safety_warning,
            "restart_context": self.restart_context,
            "created_at": self.created_at,
        }


@dataclass
class RestartPacket:
    session_id: str
    project: str
    objective: str
    completed: List[str]
    verified: List[str]
    unresolved: List[str]
    failures: List[str]
    artifacts: List[str]
    open_transactions: List[str]
    governing_decision: str
    recommended_next: str
    do_not_repeat: List[str]
    active_constraints: List[str]
    uncertainty: List[str]
    stale_warnings: List[str]
    generated_at: float
    config_snapshot: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project": self.project,
            "objective": self.objective,
            "completed": self.completed,
            "verified": self.verified,
            "unresolved": self.unresolved,
            "failures": self.failures,
            "artifacts": self.artifacts,
            "open_transactions": self.open_transactions,
            "governing_decision": self.governing_decision,
            "recommended_next": self.recommended_next,
            "do_not_repeat": self.do_not_repeat,
            "active_constraints": self.active_constraints,
            "uncertainty": self.uncertainty,
            "stale_warnings": self.stale_warnings,
            "generated_at": self.generated_at,
            "config_snapshot": self.config_snapshot,
        }


class SessionRuntime:
    """First-class session subsystem backed by SQLite (same DB as memories)."""

    def __init__(self, engine: MemoryEngine) -> None:
        self._eng = engine

    # ----- begin --------------------------------------------------
    def begin(
        self, project_namespace: str, *, objective: str = "",
        ctp_tx_id: Optional[str] = None,
    ) -> str:
        sid = uuid.uuid4().hex
        now = time.time()
        self._eng._conn.execute(
            """INSERT INTO sessions
               (session_id, project_namespace, objective, status, start_time,
                last_checkpoint, created_at, updated_at)
               VALUES (?,?,?, 'active', ?, NULL, ?, ?)""",
            (sid, project_namespace, objective, now, now, now),
        )
        self._eng._conn.execute(
            "INSERT INTO session_events (event_id, session_id, event_type, payload, created_at) "
            "VALUES (?,?, 'session.started', ?, ?)",
            (uuid.uuid4().hex, sid, json.dumps({"objective": objective}), now),
        )
        self._eng._conn.commit()
        return sid

    # ----- checkpoint ----------------------------------------------
    def checkpoint(
        self, session_id: str, *, objective: str = "", progress: str = "",
        latest_verified_result: str = "", current_hypothesis: str = "",
        pending_transaction: str = "", unresolved_failure: str = "",
        files_in_scope: Optional[List[str]] = None, next_action: str = "",
        safety_warning: str = "", restart_context: str = "",
        ctp_tx_id: Optional[str] = None,
    ) -> str:
        """Create an immutable, versioned checkpoint atomically."""
        sess = self._get(session_id)
        if sess is None:
            raise MemoryError_(f"session not found: {session_id}")
        # bump version
        version = CHECKPOINT_VERSION
        for r in self._eng._conn.execute(
            "SELECT MAX(version) AS m FROM session_checkpoints WHERE session_id=?",
            (session_id,)).fetchall():
            if r["m"]:
                version = r["m"] + 1
        # build compact restart context via AntiToken if not provided
        if not restart_context:
            restart_context = self._build_compact_context(
                session_id, objective or sess["objective"], next_action)
        cid = uuid.uuid4().hex
        now = time.time()
        # atomic: checkpoint + session last_checkpoint update
        self._eng._conn.execute(
            """INSERT INTO session_checkpoints
               (checkpoint_id, session_id, version, objective, progress,
                latest_verified_result, current_hypothesis, pending_transaction,
                unresolved_failure, files_in_scope, next_action, safety_warning,
                restart_context, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, session_id, version, objective, progress,
             latest_verified_result, current_hypothesis, pending_transaction,
             unresolved_failure, json.dumps(files_in_scope or []),
             next_action, safety_warning, restart_context, now),
        )
        self._eng._conn.execute(
            "UPDATE sessions SET last_checkpoint=?, status='active', updated_at=? "
            "WHERE session_id=?",
            (now, now, session_id))
        self._eng._conn.execute(
            "INSERT INTO session_events (event_id, session_id, event_type, payload, created_at) "
            "VALUES (?,?, 'session.checkpointed', ?, ?)",
            (uuid.uuid4().hex, session_id, json.dumps({"checkpoint_id": cid, "version": version}), now),
        )
        self._eng._conn.commit()
        return cid

    # ----- status --------------------------------------------------
    def status(self, session_id: str) -> Dict[str, Any]:
        sess = self._get(session_id)
        if sess is None:
            raise MemoryError_(f"session not found: {session_id}")
        # detect interruption: active/paused with stale checkpoint
        now = time.time()
        last = sess.get("last_checkpoint") or sess["start_time"]
        stale = (now - last) > 3600.0  # 1h heuristic for "interrupted"
        derived_status = sess["status"]
        if sess["status"] in ("active", "paused") and stale:
            derived_status = "interrupted"
        checkpoints = [dict(r) for r in self._eng._conn.execute(
            "SELECT * FROM session_checkpoints WHERE session_id=? ORDER BY version DESC",
            (session_id,)).fetchall()]
        return {
            "session_id": session_id,
            "project_namespace": sess["project_namespace"],
            "objective": sess["objective"],
            "status": sess["status"],
            "derived_status": derived_status,
            "interrupted": derived_status == "interrupted",
            "start_time": sess["start_time"],
            "last_checkpoint": sess["last_checkpoint"],
            "active_task": sess.get("active_task"),
            "completed_work": _json_loads(sess.get("completed_work")),
            "files_touched": _json_loads(sess.get("files_touched")),
            "decisions": _json_loads(sess.get("decisions")),
            "failures": _json_loads(sess.get("failures")),
            "hypotheses": _json_loads(sess.get("hypotheses")),
            "ctp_transactions": _json_loads(sess.get("ctp_transactions")),
            "pending_actions": _json_loads(sess.get("pending_actions")),
            "blockers": _json_loads(sess.get("blockers")),
            "unresolved_questions": _json_loads(sess.get("unresolved_questions")),
            "checkpoint_count": len(checkpoints),
            "latest_checkpoint": checkpoints[0] if checkpoints else None,
        }

    # ----- resume --------------------------------------------------
    def resume(self, session_id: str, *, ctp_tx_id: Optional[str] = None) -> RestartPacket:
        """Resume a session: detect interruption, return a restart packet."""
        sess = self._get(session_id)
        if sess is None:
            raise MemoryError_(f"session not found: {session_id}")
        # mark resumed / clear interrupted
        self._eng._conn.execute(
            "UPDATE sessions SET status='active', updated_at=? WHERE session_id=?",
            (time.time(), session_id))
        self._eng._conn.execute(
            "INSERT INTO session_events (event_id, session_id, event_type, payload, created_at) "
            "VALUES (?,?, 'session.resumed', ?, ?)",
            (uuid.uuid4().hex, session_id, json.dumps({}), time.time()))
        self._eng._conn.commit()
        return self.build_restart_packet(session_id)

    # ----- consolidate ---------------------------------------------
    def consolidate(
        self, session_id: str, *, ctp_tx_id: Optional[str] = None,
    ) -> str:
        """Run the session-consolidation pipeline.

        Produces a REVIEWABLE result (not auto-applied promotions). The
        result is stored; the caller decides whether to apply lifecycle
        changes (which go through LifecycleEngine + CTP).
        """
        sess = self._get(session_id)
        if sess is None:
            raise MemoryError_(f"session not found: {session_id}")
        self._eng._conn.execute(
            "UPDATE sessions SET status='consolidating', updated_at=? WHERE session_id=?",
            (time.time(), session_id))
        result = self._consolidate_pipeline(session_id)
        cid = uuid.uuid4().hex
        self._eng._conn.execute(
            """INSERT INTO session_consolidations
               (consolidation_id, session_id, reviewable_result, applied, created_at)
               VALUES (?,?,?,?,?)""",
            (cid, session_id, json.dumps(result, default=str), 0, time.time()))
        self._eng._conn.execute(
            "UPDATE sessions SET status='active', updated_at=? WHERE session_id=?",
            (time.time(), session_id))
        self._eng._conn.execute(
            "INSERT INTO session_events (event_id, session_id, event_type, payload, created_at) "
            "VALUES (?,?, 'session.consolidated', ?, ?)",
            (uuid.uuid4().hex, session_id, json.dumps({"consolidation_id": cid}), time.time()))
        self._eng._conn.commit()
        return cid

    def get_consolidation(self, consolidation_id: str) -> Dict[str, Any]:
        row = self._eng._conn.execute(
            "SELECT * FROM session_consolidations WHERE consolidation_id=?",
            (consolidation_id,)).fetchone()
        if row is None:
            raise MemoryError_(f"consolidation not found: {consolidation_id}")
        d = dict(row)
        d["reviewable_result"] = json.loads(d["reviewable_result"])
        return d

    # ----- close / abandon -----------------------------------------
    def close(
        self, session_id: str, *, outcome: str = "completed",
        ctp_tx_id: Optional[str] = None,
    ) -> None:
        sess = self._get(session_id)
        if sess is None:
            raise MemoryError_(f"session not found: {session_id}")
        self._eng._conn.execute(
            "UPDATE sessions SET status=?, close_outcome=?, updated_at=? WHERE session_id=?",
            (outcome, outcome, time.time(), session_id))
        self._eng._conn.execute(
            "INSERT INTO session_events (event_id, session_id, event_type, payload, created_at) "
            "VALUES (?,?, 'session.closed', ?, ?)",
            (uuid.uuid4().hex, session_id, json.dumps({"outcome": outcome}), time.time()))
        self._eng._conn.commit()

    def abandon(self, session_id: str, *, reason: str = "", ctp_tx_id: Optional[str] = None) -> None:
        sess = self._get(session_id)
        if sess is None:
            raise MemoryError_(f"session not found: {session_id}")
        self._eng._conn.execute(
            "UPDATE sessions SET status='abandoned', close_outcome=?, updated_at=? WHERE session_id=?",
            (reason, time.time(), session_id))
        self._eng._conn.execute(
            "INSERT INTO session_events (event_id, session_id, event_type, payload, created_at) "
            "VALUES (?,?, 'session.abandoned', ?, ?)",
            (uuid.uuid4().hex, session_id, json.dumps({"reason": reason}), time.time()))
        self._eng._conn.commit()

    # ----- listing --------------------------------------------------
    def list(self, *, namespace: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM sessions"
        where = []
        params: List[Any] = []
        if namespace:
            where.append("project_namespace=?")
            params.append(namespace)
        if status:
            where.append("status=?")
            params.append(status)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC"
        return [dict(r) for r in self._eng._conn.execute(sql, params).fetchall()]

    def list_checkpoints(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._eng._conn.execute(
            "SELECT * FROM session_checkpoints WHERE session_id=? ORDER BY version DESC",
            (session_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        row = self._eng._conn.execute(
            "SELECT * FROM session_checkpoints WHERE checkpoint_id=?",
            (checkpoint_id,)).fetchone()
        if row is None:
            raise MemoryError_(f"checkpoint not found: {checkpoint_id}")
        return dict(row)

    # ----- restart packet --------------------------------------------
    def build_restart_packet(
        self, session_id: str, *, budget: Optional[int] = None,
    ) -> RestartPacket:
        """Deterministic restart packet from CSG + AntiToken.

        Recommendations are labeled as recommendations, never as verified facts.
        """
        sess = self._get(session_id)
        if sess is None:
            raise MemoryError_(f"session not found: {session_id}")
        ns = sess["project_namespace"]
        # build context from the project namespace
        res = build_context(
            self._eng, query=sess.get("objective") or "", namespace=ns,
            max_items=10, char_budget=budget)
        # extract structured fields from session
        completed = _json_loads(sess.get("completed_work"))
        failures = _json_loads(sess.get("failures"))
        artifacts = _json_loads(sess.get("files_touched"))
        ctp_tx = _json_loads(sess.get("ctp_transactions"))
        # open transactions = those not marked resolved in session
        open_tx = [t for t in ctp_tx if not str(t).endswith(":done")]
        # governing decision = latest durable decision in context
        governing = ""
        for it in res.items:
            pkt = it.antitoken
            if pkt and pkt.kind == MemoryKind.DECISION.value:
                governing = pkt.assertion
                break
        # do-not-repeat = failures
        do_not_repeat = failures[:5] if failures else []
        # active constraints = constraints from context items
        active_constraints: List[str] = []
        uncertainty: List[str] = []
        stale_warnings: List[str] = []
        for it in res.items:
            pkt = it.antitoken
            if not pkt:
                continue
            active_constraints.extend(pkt.constraints)
            if pkt.uncertainty:
                uncertainty.append(f"{pkt.memory_id}: uncertain ({pkt.assertion[:80]})")
            if pkt.security_warning:
                stale_warnings.append(f"{pkt.memory_id}: security warning")
        # recommended next = latest checkpoint next_action or context-based
        recommended = ""
        cps = self.list_checkpoints(session_id)
        if cps:
            recommended = cps[0].get("next_action") or ""
        if not recommended and res.items:
            recommended = f"Review context item {res.items[0].memory_id} (recommendation, not verified)"
        return RestartPacket(
            session_id=session_id,
            project=ns,
            objective=sess.get("objective") or "",
            completed=completed,
            verified=[it.memory_id for it in res.items if it.antitoken and it.antitoken.kind in (MemoryKind.DECISION.value, MemoryKind.FACT.value)][:5],
            unresolved=_json_loads(sess.get("unresolved_questions")),
            failures=failures,
            artifacts=artifacts,
            open_transactions=open_tx,
            governing_decision=governing,
            recommended_next=recommended,
            do_not_repeat=do_not_repeat,
            active_constraints=active_constraints[:10],
            uncertainty=uncertainty,
            stale_warnings=stale_warnings,
            generated_at=time.time(),
            config_snapshot={"max_items": 10, "char_budget": budget,
                            "csg_weights": CSG(self._eng._conn).get_weights()},
        )

    # ----- internals -------------------------------------------------
    def _get(self, session_id: str) -> Optional[Dict[str, Any]]:
        row = self._eng._conn.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def _build_compact_context(
        self, session_id: str, objective: str, next_action: str,
    ) -> str:
        """Compact, AntiToken-derived restart context (no raw transcript)."""
        sess = self._get(session_id) or {}
        lines = [
            f"OBJECTIVE: {objective}",
            f"NEXT: {next_action}" if next_action else "NEXT: (none recorded)",
        ]
        completed = _json_loads(sess.get("completed_work"))
        if completed:
            lines.append("DONE: " + "; ".join(completed[:5]))
        failures = _json_loads(sess.get("failures"))
        if failures:
            lines.append("AVOID: " + "; ".join(failures[:3]))
        return "\n".join(lines)

    def _consolidate_pipeline(self, session_id: str) -> Dict[str, Any]:
        """Deterministic consolidation: extract candidates, reject noise,
        dedupe, evaluate trust, link CSG, extract decisions/procedures/
        prospective, compress, and produce a reviewable result.

        This does NOT auto-promote. It returns structured findings.
        """
        sess = self._get(session_id) or {}
        objective = sess.get("objective") or ""
        # gather candidate text from session fields
        candidates: List[Dict[str, Any]] = []
        completed = _json_loads(sess.get("completed_work")) or []
        failures = _json_loads(sess.get("failures")) or []
        decisions = _json_loads(sess.get("decisions")) or []
        hypotheses = _json_loads(sess.get("hypotheses")) or []
        pending = _json_loads(sess.get("pending_actions")) or []
        blockers = _json_loads(sess.get("blockers")) or []
        for text in completed + decisions:
            if text and not _is_noise(text):
                candidates.append({"text": text, "kind": "durable_fact"})
        for text in failures:
            if text and not _is_noise(text):
                candidates.append({"text": text, "kind": "failed_approach"})
        for text in hypotheses:
            if text and not _is_noise(text):
                candidates.append({"text": text, "kind": "hypothesis"})
        for text in pending:
            if text and not _is_noise(text):
                candidates.append({"text": text, "kind": "prospective_task"})
        for text in blockers:
            if text and not _is_noise(text):
                candidates.append({"text": text, "kind": "blocker"})
        # dedupe by normalized text
        seen = set()
        deduped = []
        for c in candidates:
            key = _norm(c["text"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        # extract procedures only when enough structure
        procedures = [_extract_procedure(c) for c in deduped if _has_procedure_structure(c["text"])]
        # prospective memories
        prospective = [{"description": c["text"], "kind": c["kind"]}
                        for c in deduped if c["kind"] in ("prospective_task", "blocker")]
        return {
            "session_id": session_id,
            "objective": objective,
            "candidate_count": len(candidates),
            "deduped_count": len(deduped),
            "candidates": deduped,
            "procedures": procedures,
            "prospective": prospective,
            "note": "reviewable result; apply lifecycle changes explicitly",
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _json_loads(s: Optional[str]) -> Any:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else [v]
    except (json.JSONDecodeError, TypeError):
        return [s]


def _norm(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", s.strip().lower())


_NOISE_PATTERNS = [
    r"^(ok|done|thanks|thank you|sure|yes|no|maybe|got it|ack|acknowledged)\.?$",
    r"^(lol|haha|hehe|nice|cool|great|awesome)\.?$",
    r"^(hi|hello|hey|yo)\.?$",
]


def _is_noise(text: str) -> bool:
    t = _norm(text)
    import re
    return any(re.match(p, t) for p in _NOISE_PATTERNS)


def _has_procedure_structure(text: str) -> bool:
    """A procedure needs a trigger, ordered steps, expected result, verification."""
    t = text.lower()
    has_steps = any(k in t for k in ("step", "1.", "2.", "first", "then", "run", "execute"))
    has_result = any(k in t for k in ("result", "output", "expect", "verify", "check"))
    has_trigger = any(k in t for k in ("when", "if", "to", "for", "on "))
    return has_steps and has_result and has_trigger


def _extract_procedure(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic baseline extraction. Missing fields are explicit."""
    text = candidate["text"]
    # very light heuristic split; does NOT fabricate steps
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    steps = [l for l in lines if any(k in l.lower() for k in ("step", "1.", "2.", "3.", "run", "execute", "then", "first"))]
    return {
        "source_text": text,
        "trigger": candidate.get("kind", ""),
        "steps": steps if steps else [],
        "expected_outputs": "",
        "verification": "",
        "missing_fields": ["steps"] if not steps else [],
        "candidate": True,  # explicit: incomplete procedures are candidates only
    }
