"""CAPT Solo canonical composition root (Outcome B).

Single ownership contract: every production runtime component is constructed
exactly once, here, inside :class:`CAPTRuntime`. ``CAPTRuntime.load()`` is the
only sanctioned production construction site (see RUNTIME_OWNERSHIP_MATRIX.md).
Consumers must not construct MemoryEngine / KHSB / CTPRuntime /
LifecycleManager / CapabilityRegistry / ProofEngine / ClaimGuard on their own.

Consequential execution flows through :meth:`CAPTRuntime.execute`, which is
guarded by :class:`MemoryUseGate` (MANDATORY — a non-PASS ContextPack
validation refuses execution with :class:`GateDeniedError`).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from capt_solo.core.config import ctp_journal_dir, data_dir, home_dir, memory_db_path
from capt_solo.core.errors import CaptSoloError
from capt_solo.ctp.journal import CTPRuntime
from capt_solo.khsb.bus import KHSB
from capt_solo.memory.engine import MemoryEngine
from capt_solo.lifecycle.manager import LifecycleManager
from capt_solo.foundry import CapabilityRegistry, ClaimGuard, ProofEngine
from capt_solo.contextpack.core import (
    Assumption,
    Mission,
    MissionIntent,
    RecordRef,
    TokenBudget,
    build_context_pack,
    validate_context_pack,
)
from capt_solo.model_task import ModelTaskRequest

__all__ = [
    "CAPTRuntime",
    "GateDecision",
    "GateDeniedError",
    "MemoryUseGate",
    "PreparedModelTurn",
    "normalize_selection_ids",
    "RuntimeConfiguration",
]

# Topics the durable event log persists (LifecycleManager emits + runtime emits).
_DURABLE_TOPICS = (
    # LifecycleManager consequential-op events
    "memory.promotion.requested",
    "memory.promoted",
    "memory.demoted",
    "memory.archived",
    "memory.restored",
    "memory.expired",
    "session.started",
    "session.consolidation.requested",
    "session.consolidated",
    "procedure.created",
    "prospective.created",
    "prospective.resolved",
    "retrieval.feedback.recorded",
    "retrieval.adaptation.updated",
    # Runtime mission events
    "mission.operation.started",
    "mission.operation.completed",
    "mission.operation.failed",
    "mission.checkpoint.written",
    # Model-task events
    "model-task.started",
    "model-task.completed",
    "model-task.failed",
    # Plugin governance events (Hermes adapter translates host events here)
    "tool.intent",
    "tool.executed",
    # CAPT Agent Runner (ADR-0001, Outcome C) — durable boot/turn lifecycle
    "agent.boot.requested",
    "agent.boot.memory_retrieved",
    "agent.boot.context_validated",
    "agent.boot.completed",
    "agent.boot.failed",
    "agent.turn.started",
    "agent.checkpointed",
    "agent.resumed",
    "agent.session.completed",
    "agent.session.failed",
)

_SELECTION_KINDS = ("selected", "rejected", "stale", "missing", "conflicting")


class GateDeniedError(CaptSoloError):
    """MemoryUseGate refused execution: ContextPack validation did not PASS."""


@dataclass
class GateDecision:
    """Outcome of the mandatory pre-execution gate."""

    allowed: bool
    pack: Any = None
    validation: Any = None
    retrieved: Dict[str, List[Any]] = field(default_factory=dict)

    @property
    def block_codes(self) -> List[str]:
        if self.validation is None:
            return []
        return [b.code for b in self.validation.blocks]


@dataclass
class PreparedModelTurn:
    """Handle returned by ``CAPTRuntime.prepare_external_model_turn``.

    Carries everything the Hermes plugin needs to (a) inject the governed CAPT
    context into the Hermes user message and (b) commit/abort the matching CTP
    transaction in ``post_llm_call``. CAPTRuntime remains the owner of all
    governance state; this is a thin, read-only hand-off object.

    ``selection_ids`` uses LIST semantics per category (zero or more records),
    matching ``MemoryUseGate.retrieve``. A migration reader
    (:func:`normalize_selection_ids`) accepts legacy scalar values.
    """

    turn_id: str
    ctp_tx_id: str
    session_id: str
    correlation_id: str
    contextpack_digest: str
    gate_allowed: bool
    rendered_context: str
    memory_use_decision_id: str
    selection_ids: Dict[str, List[str]] = field(default_factory=dict)
    mission_id: str = "default"
    namespace: str = "capt-solo"
    provider_owner: str = "hermes"


def normalize_selection_ids(raw: Any) -> Dict[str, List[str]]:
    """Coerce selection_ids into the canonical list-valued schema.

    Accepts:
      * dict[kind -> list[str]]  (canonical)
      * dict[kind -> str]        (legacy scalar — wrapped in a single-element list)
      * None                      (empty collections)
    Unknown categories are dropped; only ``_SELECTION_KINDS`` are kept.
    """
    out: Dict[str, List[str]] = {k: [] for k in _SELECTION_KINDS}
    if not raw:
        return out
    if not isinstance(raw, dict):
        return out
    for kind in _SELECTION_KINDS:
        v = raw.get(kind)
        if v is None:
            continue
        if isinstance(v, str):
            out[kind] = [v]
        elif isinstance(v, (list, tuple)):
            out[kind] = [str(x) for x in v]
    return out


@dataclass
class RuntimeConfiguration:
    """Persistent configuration resolved by the composition root.

    ``None`` fields fall back to CAPT_SOLO_HOME-derived defaults at
    construction time, so an isolated ``CAPT_SOLO_HOME`` is honored without
    extra plumbing.
    """

    home: Optional[Path] = None
    db_path: Optional[Path] = None
    journal_dir: Optional[Path] = None
    evidence_dir: Optional[Path] = None
    event_log_path: Optional[Path] = None
    mission_id: str = "default"

    @classmethod
    def from_env(cls) -> "RuntimeConfiguration":
        h = home_dir()
        return cls(
            home=h,
            db_path=memory_db_path(),
            journal_dir=ctp_journal_dir(),
            evidence_dir=data_dir() / "evidence",
            event_log_path=data_dir() / "khsb" / "events.jsonl",
        )


def _record_digest(embedded: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(embedded, sort_keys=True, default=str).encode()
    ).hexdigest()


def _default_token_budget(rendered: str) -> TokenBudget:
    est = max(2000, len(rendered) // 4)
    return TokenBudget(
        maximum_input_tokens=16000,
        reserved_output_tokens=2000,
        available_input_tokens=16000,
        estimated_input_tokens=est,
        remaining_tokens=16000 - est,
        tokenizer_id="approx-chars/4",
        estimation_method="heuristic",
        measurement_status="estimated",
    )


class MemoryUseGate:
    """Mandatory pre-execution gate: memory retrieval + ContextPack validation.

    Consequential execution is refused (``GateDeniedError``) when ContextPack
    validation does not PASS. Selection records (selected / rejected / stale /
    missing / conflicting) are stored with mission tags, then re-read from the
    engine before the pack is built — so retrieval demonstrably happens before
    execution, by construction.
    """

    def __init__(
        self,
        engine: MemoryEngine,
        *,
        ctp: Optional[CTPRuntime] = None,
        bus: Optional[KHSB] = None,
    ) -> None:
        self._eng = engine
        self._ctp = ctp
        self._bus = bus
        self._namespace = "capt-solo"

    # ----- record selection / retrieval --------------------------------
    def record_selection(
        self,
        mission_id: str,
        objective: str,
        *,
        records: Dict[str, str],
        namespace: str = "capt-solo",
    ) -> Dict[str, str]:
        """Persist each selection kind with mission tags; return kind→memory_id."""
        ids: Dict[str, str] = {}
        for kind, content in records.items():
            if kind not in _SELECTION_KINDS:
                continue
            m = self._eng.store(
                content,
                namespace=namespace,
                tags=["mission:" + mission_id, "selection:" + kind],
                provenance="memory-use-gate",
                confidence=0.95,
                metadata={
                    "mission_id": mission_id,
                    "selection_kind": kind,
                    "objective": objective,
                },
            )
            ids[kind] = m.memory_id
        return ids

    def retrieve(
        self, mission_id: str, *, namespace: str = "capt-solo", limit: int = 200
    ) -> Dict[str, List[Any]]:
        out: Dict[str, List[Any]] = {k: [] for k in _SELECTION_KINDS}
        for m in self._eng.list(
            namespace=namespace, tags=["mission:" + mission_id], limit=limit
        ):
            kind = None
            for tag in m.tags:
                if tag.startswith("selection:"):
                    kind = tag.split(":", 1)[1]
                    break
            if kind in out:
                out[kind].append(m)
        return out

    # ----- ContextPack build + validate --------------------------------
    def prepare(
        self,
        mission_id: str,
        objective: str,
        *,
        intent: MissionIntent,
        assumptions: Sequence[Assumption],
        evidence: Sequence[RecordRef],
        invariants: Sequence[RecordRef],
        rendered_context: str,
        token_budget: Optional[TokenBudget] = None,
        confidence: float = 0.9,
        namespace: str = "capt-solo",
    ) -> GateDecision:
        """Retrieve mission records, build + validate the ContextPack.

        Returns a decision; the caller must refuse execution when
        ``decision.allowed`` is False (mandatory, not advisory).
        """
        retrieved = self.retrieve(mission_id, namespace=namespace)
        memory_refs = []
        for kind, items in retrieved.items():
            for m in items:
                memory_refs.append(
                    RecordRef(
                        "memory:" + m.memory_id,
                        _record_digest({"memory_id": m.memory_id, "selection_kind": kind}),
                        "memory-use-gate",
                        {"memory_id": m.memory_id, "selection_kind": kind},
                    )
                )
        mission = Mission(mission_id, objective, ())
        pack = build_context_pack(
            mission,
            intent,
            assumptions,
            invariants=tuple(invariants),
            evidence=tuple(evidence),
            memory=tuple(memory_refs),
            receipts=(),
            rendered_context=rendered_context,
            token_budget=token_budget or _default_token_budget(rendered_context),
            evaluation_clock=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            confidence=confidence,
            assumption_review_status="reviewed",
            protected_fact_review_status="reviewed",
        )
        validation = validate_context_pack(pack)
        return GateDecision(
            allowed=validation.status == "PASS",
            pack=pack,
            validation=validation,
            retrieved=retrieved,
        )


class _DurableEventLog:
    """Real KHSB consumer: appends typed events to JSONL, dedupes by message_id.

    Idempotent delivery: message_ids seen in a previous process (or duplicate
    publishes within this one) are not appended twice.
    """

    def __init__(self, bus: KHSB, path: Path, topics: Sequence[str]) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = threading.Lock()
        self._seen: set = set()
        if self._path.exists():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                try:
                    self._seen.add(json.loads(line)["message_id"])
                except Exception:
                    continue
        self._subscriptions = [
            bus.subscribe(t, self._handle) for t in topics
        ]

    def _handle(self, message: Any) -> None:
        rec = {
            "message_id": message.message_id,
            "topic": message.topic,
            "payload": message.payload,
            "correlation_id": message.correlation_id,
            "type": message.type,
            "ts": message.ts,
        }
        with self._lock:
            if rec["message_id"] in self._seen:
                return
            self._seen.add(rec["message_id"])
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str) + "\n")

    @property
    def path(self) -> Path:
        return self._path

    @property
    def count(self) -> int:
        return len(self._seen)


class CAPTRuntime:
    """Single canonical composition root.

    Owns every runtime component for its lifetime. The only production
    construction site; use :meth:`load` (or construct directly with an optional
    :class:`RuntimeConfiguration`).
    """

    def __init__(self, configuration: Optional[RuntimeConfiguration] = None) -> None:
        self.config = configuration or RuntimeConfiguration.from_env()
        self.runtime_id = uuid.uuid4().hex
        self.engine = MemoryEngine(db_path=self.config.db_path)
        self.ctp = CTPRuntime(journal_dir=self.config.journal_dir)
        self.bus = KHSB()
        self.lifecycle = LifecycleManager(self.engine, bus=self.bus, ctp=self.ctp)
        self.proof = ProofEngine(self.engine._conn)
        self.registry = CapabilityRegistry(self.engine._conn, self.proof)
        self.claimguard = ClaimGuard(self.registry, self.proof)
        self.gate = MemoryUseGate(self.engine, ctp=self.ctp, bus=self.bus)
        self.events = _DurableEventLog(
            self.bus,
            self.config.event_log_path or (data_dir() / "khsb" / "events.jsonl"),
            _DURABLE_TOPICS,
        )
        # Runtime identity is recorded in every CTP transaction meta.
        self._identity_meta = {
            "runtime_id": self.runtime_id,
            "mission_id": self.config.mission_id,
        }
        # In-process cache of prepared external model turns, keyed by turn_id,
        # so a repeated pre_llm_call for the same turn (e.g. API retry) reuses
        # the existing CTP transaction instead of opening a duplicate.
        self._prepared_turns: Dict[str, PreparedModelTurn] = {}

    @classmethod
    def load(cls, configuration: Optional[RuntimeConfiguration] = None) -> "CAPTRuntime":
        return cls(configuration)

    # ----- governed execution -----------------------------------------
    def execute(
        self,
        operation: Callable[["CAPTRuntime"], Any],
        *,
        mission_id: str,
        objective: str,
        capability_id: Optional[str] = None,
        records: Optional[Dict[str, str]] = None,
        intent: Optional[MissionIntent] = None,
        assumptions: Sequence[Assumption] = (),
        evidence: Sequence[RecordRef] = (),
        invariants: Sequence[RecordRef] = (),
        rendered_context: str = "",
        token_budget: Optional[TokenBudget] = None,
        session_id: Optional[str] = None,
        namespace: str = "capt-solo",
        claim_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a governed operation under the canonical composition.

        Order (see RUNTIME_OWNERSHIP_MATRIX.md):
          1. record selection kinds (selected/rejected/stale/missing/conflicting)
          2. MemoryUseGate: retrieve records + build + validate ContextPack
             BEFORE execution — refuse (GateDeniedError) on non-PASS
          3. session (begin or reuse), CTP begin, publish started event
          4. run operation
          5. evaluate claim through ClaimGuard (when capability_id given)
          6. write lifecycle checkpoint; commit CTP; publish completed event
             ONLY after commit (no completion event contradicts CTP state)
          7. on failure: abort CTP, publish failed event, re-raise
        """
        records = records or {}
        if not rendered_context:
            rendered_context = f"MISSION {mission_id} objective={objective}"
        if intent is None:
            intent = MissionIntent(
                purpose=objective,
                priority="critical",
                tradeoffs=("governance strictness", "speed"),
                success_definition="operation completes inside a committed CTP transaction",
                safety_constraints=("no ungoverned execution",),
            )

        # 1. record selection kinds
        selection_ids = self.gate.record_selection(
            mission_id, objective, records=records, namespace=namespace
        )

        # 2. mandatory gate — retrieval + ContextPack validation BEFORE execution
        decision = self.gate.prepare(
            mission_id,
            objective,
            intent=intent,
            assumptions=assumptions,
            evidence=evidence,
            invariants=invariants,
            rendered_context=rendered_context,
            token_budget=token_budget,
            namespace=namespace,
        )
        if not decision.allowed:
            raise GateDeniedError(
                f"ContextPack validation {decision.validation.status} for mission "
                f"{mission_id}: {', '.join(decision.block_codes)}"
            )

        # 3. session + transaction
        sid = session_id or self.lifecycle.sessions.begin(
            namespace, objective=objective
        )
        tx = self.ctp.begin(
            correlation_id=f"mission:{mission_id}",
            idempotency_key=f"mission-execute:{mission_id}:"
            f"{hashlib.sha256(objective.encode()).hexdigest()[:12]}",
            meta={**self._identity_meta, "session_id": sid, "objective": objective},
        )
        self.bus.publish(
            "mission.operation.started",
            {"mission_id": mission_id, "session_id": sid, "tx_id": tx},
            correlation_id=tx,
        )

        try:
            # 4. run the operation
            op_result = operation(self)

            # 5. claim evaluation through ClaimGuard
            verdict = None
            if capability_id is not None:
                claim_text = claim_text or f"{objective} complete and verified."
                verdict = self.claimguard.verify_claim(
                    claim_text, capability_id=capability_id
                )

            # 6. checkpoint + commit; completion event only after commit
            ckpt_id = self.lifecycle.sessions.checkpoint(
                sid,
                objective=objective,
                progress="governed operation completed",
                latest_verified_result=str(op_result)[:500],
                pending_transaction=tx,
                ctp_tx_id=tx,
            )
            self.bus.publish(
                "mission.checkpoint.written",
                {"checkpoint_id": ckpt_id, "session_id": sid, "tx_id": tx},
                correlation_id=tx,
            )
            rcpt = self.ctp.commit(tx)
            self.bus.publish(
                "mission.operation.completed",
                {
                    "mission_id": mission_id,
                    "session_id": sid,
                    "tx_id": tx,
                    "checkpoint_id": ckpt_id,
                    "receipt_status": rcpt.status,
                },
                correlation_id=tx,
            )

            result = {
                "ok": True,
                "mission_id": mission_id,
                "session_id": sid,
                "tx_id": tx,
                "receipt": rcpt.to_dict(),
                "checkpoint_id": ckpt_id,
                "runtime_id": self.runtime_id,
                "operation_result": op_result,
                "claim_verdict": verdict.to_dict() if verdict is not None else None,
                "selection_ids": selection_ids,
                "retrieved_counts": {
                    k: len(v) for k, v in decision.retrieved.items()
                },
                "contextpack": {
                    "digest": decision.pack.digest,
                    "validation": decision.validation.status,
                },
                "event_log": str(self.events.path),
                "events_persisted": self.events.count,
            }
            result["evidence_path"] = str(self._write_evidence(result))
            return result

        except Exception:
            # 7. abort + failed event — NO completion event
            try:
                self.ctp.abort(tx)
            except Exception:
                pass
            self.bus.publish(
                "mission.operation.failed",
                {"mission_id": mission_id, "session_id": sid, "tx_id": tx},
                correlation_id=tx,
            )
            raise

    def execute_model_task(
        self,
        *,
        task_id: str,
        mission_id: str,
        objective: str,
        provider: Any,
        user_prompt: str = "",
        capability_id: Optional[str] = None,
        records: Optional[Dict[str, str]] = None,
        intent: Optional[MissionIntent] = None,
        assumptions: Sequence[Assumption] = (),
        evidence: Sequence[RecordRef] = (),
        invariants: Sequence[RecordRef] = (),
        rendered_context: str = "",
        token_budget: Optional[TokenBudget] = None,
        session_id: Optional[str] = None,
        namespace: str = "capt-solo",
        claim_text: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        idempotency_key: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a governed MODEL task: the provider invocation is inside the
        CAPT execution path.

        Order (mirrors execute(); the model is NEVER invoked before the gate):
          1. record selection kinds
          2. MemoryUseGate: retrieve + build + validate ContextPack BEFORE
             execution — GateDeniedError on non-PASS (provider not called);
             refusals are DURABLE (CTP ABORT + model-task.failed)
          3. session, CTP begin, publish model-task.started
          4. construct ModelTaskRequest carrying the VALIDATED ContextPack
             digest + rendered_context (NOT the transcript); persist the
             request artifact (dataclass fields only — no headers)
          5. provider.invoke(request); persist the response artifact
          6. record evidence (artifact_hash of the response artifact)
          7. evaluate completion claim through ClaimGuard (when capability_id)
          8. checkpoint + commit; publish model-task.completed ONLY after commit
          9. on failure: abort CTP, publish model-task.failed, re-raise
        """
        records = records or {}
        if not rendered_context:
            rendered_context = f"MISSION {mission_id} objective={objective}"
        if intent is None:
            intent = MissionIntent(
                purpose=objective,
                priority="critical",
                tradeoffs=("governance strictness", "speed"),
                success_definition="model task completes inside a committed CTP transaction",
                safety_constraints=("no ungoverned model execution",),
            )

        # 1. selection kinds
        selection_ids = self.gate.record_selection(
            mission_id, objective, records=records, namespace=namespace
        )

        # 2. mandatory gate — provider must NOT be invoked before PASS
        decision = self.gate.prepare(
            mission_id,
            objective,
            intent=intent,
            assumptions=assumptions,
            evidence=evidence,
            invariants=invariants,
            rendered_context=rendered_context,
            token_budget=token_budget,
            namespace=namespace,
        )

        # 3. session + transaction
        sid = session_id or self.lifecycle.sessions.begin(
            namespace, objective=objective
        )
        _key = idempotency_key or hashlib.sha256(objective.encode()).hexdigest()[:12]
        tx = self.ctp.begin(
            correlation_id=f"model-task:{task_id}",
            idempotency_key=f"model-task:{task_id}:{_key}",
            meta={**self._identity_meta, "session_id": sid, "objective": objective},
        )
        self.bus.publish(
            "model-task.started",
            {"task_id": task_id, "mission_id": mission_id,
             "session_id": sid, "tx_id": tx},
            correlation_id=tx,
        )

        try:
            # 4. mandatory gate — refuse BEFORE any provider invocation; the
            # refusal is durable because it happens inside the CTP transaction
            # (the except handler below aborts + publishes model-task.failed)
            if not decision.allowed:
                raise GateDeniedError(
                    f"ContextPack validation {decision.validation.status} for mission "
                    f"{mission_id}: {', '.join(decision.block_codes)}"
                )

            # 5. request construction — validated ContextPack, not transcript
            decision_id = hashlib.sha256(
                f"{mission_id}:{objective}:{decision.pack.digest}".encode()
            ).hexdigest()[:16]
            request = ModelTaskRequest(
                task_id=task_id,
                mission_id=mission_id,
                session_id=sid,
                contextpack_digest=decision.pack.digest,
                memory_use_decision_id=decision_id,
                active_directive_ids=(),
                system_prompt=decision.pack.rendered_context,
                user_prompt=user_prompt,
                tool_definitions=(),
                response_schema=None,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                idempotency_key=f"{tx}:{_key}",
                metadata=metadata or {},
            )
            request_artifact_id = self._persist_artifact(
                "model-task-request", task_id, tx, request
            )

            # 5. provider invocation + response capture
            result = provider.invoke(request)
            response_artifact_id = self._persist_artifact(
                "model-task-response", task_id, tx, result
            )
            result = dataclasses.replace(
                result,
                request_artifact_id=request_artifact_id,
                response_artifact_id=response_artifact_id,
            )

            # 6. evidence (whitelisted artifact_hash type)
            resp_sha = self._artifact_sha("model-task-response", task_id, tx)
            scope = capability_id or "default"
            self.proof.record(
                "artifact_hash",
                f"model-task:{task_id}",
                resp_sha,
                "governed model task",
                scope=scope,
            )

            # 7. claim evaluation through ClaimGuard
            verdict = None
            if capability_id is not None:
                claim_text = claim_text or f"{objective} complete and verified."
                verdict = self.claimguard.verify_claim(
                    claim_text, capability_id=capability_id
                )

            # 8. checkpoint + commit; completion event only after commit
            ckpt_id = self.lifecycle.sessions.checkpoint(
                sid,
                objective=objective,
                progress="governed model task completed",
                latest_verified_result=str(result.response_text)[:500],
                pending_transaction=tx,
                ctp_tx_id=tx,
            )
            self.bus.publish(
                "mission.checkpoint.written",
                {"checkpoint_id": ckpt_id, "session_id": sid, "tx_id": tx},
                correlation_id=tx,
            )
            rcpt = self.ctp.commit(tx)
            self.bus.publish(
                "model-task.completed",
                {
                    "task_id": task_id,
                    "mission_id": mission_id,
                    "session_id": sid,
                    "tx_id": tx,
                    "checkpoint_id": ckpt_id,
                    "receipt_status": rcpt.status,
                },
                correlation_id=tx,
            )

            result_dict = {
                "ok": True,
                "task_id": task_id,
                "mission_id": mission_id,
                "session_id": sid,
                "tx_id": tx,
                "receipt": rcpt.to_dict(),
                "checkpoint_id": ckpt_id,
                "runtime_id": self.runtime_id,
                "provider": result.provider,
                "model_id": result.model_id,
                "request_artifact_id": request_artifact_id,
                "response_artifact_id": response_artifact_id,
                "response_text": result.response_text,
                "finish_reason": result.finish_reason,
                "tool_calls": list(getattr(result, "tool_calls", ()) or ()),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": result.latency_ms,
                "provider_request_id": result.provider_request_id,
                "claim_verdict": verdict.to_dict() if verdict is not None else None,
                "selection_ids": selection_ids,
                "retrieved_counts": {
                    k: len(v) for k, v in decision.retrieved.items()
                },
                "contextpack": {
                    "digest": decision.pack.digest,
                    "validation": decision.validation.status,
                },
                "event_log": str(self.events.path),
                "events_persisted": self.events.count,
            }
            result_dict["evidence_path"] = str(self._write_evidence(result_dict))
            return result_dict

        except Exception:
            # 9. abort + failed event — NO completion event
            try:
                self.ctp.abort(tx)
            except Exception:
                pass
            self.bus.publish(
                "model-task.failed",
                {"task_id": task_id, "mission_id": mission_id,
                 "session_id": sid, "tx_id": tx},
                correlation_id=tx,
            )
            raise

    def prepare_external_model_turn(
        self,
        *,
        mission_id: str,
        session_id: str,
        turn_id: str,
        objective: str,
        provider_owner: str = "hermes",
        capability_id: Optional[str] = None,
        records: Optional[Dict[str, str]] = None,
        intent: Optional[MissionIntent] = None,
        assumptions: Sequence[Assumption] = (),
        evidence: Sequence[RecordRef] = (),
        invariants: Sequence[RecordRef] = (),
        rendered_context: str = "",
        token_budget: Optional[TokenBudget] = None,
        namespace: str = "capt-solo",
        capt_session_id: Optional[str] = None,
    ) -> PreparedModelTurn:
        """Governed preparation for an EXTERNAL (Hermes-native) model turn.

        This is the canonical CAPTRuntime entrypoint the Hermes plugin calls from
        ``pre_llm_call``. It performs steps 1-3 of the governed path — selection
        recording, MemoryUseGate (retrieve + build + validate ContextPack), and CTP
        transaction begin — but does NOT invoke the provider. Hermes owns the
        transport and calls ``commit_external_model_turn`` / ``abort_external_model_turn``
        from ``post_llm_call``.

        All governance logic stays inside CAPTRuntime; the plugin only translates
        Hermes hook kwargs into this call and carries the returned handle.

        Idempotency: ``ctp.begin`` uses ``idempotency_key=f"model-turn:{turn_id}"``,
        so a repeated ``pre_llm_call`` for the same turn (e.g. API retry) reuses or
        is rejected by the journal rather than opening a duplicate transaction.

        Raises ``GateDeniedError`` when the ContextPack validation does not PASS
        (the provider must not be called).
        """
        records = records or {}
        if not rendered_context:
            rendered_context = objective
        if intent is None:
            intent = MissionIntent(
                purpose=objective,
                priority="critical",
                tradeoffs=("governance strictness", "speed"),
                success_definition="external model turn completes inside a committed CTP transaction",
                safety_constraints=("no ungoverned model execution",),
            )

        # Idempotency: reuse an already-prepared turn for this turn_id (a second
        # pre_llm_call for the same logical turn must not open a duplicate CTP tx).
        if turn_id in self._prepared_turns:
            return self._prepared_turns[turn_id]

        # 1. record selection kinds (selected/rejected/stale/missing/conflicting)
        selection_ids_scalar = self.gate.record_selection(
            mission_id, objective, records=records, namespace=namespace
        )

        # 2. mandatory gate — retrieve + build + validate BEFORE any provider call
        decision = self.gate.prepare(
            mission_id,
            objective,
            intent=intent,
            assumptions=assumptions,
            evidence=evidence,
            invariants=invariants,
            rendered_context=rendered_context,
            token_budget=token_budget,
            namespace=namespace,
        )
        if not decision.allowed:
            raise GateDeniedError(
                f"ContextPack validation {decision.validation.status} for mission "
                f"{mission_id}: {', '.join(decision.block_codes)}"
            )

        # 3. ensure a CAPTRuntime session exists (Hermes session id is the
        # correlation key; CAPTRuntime owns its own session identity). When the
        # plugin already created a session via on_session_start, reuse it so the
        # turn's CTP transaction is correlated to the session's checkpoint chain.
        if capt_session_id:
            sid = capt_session_id
        else:
            sid = self.lifecycle.sessions.begin(namespace, objective=objective)
        correlation_id = f"turn:{turn_id}"
        tx = self.ctp.begin(
            correlation_id=correlation_id,
            idempotency_key=f"model-turn:{turn_id}",
            meta={
                **self._identity_meta,
                "session_id": sid,
                "hermes_session_id": session_id,
                "turn_id": turn_id,
                "objective": objective,
                "provider_owner": provider_owner,
            },
        )
        self.bus.publish(
            "model-task.started",
            {
                "turn_id": turn_id,
                "mission_id": mission_id,
                "session_id": session_id,
                "tx_id": tx,
                "provider_owner": provider_owner,
            },
            correlation_id=tx,
        )

        # MemoryUseDecision id (mirrors execute_model_task)
        memory_use_decision_id = hashlib.sha256(
            f"{mission_id}:{objective}:{decision.pack.digest}".encode()
        ).hexdigest()[:16]

        # canonical list-valued selection_ids (retrieved collections)
        selection_ids = normalize_selection_ids(
            {k: [m.memory_id for m in v] for k, v in decision.retrieved.items()}
        )
        # merge the recorded scalar ids so every kind has at least its recorded id
        for k, mid in selection_ids_scalar.items():
            if mid and (not selection_ids.get(k)):
                selection_ids[k] = [mid]

        prepared = PreparedModelTurn(
            turn_id=turn_id,
            ctp_tx_id=tx,
            session_id=sid,
            correlation_id=correlation_id,
            contextpack_digest=decision.pack.digest,
            gate_allowed=True,
            rendered_context=decision.pack.rendered_context or "",
            memory_use_decision_id=memory_use_decision_id,
            selection_ids=selection_ids,
            mission_id=mission_id,
            namespace=namespace,
            provider_owner=provider_owner,
        )
        self._prepared_turns[turn_id] = prepared
        return prepared

    def commit_external_model_turn(
        self,
        *,
        prepared: PreparedModelTurn,
        assistant_response: str = "",
        claim_text: Optional[str] = None,
        capability_id: Optional[str] = None,
        namespace: str = "capt-solo",
    ) -> Dict[str, Any]:
        """Commit the CTP transaction opened by ``prepare_external_model_turn``.

        Called from the Hermes ``post_llm_call`` hook after the provider returns.
        Persists response evidence, evaluates a ClaimGuard claim, writes a
        checkpoint, commits the CTP transaction, and publishes the completion
        event ONLY after commit (no KHSB completion contradicts CTP state).
        """
        sid = prepared.session_id
        tx = prepared.ctp_tx_id
        try:
            # evidence: artifact_hash of the response
            resp_sha = hashlib.sha256(assistant_response.encode()).hexdigest()
            scope = capability_id or prepared.mission_id
            self.proof.record(
                "artifact_hash",
                f"turn:{prepared.turn_id}",
                resp_sha,
                "governed external model turn response",
                scope=scope,
            )

            # ClaimGuard evaluation (narrow claim, only if a capability is given)
            verdict = None
            if capability_id is not None:
                verdict = self.claimguard.verify_claim(
                    claim_text or f"{prepared.mission_id} turn completed and verified.",
                    capability_id=capability_id,
                )

            # checkpoint
            ckpt_id = self.lifecycle.sessions.checkpoint(
                sid,
                objective=prepared.rendered_context[:200] or prepared.mission_id,
                progress="governed external model turn completed",
                latest_verified_result=assistant_response[:500],
                pending_transaction=tx,
                ctp_tx_id=tx,
            )
            self.bus.publish(
                "mission.checkpoint.written",
                {"checkpoint_id": ckpt_id, "session_id": sid, "tx_id": tx},
                correlation_id=tx,
            )

            # commit BEFORE completion event
            rcpt = self.ctp.commit(tx)
            self.bus.publish(
                "model-task.completed",
                {
                    "turn_id": prepared.turn_id,
                    "mission_id": prepared.mission_id,
                    "session_id": sid,
                    "tx_id": tx,
                    "checkpoint_id": ckpt_id,
                    "receipt_status": rcpt.status,
                },
                correlation_id=tx,
            )
            return {
                "ok": True,
                "turn_id": prepared.turn_id,
                "tx_id": tx,
                "receipt": rcpt.to_dict(),
                "checkpoint_id": ckpt_id,
                "claim_verdict": verdict.to_dict() if verdict is not None else None,
                "contextpack_digest": prepared.contextpack_digest,
                "selection_ids": prepared.selection_ids,
            }
        except Exception:
            # abort + failed event — NO completion event
            try:
                self.ctp.abort(tx)
            except Exception:
                pass
            self.bus.publish(
                "model-task.failed",
                {
                    "turn_id": prepared.turn_id,
                    "mission_id": prepared.mission_id,
                    "session_id": sid,
                    "tx_id": tx,
                },
                correlation_id=tx,
            )
            raise

    def abort_external_model_turn(
        self, *, prepared: PreparedModelTurn
    ) -> Dict[str, Any]:
        """Abort the CTP transaction (e.g. when post_llm_call has no finalized response)."""
        tx = prepared.ctp_tx_id
        try:
            self.ctp.abort(tx)
        except Exception:
            pass
        self.bus.publish(
            "model-task.failed",
            {
                "turn_id": prepared.turn_id,
                "mission_id": prepared.mission_id,
                "session_id": prepared.session_id,
                "tx_id": tx,
            },
            correlation_id=tx,
        )
        return {"ok": False, "turn_id": prepared.turn_id, "tx_id": tx, "aborted": True}

    def _artifact_dir(self, kind: str) -> Path:
        base = self.config.evidence_dir or (data_dir() / "evidence")
        d = base / kind
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        return d

    def _persist_artifact(self, kind: str, task_id: str, tx: str, obj: Any) -> str:
        """Persist a request/response artifact (dataclass fields ONLY — never
        headers), returning the artifact id."""
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            obj = dataclasses.asdict(obj)  # type: ignore[arg-type]
        payload = json.dumps(obj, indent=2, default=str)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        path = self._artifact_dir(kind) / f"{task_id}_{tx}.json"
        path.write_text(payload, encoding="utf-8")
        sidecar = path.with_suffix(".json.sha256")
        sidecar.write_text(f"sha256:{digest}  {path.name}\n", encoding="utf-8")
        return f"{kind}:{task_id}:{tx}"

    def _artifact_sha(self, kind: str, task_id: str, tx: str) -> str:
        path = self._artifact_dir(kind) / f"{task_id}_{tx}.json"
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_evidence(self, result: Dict[str, Any]) -> Path:
        ev_dir = self.config.evidence_dir or (data_dir() / "evidence")
        ev_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = json.dumps(result, indent=2, default=str)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        path = ev_dir / f"{result['mission_id']}_{result['tx_id']}.json"
        path.write_text(payload, encoding="utf-8")
        sidecar = path.with_suffix(".sha256")
        sidecar.write_text(f"sha256:{digest}  {path.name}\n", encoding="utf-8")
        return path

    def close(self) -> None:
        self.engine.close()
        self.ctp.close()
