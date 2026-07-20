"""CAPT Solo v0.3 — Lifecycle Manager (KHSB events + CTP integration).

This module orchestrates consequential lifecycle operations so they are:
  * idempotent (CTP idempotency key)
  * recoverable (CTP receipt + rollback on failure)
  * audited (KHSB lifecycle events, idempotent handlers)
  * linked to affected records

KHSB remains transport-only; SQLite remains source of truth.
Handlers must be idempotent.

A failed lifecycle operation must NOT leave partial state: the
manager wraps each consequential op in a CTP transaction and
rolls back the lifecycle transition if a later step fails.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_, TransactionError
from capt_solo.ctp.journal import CTPRuntime
from capt_solo.khsb.bus import KHSB
from capt_solo.lifecycle.feedback import RetrievalFeedback
from capt_solo.lifecycle.lifecycle import LifecycleEngine, LifecycleState
from capt_solo.lifecycle.procedures import ProcedureStore
from capt_solo.lifecycle.prospective import ProspectiveStore
from capt_solo.lifecycle.sessions import SessionRuntime
from capt_solo.memory.engine import MemoryEngine


# KHSB lifecycle event topics (transport only).
EVENTS = [
    "session.started", "session.checkpointed", "session.interrupted",
    "session.resumed", "session.consolidation.requested",
    "session.consolidated", "session.closed",
    "memory.promotion.requested", "memory.promoted", "memory.demoted",
    "memory.archived", "memory.restored", "memory.expired",
    "procedure.created", "procedure.revised", "procedure.run.recorded",
    "prospective.created", "prospective.ready", "prospective.resolved",
    "retrieval.feedback.recorded", "retrieval.adaptation.updated",
]


class LifecycleManager:
    """Orchestrates consequential lifecycle ops with CTP + KHSB."""

    def __init__(
        self, engine: MemoryEngine,
        *, bus: Optional[KHSB] = None,
        ctp: Optional[CTPRuntime] = None,
    ) -> None:
        self._eng = engine
        self._bus = bus or KHSB()
        self._ctp = ctp or CTPRuntime()
        self._lc = LifecycleEngine(engine)
        self._sess = SessionRuntime(engine)
        self._proc = ProcedureStore(engine)
        self._prosp = ProspectiveStore(engine)
        self._fb = RetrievalFeedback(engine)

    # ----- CTP-wrapped consequential ops -------------------------
    def promote_with_ctp(
        self, memory_id: str, target_state: str, *,
        reason: Optional[str] = None, actor: str = "user",
        evidence: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Promote inside a CTP transaction; rollback on failure."""
        tx_id = self._ctp.begin(
            correlation_id=f"promote:{memory_id}:{target_state}",
            idempotency_key=idempotency_key or f"promote:{memory_id}:{target_state}",
            meta={"memory_id": memory_id, "target": target_state})
        try:
            self._bus.publish("memory.promotion.requested",
                              {"memory_id": memory_id, "target": target_state})
            tid = self._lc.promote(
                memory_id, target_state, reason=reason, actor=actor,
                evidence=evidence, ctp_tx_id=tx_id)
            self._bus.publish("memory.promoted",
                              {"memory_id": memory_id, "new_state": target_state,
                               "transition_id": tid})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "transition_id": tid,
                    "receipt": rcpt.to_dict()}
        except Exception as e:  # rollback: no partial lifecycle state
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            self._bus.publish("memory.demoted",
                              {"memory_id": memory_id, "reason": f"rollback: {e}"})
            raise

    def archive_with_ctp(
        self, memory_id: str, *, reason: Optional[str] = None,
        actor: str = "unknown",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"archive:{memory_id}",
            idempotency_key=idempotency_key or f"archive:{memory_id}",
            meta={"memory_id": memory_id})
        try:
            tid = self._lc.archive(memory_id, reason=reason, actor=actor,
                                   ctp_tx_id=tx_id)
            self._bus.publish("memory.archived",
                              {"memory_id": memory_id, "transition_id": tid})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "transition_id": tid, "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    def restore_with_ctp(
        self, memory_id: str, *, reason: Optional[str] = None,
        actor: str = "unknown",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"restore:{memory_id}",
            idempotency_key=idempotency_key or f"restore:{memory_id}",
            meta={"memory_id": memory_id})
        try:
            tid = self._lc.restore(memory_id, reason=reason, actor=actor,
                                   ctp_tx_id=tx_id)
            self._bus.publish("memory.restored",
                              {"memory_id": memory_id, "transition_id": tid})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "transition_id": tid, "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    def expire_with_ctp(
        self, memory_id: str, *, reason: Optional[str] = None,
        actor: str = "unknown",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"expire:{memory_id}",
            idempotency_key=idempotency_key or f"expire:{memory_id}",
            meta={"memory_id": memory_id})
        try:
            tid = self._lc.expire(memory_id, reason=reason, actor=actor,
                                  ctp_tx_id=tx_id)
            self._bus.publish("memory.expired",
                              {"memory_id": memory_id, "transition_id": tid})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "transition_id": tid, "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    def session_begin_with_ctp(
        self, project_namespace: str, *, objective: str = "",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"session.begin:{project_namespace}",
            idempotency_key=idempotency_key,
            meta={"namespace": project_namespace})
        try:
            sid = self._sess.begin(project_namespace, objective=objective,
                                  ctp_tx_id=tx_id)
            self._bus.publish("session.started",
                              {"session_id": sid, "namespace": project_namespace})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "session_id": sid, "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    def session_consolidate_with_ctp(
        self, session_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"session.consolidate:{session_id}",
            idempotency_key=idempotency_key,
            meta={"session_id": session_id})
        try:
            self._bus.publish("session.consolidation.requested",
                              {"session_id": session_id})
            cid = self._sess.consolidate(session_id, ctp_tx_id=tx_id)
            self._bus.publish("session.consolidated",
                              {"session_id": session_id,
                               "consolidation_id": cid})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "consolidation_id": cid,
                    "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    def procedure_create_with_ctp(
        self, name: str, *, namespace: str = "default",
        idempotency_key: Optional[str] = None, **kwargs,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"proc.create:{name}:{namespace}",
            idempotency_key=idempotency_key,
            meta={"name": name, "namespace": namespace})
        try:
            pid = self._proc.create(name, namespace=namespace,
                                   ctp_tx_id=tx_id, **kwargs)
            self._bus.publish("procedure.created",
                              {"procedure_id": pid, "name": name})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "procedure_id": pid,
                    "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    def prospective_create_with_ctp(
        self, description: str, *, kind: str = "task",
        namespace: str = "default",
        idempotency_key: Optional[str] = None, **kwargs,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"prosp.create:{kind}:{namespace}",
            idempotency_key=idempotency_key,
            meta={"kind": kind, "namespace": namespace})
        try:
            refs = list(kwargs.pop("ctp_refs", []) or [])
            refs.append(tx_id)
            iid = self._prosp.create(description, kind=kind,
                                  namespace=namespace,
                                  ctp_refs=refs, **kwargs)
            self._bus.publish("prospective.created",
                              {"intent_id": iid, "kind": kind})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "intent_id": iid,
                    "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    def prospective_resolve_with_ctp(
        self, intent_id: str, *,
        idempotency_key: Optional[str] = None, **kwargs,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"prosp.resolve:{intent_id}",
            idempotency_key=idempotency_key,
            meta={"intent_id": intent_id})
        try:
            ok = self._prosp.resolve(intent_id, **kwargs)
            self._bus.publish("prospective.resolved",
                              {"intent_id": intent_id, "ok": ok})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "resolved": ok,
                    "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    def feedback_with_ctp(
        self, feedback_kind: str, *,
        namespace: str = "default",
        idempotency_key: Optional[str] = None, **kwargs,
    ) -> Dict[str, Any]:
        tx_id = self._ctp.begin(
            correlation_id=f"feedback:{feedback_kind}:{namespace}",
            idempotency_key=idempotency_key,
            meta={"feedback_kind": feedback_kind})
        try:
            fid = self._fb.record(feedback_kind, namespace=namespace,
                                 **kwargs)
            self._bus.publish("retrieval.feedback.recorded",
                              {"feedback_id": fid, "kind": feedback_kind})
            self._bus.publish("retrieval.adaptation.updated",
                              {"namespace": namespace,
                               "state": self._fb.get_adaptation_state(namespace)})
            rcpt = self._ctp.commit(tx_id)
            return {"ok": True, "feedback_id": fid,
                    "receipt": rcpt.to_dict()}
        except Exception as e:
            try:
                self._ctp.abort(tx_id)
            except Exception:
                pass
            raise

    # ----- accessors (for plugin/tools) --------------------------
    @property
    def lifecycle(self) -> LifecycleEngine:
        return self._lc

    @property
    def sessions(self) -> SessionRuntime:
        return self._sess

    @property
    def procedures(self) -> ProcedureStore:
        return self._proc

    @property
    def prospective(self) -> ProspectiveStore:
        return self._prosp

    @property
    def feedback(self) -> RetrievalFeedback:
        return self._fb

    def close(self) -> None:
        self._ctp.close()
