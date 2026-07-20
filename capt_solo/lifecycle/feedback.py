"""CAPT Solo v0.3 — Retrieval Feedback + Bounded Adaptation.

Retrieval feedback records how useful a retrieved memory was. It may
adjust per-project RANKING signals only. It must NEVER:

  * change trust state
  * establish truth
  * delete memory
  * resolve conflicts
  * promote a memory to durable
  * rewrite source content

Adaptation is BOUNDED, reversible, inspectable, and project-scoped.
There is NO hidden model training and NO silent cross-project transfer.
This is accurately described as bounded feedback-driven ranking
adaptation — NOT machine learning.

Public operations:
    feedback.record(...)
    feedback.get_adaptation_state(...)
    feedback.reset_adaptation(...)
    feedback.explain_weight_change(...)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.memory.engine import MemoryEngine

# Allowed feedback kinds (explicit, auditable).
FEEDBACK_KINDS = [
    "useful", "irrelevant", "outdated", "contradictory",
    "misleading", "incomplete", "too_verbose", "too_compressed",
]

# Bounded adaptation keys (per-project ranking preferences).
ADAPTATION_KEYS = [
    "preferred_memory_kind",
    "preferred_recency_balance",
    "preferred_verbosity",
    "preferred_procedural_detail",
    "preferred_conflict_visibility",
    "preferred_context_density",
]

# Bounds: each adaptation value is clamped to [MIN, MAX].
ADAPTATION_MIN = -1.0
ADAPTATION_MAX = 1.0
ADAPTATION_STEP = 0.1

# Feedback -> bounded delta per adaptation key.
FEEDBACK_TO_DELTA = {
    "useful": {"preferred_memory_kind": 0.0, "preferred_recency_balance": 0.05,
                "preferred_verbosity": 0.0, "preferred_procedural_detail": 0.05,
                "preferred_conflict_visibility": 0.0,
                "preferred_context_density": 0.05},
    "irrelevant": {"preferred_context_density": -0.1,
                    "preferred_recency_balance": -0.05},
    "outdated": {"preferred_recency_balance": -0.1},
    "contradictory": {"preferred_conflict_visibility": 0.1},
    "misleading": {"preferred_conflict_visibility": 0.1,
                    "preferred_context_density": -0.05},
    "incomplete": {"preferred_context_density": -0.05},
    "too_verbose": {"preferred_verbosity": -0.1},
    "too_compressed": {"preferred_verbosity": 0.1},
}


@dataclass
class FeedbackRecord:
    feedback_id: str
    memory_id: Optional[str]
    context_build_id: Optional[str]
    session_id: Optional[str]
    query: str
    feedback_kind: str
    reason: str
    actor: str
    trace_id: str
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "memory_id": self.memory_id,
            "context_build_id": self.context_build_id,
            "session_id": self.session_id,
            "query": self.query,
            "feedback_kind": self.feedback_kind,
            "reason": self.reason,
            "actor": self.actor,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }


class RetrievalFeedback:
    """Bounded, reversible, project-scoped ranking adaptation."""

    def __init__(self, engine: MemoryEngine) -> None:
        self._eng = engine

    # ----- record -------------------------------------------------
    def record(
        self, feedback_kind: str, *,
        memory_id: Optional[str] = None,
        context_build_id: Optional[str] = None,
        session_id: Optional[str] = None,
        query: str = "",
        reason: str = "",
        actor: str = "unknown",
        namespace: str = "default",
        trace_id: Optional[str] = None,
    ) -> str:
        if feedback_kind not in FEEDBACK_KINDS:
            raise MemoryError_(f"unknown feedback kind: {feedback_kind}")
        fid = uuid.uuid4().hex
        now = time.time()
        self._eng._conn.execute(
            """INSERT INTO retrieval_feedback
               (feedback_id, memory_id, context_build_id, session_id,
                query, feedback_kind, reason, actor, trace_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (fid, memory_id, context_build_id, session_id,
             query, feedback_kind, reason, actor,
             trace_id or uuid.uuid4().hex, now),
        )
        # bounded adaptation update (does NOT touch trust/truth/memory)
        self._apply_adaptation(namespace, feedback_kind, fid)
        self._eng._conn.commit()
        return fid

    # ----- adaptation state ------------------------------------------
    def get_adaptation_state(self, namespace: str = "default") -> Dict[str, Any]:
        rows = self._eng._conn.execute(
            "SELECT key, value FROM retrieval_adaptation WHERE namespace=?",
            (namespace,)).fetchall()
        state = {k: 0.0 for k in ADAPTATION_KEYS}
        for r in rows:
            state[r["key"]] = r["value"]
        return {"namespace": namespace, "adaptation": state,
                "bounded": True, "range": [ADAPTATION_MIN, ADAPTATION_MAX]}

    def list_feedback(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent retrieval feedback entries (no raw SQL at call sites)."""
        rows = self._eng._conn.execute(
            "SELECT * FROM retrieval_feedback ORDER BY created_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]

    def reset_adaptation(self, namespace: str = "default") -> None:
        """Revert adaptation to neutral (reversible). Does NOT delete feedback."""
        self._eng._conn.execute(
            "DELETE FROM retrieval_adaptation WHERE namespace=?", (namespace,))
        self._eng._conn.commit()

    def explain_weight_change(
        self, feedback_kind: str, namespace: str = "default",
    ) -> Dict[str, Any]:
        """Explain what a feedback kind WOULD change (no mutation)."""
        if feedback_kind not in FEEDBACK_KINDS:
            raise MemoryError_(f"unknown feedback kind: {feedback_kind}")
        deltas = FEEDBACK_TO_DELTA.get(feedback_kind, {})
        return {
            "feedback_kind": feedback_kind,
            "would_change": deltas,
            "bounded": True,
            "note": "adaptation affects ranking only; never trust/truth/memory",
        }

    # ----- internals -------------------------------------------------
    def _apply_adaptation(
        self, namespace: str, feedback_kind: str, feedback_id: str,
    ) -> None:
        deltas = FEEDBACK_TO_DELTA.get(feedback_kind, {})
        if not deltas:
            return
        # read current state
        cur = {r["key"]: r["value"] for r in self._eng._conn.execute(
            "SELECT key, value FROM retrieval_adaptation WHERE namespace=?",
            (namespace,)).fetchall()}
        now = time.time()
        for key, delta in deltas.items():
            if key not in ADAPTATION_KEYS:
                continue
            new_v = cur.get(key, 0.0) + delta * ADAPTATION_STEP
            new_v = max(ADAPTATION_MIN, min(ADAPTATION_MAX, round(new_v, 4)))
            cur[key] = new_v
            self._eng._conn.execute(
                """INSERT OR REPLACE INTO retrieval_adaptation
                   (namespace, key, value, updated_at) VALUES (?,?,?,?)""",
                (namespace, key, new_v, now))
