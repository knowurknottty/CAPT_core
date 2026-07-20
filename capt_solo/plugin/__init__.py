"""CAPT Solo Hermes plugin.

Exposes ONLY stable public tools. No implementation internals leak into the
tool surface. Each tool is a thin wrapper over :mod:`capt_solo.api`.

Tool names (stable):
    capt_store_memory
    capt_search_memory
    capt_get_memory
    capt_begin_transaction
    capt_commit_transaction
    capt_abort_transaction
    capt_send_message
    capt_health
    capt_export_project
    capt_import_project
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from capt_solo.api import (
    CTPRuntime,
    KHSB,
    MemoryEngine,
    health,
)
from capt_solo.lifecycle.procedures import ProcedureStore
from capt_solo.foundry import (
    ProofEngine, CapabilityRegistry, ClaimGuard, SkillFoundry,
    ValidationHarness, KnowledgeBubbleRuntime,
)


class CaptSoloPlugin:
    """Hermes-facing plugin. Stateless wrappers over the public API."""

    def __init__(self) -> None:
        self._bus = KHSB()

    # ----- memory tools --------------------------------------------------
    def capt_store_memory(
        self,
        content: str,
        namespace: str = "default",
        tags: Optional[List[str]] = None,
        provenance: str = "hermes",
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            m = eng.store(
                content, namespace=namespace, tags=tags,
                provenance=provenance, confidence=confidence, metadata=metadata)
            return {"ok": True, "memory": m.to_dict()}
        finally:
            eng.close()

    def capt_search_memory(
        self, query: str, limit: int = 10,
        namespace: Optional[str] = None, tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            results = eng.search(query, limit=limit, namespace=namespace, tags=tags)
            return {"ok": True, "results": [m.to_dict() for m in results]}
        finally:
            eng.close()

    def capt_get_memory(self, memory_id: str) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            m = eng.get(memory_id)
            if m is None:
                return {"ok": False, "error": "not_found"}
            return {"ok": True, "memory": m.to_dict()}
        finally:
            eng.close()

    # ----- transaction tools --------------------------------------------
    def capt_begin_transaction(
        self, correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None, meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ctp = CTPRuntime()
        try:
            tx_id = ctp.begin(correlation_id=correlation_id,
                              idempotency_key=idempotency_key, meta=meta)
            return {"ok": True, "tx_id": tx_id}
        except Exception as e:  # surface as structured error
            return {"ok": False, "error": str(e)}
        finally:
            ctp.close()

    def capt_commit_transaction(self, tx_id: str) -> Dict[str, Any]:
        ctp = CTPRuntime()
        try:
            receipt = ctp.commit(tx_id)
            return {"ok": True, "receipt": receipt.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            ctp.close()

    def capt_abort_transaction(self, tx_id: str) -> Dict[str, Any]:
        ctp = CTPRuntime()
        try:
            receipt = ctp.abort(tx_id)
            return {"ok": True, "receipt": receipt.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            ctp.close()

    # ----- messaging tool ------------------------------------------------
    def capt_send_message(
        self, topic: str, payload: Any, correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        msg_id = self._bus.publish(topic, payload, correlation_id=correlation_id)
        return {"ok": True, "message_id": msg_id}

    # ----- health / project tools ---------------------------------------
    def capt_health(self) -> Dict[str, Any]:
        return health()

    def capt_export_project(self, path: Optional[str] = None) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            p = eng.export_json(Path(path) if path else None)
            return {"ok": True, "path": str(p)}
        finally:
            eng.close()

    def capt_import_project(self, path: str, merge: bool = True) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            n = eng.import_json(Path(path), merge=merge)
            return {"ok": True, "imported": n}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    # ----- v0.2 context-intelligence tools -----------------------------
    def capt_build_context(
        self, query: str = "", namespace: Optional[str] = None,
        tags: Optional[List[str]] = None, max_items: int = 10,
        char_budget: Optional[int] = None, token_budget: Optional[int] = None,
        include_superseded: bool = False, include_conflicts: bool = False,
        task_intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            from capt_solo.memory.context import build_context
            res = build_context(
                eng, query=query, namespace=namespace, tags=tags,
                max_items=max_items, char_budget=char_budget,
                token_budget=token_budget,
                include_superseded=include_superseded,
                include_conflicts=include_conflicts,
                task_intent=task_intent)
            return {"ok": True, "context": res.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_explain_context(self, query: str = "", namespace: Optional[str] = None,
                            max_items: int = 10) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            from capt_solo.memory.context import build_context
            from capt_solo.memory.csg import CSG
            res = build_context(eng, query=query, namespace=namespace, max_items=max_items)
            csg = CSG(eng._conn)
            explanations = [{"memory_id": i.memory_id, "decision": "selected",
                            "score": i.score, "reason": "selected by CSG weighted algorithm"}
                           for i in res.items]
            return {"ok": True, "explanation": csg.explain_selection(explanations)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_add_memory_relation(
        self, source: str, target: str, edge_type: str,
        weight: float = 1.0, confidence: float = 1.0,
        provenance: str = "hermes", ctp_tx_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            edge_id = eng.add_relation(
                source, target, edge_type, weight=weight,
                confidence=confidence, provenance=provenance, ctp_tx_id=ctp_tx_id)
            return {"ok": True, "edge_id": edge_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_detect_memory_conflicts(self, memory_id: str) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            conflicts = eng.detect_conflicts(memory_id)
            return {"ok": True, "conflicts": conflicts}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_review_memory_conflicts(self, unresolved_only: bool = True) -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            conflicts = eng.list_conflicts(unresolved_only=unresolved_only)
            return {"ok": True, "conflicts": conflicts}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_compress_memory(self, memory_id: str, format: str = "text") -> Dict[str, Any]:
        eng = MemoryEngine()
        try:
            mem = eng.get(memory_id)
            if mem is None:
                return {"ok": False, "error": "not_found"}
            from capt_solo.memory.antitoken import extract, render
            pkt = extract(mem.to_dict())
            return {"ok": True, "packet": pkt.to_dict(), "rendered": render(pkt, format)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    # ----- v0.3 lifecycle / sessions / procedures / prospective / feedback ---
    def capt_session_begin(self, project_namespace: str, *, objective: str = "") -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            r = mgr.session_begin_with_ctp(project_namespace, objective=objective)
            return {"ok": True, "session_id": r["session_id"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_session_checkpoint(
        self, session_id: str, *, objective: str = "", progress: str = "",
        latest_verified_result: str = "", current_hypothesis: str = "",
        pending_transaction: str = "", unresolved_failure: str = "",
        files_in_scope: Optional[List[str]] = None, next_action: str = "",
        safety_warning: str = "",
    ) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            cid = mgr.sessions.checkpoint(
                session_id, objective=objective, progress=progress,
                latest_verified_result=latest_verified_result,
                current_hypothesis=current_hypothesis,
                pending_transaction=pending_transaction,
                unresolved_failure=unresolved_failure,
                files_in_scope=files_in_scope, next_action=next_action,
                safety_warning=safety_warning)
            return {"ok": True, "checkpoint_id": cid}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_session_resume(self, session_id: str) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            pkt = mgr.sessions.resume(session_id)
            return {"ok": True, "restart_packet": pkt.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_session_status(self, session_id: str) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            return {"ok": True, "status": mgr.sessions.status(session_id)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_session_consolidate(self, session_id: str) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            r = mgr.session_consolidate_with_ctp(session_id)
            return {"ok": True, "consolidation_id": r["consolidation_id"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_session_close(self, session_id: str, *, outcome: str = "completed") -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            mgr.sessions.close(session_id, outcome=outcome)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_promote_memory(
        self, memory_id: str, target_state: str, *, reason: Optional[str] = None,
        actor: str = "user", evidence: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            r = mgr.promote_with_ctp(memory_id, target_state, reason=reason,
                                    actor=actor, evidence=evidence)
            return {"ok": True, "transition_id": r["transition_id"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_archive_memory(self, memory_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            r = mgr.archive_with_ctp(memory_id, reason=reason)
            return {"ok": True, "transition_id": r["transition_id"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_pin_memory(self, memory_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            tid = mgr.lifecycle.pin(memory_id, reason=reason)
            return {"ok": True, "transition_id": tid}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_explain_memory_lifecycle(self, memory_id: str) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            hist = mgr.lifecycle.transition_history(memory_id)
            ev = mgr.lifecycle.evaluate_promotion(memory_id)
            return {"ok": True, "transition_history": hist,
                    "promotion_evaluation": ev.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_create_procedure(
        self, name: str, *, trigger: str = "", purpose: str = "",
        steps: str = "", verification: str = "", namespace: str = "default",
        preconditions: str = "", inputs: str = "", expected_outputs: str = "",
        failure_modes: str = "", recovery_steps: str = "",
        evidence_refs: Optional[List[str]] = None,
        artifact_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            r = mgr.procedure_create_with_ctp(
                name, trigger=trigger, purpose=purpose, steps=steps,
                verification=verification, namespace=namespace,
                preconditions=preconditions, inputs=inputs,
                expected_outputs=expected_outputs, failure_modes=failure_modes,
                recovery_steps=recovery_steps,
                evidence_refs=evidence_refs, artifact_refs=artifact_refs)
            return {"ok": True, "procedure_id": r["procedure_id"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_get_procedure(self, procedure_id: str) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            p = mgr.procedures.get(procedure_id)
            if p is None:
                return {"ok": False, "error": "not_found"}
            return {"ok": True, "procedure": p.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_record_procedure_run(
        self, procedure_id: str, *, outcome: str, version_used: Optional[int] = None,
        inputs: str = "", verification_result: str = "",
        failure_reason: str = "", ctp_ref: Optional[str] = None,
        session_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            rid = mgr.procedures.record_run(
                procedure_id, outcome=outcome, version_used=version_used,
                inputs=inputs, verification_result=verification_result,
                failure_reason=failure_reason, ctp_ref=ctp_ref,
                session_ref=session_ref)
            return {"ok": True, "run_id": rid}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_find_procedures(self, *, namespace: Optional[str] = None,
                            lifecycle_state: Optional[str] = None) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            procs = mgr.procedures.list(namespace=namespace,
                                        lifecycle_state=lifecycle_state)
            return {"ok": True, "procedures": [p.to_dict() for p in procs]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_add_prospective_memory(
        self, description: str, *, kind: str = "task", namespace: str = "default",
        priority: str = "normal", source_session: Optional[str] = None,
        source_memory: Optional[str] = None, prerequisites: Optional[List[str]] = None,
        blocking_conditions: Optional[List[str]] = None, target_condition: str = "",
        due_date: Optional[float] = None, retry_after: str = "",
        evidence: str = "", ctp_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            r = mgr.prospective_create_with_ctp(
                description, kind=kind, namespace=namespace, priority=priority,
                source_session=source_session, source_memory=source_memory,
                prerequisites=prerequisites, blocking_conditions=blocking_conditions,
                target_condition=target_condition, due_date=due_date,
                retry_after=retry_after, evidence=evidence, ctp_refs=ctp_refs)
            return {"ok": True, "intent_id": r["intent_id"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_list_pending_intents(self, *, namespace: Optional[str] = None) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            intents = mgr.prospective.list(namespace=namespace, status="pending")
            return {"ok": True, "intents": [i.to_dict() for i in intents]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_resolve_intent(self, intent_id: str, *, reason: str = "") -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            r = mgr.prospective_resolve_with_ctp(intent_id, reason=reason)
            return {"ok": True, "resolved": r["resolved"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_record_retrieval_feedback(
        self, feedback_kind: str, *, memory_id: Optional[str] = None,
        query: str = "", reason: str = "", namespace: str = "default",
    ) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            r = mgr.feedback_with_ctp(
                feedback_kind, memory_id=memory_id, query=query,
                reason=reason, namespace=namespace)
            return {"ok": True, "feedback_id": r["feedback_id"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_get_restart_context(self, session_id: str, *, budget: Optional[int] = None) -> Dict[str, Any]:
        from capt_solo.lifecycle.manager import LifecycleManager
        from capt_solo.khsb.bus import KHSB
        from capt_solo.ctp.journal import CTPRuntime
        eng = MemoryEngine()
        try:
            mgr = LifecycleManager(eng, bus=KHSB(), ctp=CTPRuntime())
            pkt = mgr.sessions.build_restart_packet(session_id, budget=budget)
            return {"ok": True, "restart_packet": pkt.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()


    def capt_memory_pipeline_status(self) -> Dict[str, Any]:
        """Return CSG graph + conflict status (v0.2 compatibility)."""
        eng = MemoryEngine()
        try:
            from capt_solo.memory.csg import CSG
            csg = CSG(eng._conn)
            edges = eng._conn.execute("SELECT COUNT(*) AS c FROM memory_edges").fetchone()["c"]
            nodes = eng._conn.execute("SELECT COUNT(*) AS c FROM memory_nodes").fetchone()["c"]
            conflicts = eng._conn.execute(
                "SELECT COUNT(*) AS c FROM memory_conflicts WHERE resolved=0").fetchone()["c"]
            return {
                "ok": True,
                "graph_nodes": nodes,
                "graph_edges": edges,
                "unresolved_conflicts": conflicts,
                "csg_weights": csg.get_weights(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    # ----- v0.4 foundry tools ------------------------------------------
    def capt_generate_skill(self, procedure_id: str, name: str = "",
                           verification_requirements: Optional[List[Dict]] = None,
                           permissions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate a skill candidate from a verified procedure."""
        try:
            eng = MemoryEngine()
            ps = ProcedureStore(eng)
            pe = ProofEngine(eng._conn)
            sf = SkillFoundry(eng._conn, pe, ps)
            cid = sf.create_candidate(procedure_id)
            sid = sf.build_skill(
                cid, name=name, permissions=permissions or [],
                verification_requirements=verification_requirements or [])
            return {"ok": True, "skill_id": sid, "candidate_id": cid}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_validate_skill(self, skill_id: str) -> Dict[str, Any]:
        """Run the 12-stage validation harness against a skill."""
        try:
            eng = MemoryEngine()
            pe = ProofEngine(eng._conn)
            sf = SkillFoundry(eng._conn, pe, ProcedureStore(eng))
            rep = sf.validate(skill_id, ValidationHarness(pe))
            return {"ok": True, **rep.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_publish_skill(self, skill_id: str, reviewer: str = "hermes",
                           ctp_tx_id: Optional[str] = None) -> Dict[str, Any]:
        """Approve + publish a skill through the governed pipeline."""
        try:
            eng = MemoryEngine()
            pe = ProofEngine(eng._conn)
            sf = SkillFoundry(eng._conn, pe, ProcedureStore(eng))
            sf.submit_for_review(skill_id)
            sf.approve(skill_id, reviewer=reviewer)
            sf.publish(skill_id, ctp_tx_id=ctp_tx_id)
            return {"ok": True, "lifecycle": "published"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_query_capability(self, identifier: str) -> Dict[str, Any]:
        """Query the capability registry for a single capability."""
        try:
            eng = MemoryEngine()
            pe = ProofEngine(eng._conn)
            reg = CapabilityRegistry(eng._conn, pe)
            cap = reg.get(identifier)
            if cap is None:
                return {"ok": False, "error": f"capability not found: {identifier}"}
            return {"ok": True, **cap.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_verify_claim(self, claim_text: str, capability_id: Optional[str] = None,
                          scope: str = "default") -> Dict[str, Any]:
        """Validate a completion claim against proof before reporting it."""
        try:
            eng = MemoryEngine()
            pe = ProofEngine(eng._conn)
            reg = CapabilityRegistry(eng._conn, pe)
            cg = ClaimGuard(reg, pe)
            v = cg.verify_claim(claim_text, capability_id=capability_id)
            return {"ok": True, **v.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_build_bubble(self, name: str, skills: Optional[List[Dict]] = None,
                          procedures: Optional[List[Dict]] = None,
                          proof: Optional[List[Dict]] = None,
                          trust_metadata: Optional[Dict] = None,
                          compatibility: str = "") -> Dict[str, Any]:
        """Build a knowledge bubble manifest (not yet imported)."""
        try:
            bubble = KnowledgeBubbleRuntime.build_bubble(
                name, skills=skills or [], procedures=procedures or [],
                proof=proof or [], trust_metadata=trust_metadata or {},
                compatibility=compatibility)
            return {"ok": True, "bubble": bubble}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def capt_validate_bubble(self, bubble: Dict[str, Any]) -> Dict[str, Any]:
        """Import (quarantined) + validate a bubble manifest."""
        try:
            eng = MemoryEngine()
            kb = KnowledgeBubbleRuntime(eng._conn)
            bid = kb.import_bubble(bubble)
            rep = kb.validate_bubble(bid)
            return {"ok": True, "bubble_id": bid, **rep.to_dict()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_install_bubble(self, bubble: Dict[str, Any],
                            approver: str = "hermes",
                            ctp_tx_id: Optional[str] = None) -> Dict[str, Any]:
        """Approve + install a bubble through the governed pipeline."""
        try:
            eng = MemoryEngine()
            kb = KnowledgeBubbleRuntime(eng._conn)
            bid = kb.import_bubble(bubble)
            kb.validate_bubble(bid)
            kb.approve_bubble(bid, approver)
            res = kb.install_bubble(bid, ctp_tx_id=ctp_tx_id)
            return {"ok": True, **res}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_export_bubble(self, skills: Optional[List[str]] = None,
                           procedures: Optional[List[str]] = None,
                           include_private: bool = False) -> Dict[str, Any]:
        """Export selected skills/procedures as a bubble (private excluded by default)."""
        try:
            eng = MemoryEngine()
            kb = KnowledgeBubbleRuntime(eng._conn)
            bubble = kb.export_selected(
                skills=skills or [], procedures=procedures or [],
                include_private=include_private)
            return {"ok": True, "bubble": bubble}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()

    def capt_inspect_proof(self, scope: str) -> Dict[str, Any]:
        """Inspect proof evidence and aggregate for a scope."""
        try:
            eng = MemoryEngine()
            pe = ProofEngine(eng._conn)
            evs = pe.list_by_scope(scope)
            agg = pe.aggregate(scope)
            return {
                "ok": True,
                "scope": scope,
                "evidence_count": len(evs),
                "aggregate": agg.to_dict(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            eng.close()


# Tool registry — Hermes discovers tools from this mapping.
TOOLS = {
    "capt_store_memory": CaptSoloPlugin.capt_store_memory,
    "capt_search_memory": CaptSoloPlugin.capt_search_memory,
    "capt_get_memory": CaptSoloPlugin.capt_get_memory,
    "capt_begin_transaction": CaptSoloPlugin.capt_begin_transaction,
    "capt_commit_transaction": CaptSoloPlugin.capt_commit_transaction,
    "capt_abort_transaction": CaptSoloPlugin.capt_abort_transaction,
    "capt_send_message": CaptSoloPlugin.capt_send_message,
    "capt_health": CaptSoloPlugin.capt_health,
    "capt_export_project": CaptSoloPlugin.capt_export_project,
    "capt_import_project": CaptSoloPlugin.capt_import_project,
    # v0.2 context-intelligence tools
    "capt_build_context": CaptSoloPlugin.capt_build_context,
    "capt_explain_context": CaptSoloPlugin.capt_explain_context,
    "capt_add_memory_relation": CaptSoloPlugin.capt_add_memory_relation,
    "capt_detect_memory_conflicts": CaptSoloPlugin.capt_detect_memory_conflicts,
    "capt_review_memory_conflicts": CaptSoloPlugin.capt_review_memory_conflicts,
    "capt_compress_memory": CaptSoloPlugin.capt_compress_memory,
    "capt_memory_pipeline_status": CaptSoloPlugin.capt_memory_pipeline_status,
    # v0.3 adaptive lifecycle / session / procedure / prospective / feedback tools
    "capt_session_begin": CaptSoloPlugin.capt_session_begin,
    "capt_session_checkpoint": CaptSoloPlugin.capt_session_checkpoint,
    "capt_session_resume": CaptSoloPlugin.capt_session_resume,
    "capt_session_status": CaptSoloPlugin.capt_session_status,
    "capt_session_consolidate": CaptSoloPlugin.capt_session_consolidate,
    "capt_session_close": CaptSoloPlugin.capt_session_close,
    "capt_promote_memory": CaptSoloPlugin.capt_promote_memory,
    "capt_archive_memory": CaptSoloPlugin.capt_archive_memory,
    "capt_pin_memory": CaptSoloPlugin.capt_pin_memory,
    "capt_explain_memory_lifecycle": CaptSoloPlugin.capt_explain_memory_lifecycle,
    "capt_create_procedure": CaptSoloPlugin.capt_create_procedure,
    "capt_get_procedure": CaptSoloPlugin.capt_get_procedure,
    "capt_record_procedure_run": CaptSoloPlugin.capt_record_procedure_run,
    "capt_find_procedures": CaptSoloPlugin.capt_find_procedures,
    "capt_add_prospective_memory": CaptSoloPlugin.capt_add_prospective_memory,
    "capt_list_pending_intents": CaptSoloPlugin.capt_list_pending_intents,
    "capt_resolve_intent": CaptSoloPlugin.capt_resolve_intent,
    "capt_record_retrieval_feedback": CaptSoloPlugin.capt_record_retrieval_feedback,
    "capt_get_restart_context": CaptSoloPlugin.capt_get_restart_context,
    # v0.4 foundry tools
    "capt_generate_skill": CaptSoloPlugin.capt_generate_skill,
    "capt_validate_skill": CaptSoloPlugin.capt_validate_skill,
    "capt_publish_skill": CaptSoloPlugin.capt_publish_skill,
    "capt_query_capability": CaptSoloPlugin.capt_query_capability,
    "capt_verify_claim": CaptSoloPlugin.capt_verify_claim,
    "capt_build_bubble": CaptSoloPlugin.capt_build_bubble,
    "capt_validate_bubble": CaptSoloPlugin.capt_validate_bubble,
    "capt_install_bubble": CaptSoloPlugin.capt_install_bubble,
    "capt_export_bubble": CaptSoloPlugin.capt_export_bubble,
    "capt_inspect_proof": CaptSoloPlugin.capt_inspect_proof,
}


def get_plugin() -> CaptSoloPlugin:
    return CaptSoloPlugin()


def tool_names() -> List[str]:
    return list(TOOLS.keys())
