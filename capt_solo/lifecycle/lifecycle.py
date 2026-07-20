"""CAPT Solo v0.3 — Adaptive Memory Lifecycle (engine internals).

This module implements the explicit memory-tier and lifecycle-state model,
deterministic promotion/demotion rules, controlled decay, and
archive/restore. The public re-exports live in
``capt_solo.lifecycle.__init__``; this file is the implementation.

Design constraints (from the v0.3 spec):
  * Every memory has an explicit tier and lifecycle state.
  * Lifecycle state and trust state are DISTINCT concepts.
  * Repetition alone never promotes truth or trust.
  * No automatic promotion to ``pinned``.
  * Protected records are never silently decayed or deleted.
  * Permanent deletion remains an explicit, audited operation.

All transitions are recorded in ``memory_lifecycle_transitions`` with
previous state, new state, reason, actor, timestamp, evidence, CTP
tx id, config snapshot, and trace id. A failed transition must
NOT leave partial state.
"""

from __future__ import annotations

import enum
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.memory.models import TrustState


class MemoryTier(str, enum.Enum):
    """Explicit durability/visibility tiers.

    A tier describes HOW LONG and HOW PROMINENTLY a memory lives. It is
    independent of lifecycle state (a ``durable`` memory can be ``candidate``).
    """

    WORKING = "working"
    SESSION = "session"
    EPISODIC = "episodic"
    DURABLE = "durable"
    PROCEDURAL = "procedural"
    PROSPECTIVE = "prospective"
    ARCHIVED = "archived"


class LifecycleState(str, enum.Enum):
    """Explicit lifecycle states, independent of trust."""

    TRANSIENT = "transient"
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DURABLE = "durable"
    PINNED = "pinned"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    REJECTED = "rejected"
    EXPIRED = "expired"


# Allowed transitions. A transition not in this map is invalid and must fail.
VALID_TRANSITIONS: Dict[str, List[str]] = {
    LifecycleState.TRANSIENT.value: [
        LifecycleState.CANDIDATE.value,
        LifecycleState.EXPIRED.value,
    ],
    LifecycleState.CANDIDATE.value: [
        LifecycleState.ACTIVE.value,
        LifecycleState.DURABLE.value,
        LifecycleState.REJECTED.value,
    ],
    LifecycleState.ACTIVE.value: [
        LifecycleState.DURABLE.value,
        LifecycleState.SUPERSEDED.value,
        LifecycleState.ARCHIVED.value,
        LifecycleState.EXPIRED.value,
    ],
    LifecycleState.DURABLE.value: [
        LifecycleState.PINNED.value,
        LifecycleState.ARCHIVED.value,
        LifecycleState.SUPERSEDED.value,
        LifecycleState.EXPIRED.value,
    ],
    LifecycleState.PINNED.value: [
        LifecycleState.ARCHIVED.value,
        LifecycleState.EXPIRED.value,
    ],
    LifecycleState.SUPERSEDED.value: [
        LifecycleState.ARCHIVED.value,
        LifecycleState.ACTIVE.value,  # recoverable if the superseding record is itself superseded
    ],
    LifecycleState.ARCHIVED.value: [
        LifecycleState.ACTIVE.value,  # restore
        LifecycleState.EXPIRED.value,
    ],
    LifecycleState.REJECTED.value: [
        LifecycleState.CANDIDATE.value,  # re-open if new evidence arrives
    ],
    LifecycleState.EXPIRED.value: [
        LifecycleState.CANDIDATE.value,  # re-open if new evidence arrives
    ],
}

# States that may NEVER be silently decayed or deleted.
PROTECTED_STATES = {
    LifecycleState.PINNED.value,
    LifecycleState.ARCHIVED.value,  # archived is preserved, not decayed
}

# Retention classes (configurable per namespace).
class RetentionClass(str, enum.Enum):
    EPHEMERAL = "ephemeral"
    SESSION = "session"
    PROJECT = "project"
    LONG_TERM = "long_term"
    PINNED = "pinned"
    AUDIT = "audit"


@dataclass
class PromotionEvaluation:
    memory_id: str
    current_state: str
    trust_state: str
    eligible_transitions: List[str]
    missing_evidence: List[str]
    disqualifying_conflicts: List[str]
    confidence: float
    user_approval_required: bool
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "current_state": self.current_state,
            "trust_state": self.trust_state,
            "eligible_transitions": self.eligible_transitions,
            "missing_evidence": self.missing_evidence,
            "disqualifying_conflicts": self.disqualifying_conflicts,
            "confidence": self.confidence,
            "user_approval_required": self.user_approval_required,
            "reason": self.reason,
        }


# Evidence kinds that count toward promotion (explicit, auditable).
PROMOTION_EVIDENCE = {
    "user_approval",
    "verified_test_result",
    "committed_ctp_receipt",
    "repeated_independent_confirmation",
    "stable_architectural_decision",
    "successful_repeated_procedure",
    "resolved_conflict",
    "artifact_evidence",
    "imported_signed_or_trusted_source",
}


def _valid_transitions_from(state: str) -> List[str]:
    return list(VALID_TRANSITIONS.get(state, []))


class LifecycleEngine:
    """Orchestrates tier/state transitions, promotion, decay, archive/restore.

    Operates on a :class:`MemoryEngine` instance (caller owns lifecycle).
    All consequential operations accept an optional ``ctp_tx_id`` so the CTP
    journal can link the lifecycle change to a recoverable transaction.
    """

    def __init__(self, engine) -> None:
        self._eng = engine

    # ----- transition core ----------------------------------------------
    def _record_transition(
        self, memory_id: str, previous: str, new: str, *,
        reason: Optional[str] = None, actor: str = "unknown",
        evidence: Optional[List[str]] = None, ctp_tx_id: Optional[str] = None,
        config_snapshot: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        tid = uuid.uuid4().hex
        self._eng._conn.execute(
            """INSERT INTO memory_lifecycle_transitions
               (transition_id, memory_id, previous_state, new_state, reason,
                actor, evidence, ctp_tx_id, config_snapshot, trace_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (tid, memory_id, previous, new, reason, actor,
             json.dumps(evidence or []), ctp_tx_id,
             json.dumps(config_snapshot or {}), trace_id or uuid.uuid4().hex,
             time.time()),
        )
        self._eng._conn.commit()
        return tid

    def transition(
        self, memory_id: str, new_state: str, *,
        reason: Optional[str] = None, actor: str = "unknown",
        evidence: Optional[List[str]] = None, ctp_tx_id: Optional[str] = None,
        config_snapshot: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Apply a lifecycle transition if valid. Returns transition_id.

        Raises MemoryError_ if the memory is missing or the transition is
        not in VALID_TRANSITIONS. Never silently changes trust state.
        """
        mem = self._eng.get(memory_id)
        if mem is None:
            raise MemoryError_(f"memory_id not found: {memory_id}")
        previous = mem.lifecycle_state
        if new_state not in _valid_transitions_from(previous):
            raise MemoryError_(
                f"invalid transition: {previous} -> {new_state}")
        # update the memory's lifecycle_state column (NOT trust)
        meta = dict(mem.metadata)
        self._eng.update(memory_id, lifecycle_state=new_state, metadata=meta)
        return self._record_transition(
            memory_id, previous, new_state, reason=reason, actor=actor,
            evidence=evidence, ctp_tx_id=ctp_tx_id,
            config_snapshot=config_snapshot,
        )

    def transition_history(self, memory_id: str) -> List[Dict[str, Any]]:
        rows = self._eng._conn.execute(
            "SELECT * FROM memory_lifecycle_transitions WHERE memory_id=? "
            "ORDER BY created_at ASC", (memory_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["evidence"] = json.loads(r["evidence"])
            d["config_snapshot"] = json.loads(r["config_snapshot"])
            out.append(d)
        return out

    # ----- promotion --------------------------------------------------
    def evaluate_promotion(self, memory_id: str) -> PromotionEvaluation:
        mem = self._eng.get(memory_id)
        if mem is None:
            raise MemoryError_(f"memory_id not found: {memory_id}")
        meta = mem.metadata or {}
        current = mem.lifecycle_state
        trust = str(meta.get("trust_state", "observed_fact"))
        # eligible transitions from current state
        eligible = _valid_transitions_from(current)
        # disqualifying conflicts
        conflicts = self._eng.detect_conflicts(memory_id)
        disqualifying = [c["with"] for c in conflicts]
        # missing evidence assessment
        ev = set(meta.get("promotion_evidence", []) or [])
        missing: List[str] = []
        if not ev:
            missing.append("no_promotion_evidence_recorded")
        # user approval is required to reach pinned (never automatic)
        user_required = LifecycleState.PINNED.value in eligible
        # repetition alone is NOT evidence
        if "repetition_only" in ev:
            missing.append("repetition_is_not_evidence")
        return PromotionEvaluation(
            memory_id=memory_id,
            current_state=current,
            trust_state=trust,
            eligible_transitions=eligible,
            missing_evidence=missing,
            disqualifying_conflicts=disqualifying,
            confidence=mem.confidence,
            user_approval_required=user_required,
            reason="evaluation only; no state changed",
        )

    def promote(
        self, memory_id: str, target_state: str, *,
        reason: Optional[str] = None, actor: str = "unknown",
        evidence: Optional[List[str]] = None, ctp_tx_id: Optional[str] = None,
    ) -> str:
        """Promote a memory to a target lifecycle state.

        Promotion requires explicit evidence; repetition alone is rejected.
        Promotion to ``pinned`` requires user approval (actor == 'user' or
        an explicit user_approval evidence entry).
        """
        mem = self._eng.get(memory_id)
        if mem is None:
            raise MemoryError_(f"memory_id not found: {memory_id}")
        ev = list(evidence or [])
        meta = dict(mem.metadata)
        # validate evidence is a known kind
        unknown = [e for e in ev if e not in PROMOTION_EVIDENCE]
        if unknown:
            raise MemoryError_(f"unknown promotion evidence: {unknown}")
        # promotion requires at least one explicit evidence entry
        if not ev:
            raise MemoryError_("promotion requires at least one evidence entry")
        # repetition is never sufficient
        if ev == ["repetition_only"] or (len(ev) == 1 and ev[0] == "repetition_only"):
            raise MemoryError_("repetition alone cannot promote a memory")
        # pinned requires user approval (actor must be user)
        if target_state == LifecycleState.PINNED.value:
            if actor != "user":
                raise MemoryError_("pinned requires explicit user approval (actor='user')")
        # record evidence in metadata (does NOT change trust)
        meta["promotion_evidence"] = meta.get("promotion_evidence", []) + ev
        self._eng.update(memory_id, metadata=meta)
        return self.transition(
            memory_id, target_state, reason=reason, actor=actor,
            evidence=ev, ctp_tx_id=ctp_tx_id,
            config_snapshot={"promotion_evidence": ev},
        )

    def reject_candidate(
        self, memory_id: str, *, reason: Optional[str] = None,
        actor: str = "unknown", ctp_tx_id: Optional[str] = None,
    ) -> str:
        return self.transition(
            memory_id, LifecycleState.REJECTED.value, reason=reason,
            actor=actor, ctp_tx_id=ctp_tx_id)

    def pin(
        self, memory_id: str, *, reason: Optional[str] = None,
        actor: str = "user", ctp_tx_id: Optional[str] = None,
    ) -> str:
        """Pin a memory. Requires user actor (no automatic pinning)."""
        if actor != "user":
            raise MemoryError_("pinned requires explicit user approval (actor='user')")
        return self.transition(
            memory_id, LifecycleState.PINNED.value, reason=reason,
            actor=actor, ctp_tx_id=ctp_tx_id)

    # ----- decay / archive / restore --------------------------------
    def evaluate_decay(self, memory_id: str) -> Dict[str, Any]:
        """Return a deterministic decay assessment (ranking impact only).

        Decay affects retrieval priority, never erases canonical data.
        Protected records return ``protected=True`` and no decay is applied.
        """
        mem = self._eng.get(memory_id)
        if mem is None:
            raise MemoryError_(f"memory_id not found: {memory_id}")
        meta = mem.metadata or {}
        state = mem.lifecycle_state
        protected = state in PROTECTED_STATES
        age_days = (time.time() - mem.updated_at) / 86400.0
        # decay inputs
        inputs = {
            "age_days": round(age_days, 3),
            "has_retrieval": bool(meta.get("retrieval_count", 0) > 0),
            "explicit_irrelevance": bool(meta.get("irrelevance_flag")),
            "superseded": state == LifecycleState.SUPERSEDED.value,
            "resolved_task": bool(meta.get("task_resolved")),
            "namespace_inactive": bool(meta.get("namespace_inactive")),
            "stale_prospective": meta.get("tier") == MemoryTier.PROSPECTIVE.value
            and state == LifecycleState.EXPIRED.value,
            "archived_project": meta.get("tier") == MemoryTier.ARCHIVED.value,
        }
        # compute a bounded decay score in [0, 1]; 0 = no decay
        score = 0.0
        if not protected:
            if inputs["age_days"] > 180:
                score += min(0.4, (inputs["age_days"] - 180) / 1800.0)
            if not inputs["has_retrieval"]:
                score += 0.1
            if inputs["explicit_irrelevance"]:
                score += 0.3
            if inputs["superseded"]:
                score += 0.2
            if inputs["resolved_task"]:
                score += 0.1
            if inputs["namespace_inactive"]:
                score += 0.1
            if inputs["stale_prospective"]:
                score += 0.2
            if inputs["archived_project"]:
                score += 0.05
        score = round(min(1.0, score), 4)
        return {
            "memory_id": memory_id,
            "protected": protected,
            "decay_score": score,
            "decay_inputs": inputs,
            "note": "decay affects ranking only; canonical data is preserved",
        }

    def apply_decay(self, memory_id: str) -> Dict[str, Any]:
        """Apply decay as a ranking signal only (writes a decay_score into metadata).

        Never deletes or archives. Protected records are skipped.
        """
        assessment = self.evaluate_decay(memory_id)
        if assessment["protected"]:
            return {**assessment, "applied": False,
                    "reason": "protected record; decay not applied"}
        mem = self._eng.get(memory_id)
        meta = dict(mem.metadata)
        meta["decay_score"] = assessment["decay_score"]
        meta["last_decay_at"] = time.time()
        self._eng.update(memory_id, metadata=meta)
        return {**assessment, "applied": True}

    def archive(
        self, memory_id: str, *, reason: Optional[str] = None,
        actor: str = "unknown", ctp_tx_id: Optional[str] = None,
    ) -> str:
        """Archive a memory (preserved, excluded from active retrieval)."""
        return self.transition(
            memory_id, LifecycleState.ARCHIVED.value, reason=reason,
            actor=actor, ctp_tx_id=ctp_tx_id)

    def expire(
        self, memory_id: str, *, reason: Optional[str] = None,
        actor: str = "unknown", ctp_tx_id: Optional[str] = None,
    ) -> str:
        return self.transition(
            memory_id, LifecycleState.EXPIRED.value, reason=reason,
            actor=actor, ctp_tx_id=ctp_tx_id)

    def restore(
        self, memory_id: str, *, reason: Optional[str] = None,
        actor: str = "unknown", ctp_tx_id: Optional[str] = None,
    ) -> str:
        """Restore an archived/expired memory back to active."""
        mem = self._eng.get(memory_id)
        if mem is None:
            raise MemoryError_(f"memory_id not found: {memory_id}")
        if mem.lifecycle_state not in (
                LifecycleState.ARCHIVED.value, LifecycleState.EXPIRED.value):
            raise MemoryError_(
                f"restore only valid from archived/expired, not {mem.lifecycle_state}")
        return self.transition(
            memory_id, LifecycleState.ACTIVE.value, reason=reason,
            actor=actor, ctp_tx_id=ctp_tx_id)

    # ----- retention policies -----------------------------------------
    def set_retention_policy(
        self, namespace: str, retention_class: str, decay_rate: float = 0.0,
    ) -> None:
        if retention_class not in [c.value for c in RetentionClass]:
            raise MemoryError_(f"unknown retention class: {retention_class}")
        self._eng._conn.execute(
            """INSERT OR REPLACE INTO memory_retention_policies
               (namespace, retention_class, decay_rate) VALUES (?,?,?)""",
            (namespace, retention_class, decay_rate))
        self._eng._conn.commit()

    def get_retention_policy(self, namespace: str) -> Optional[Dict[str, Any]]:
        row = self._eng._conn.execute(
            "SELECT * FROM memory_retention_policies WHERE namespace=?",
            (namespace,)).fetchone()
        return dict(row) if row else None
