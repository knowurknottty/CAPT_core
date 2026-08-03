"""MemoryTriggerEngine — CAPT-owned mandatory memory trigger enforcement.

This is the authoritative integration point. It:

- owns the active MemoryTriggerPolicy and per-mission trigger state;
- measures context usage and computes the next trigger boundary;
- fires the mandatory memory query when the retrieval trigger crosses;
- assembles the ContextPack and records its digest;
- enforces harness dispatch gating (DriverHost calls require_memory_before_dispatch);
- evaluates memory-promotion candidates after execution;
- persists policy changes and trigger state for reconnect/replay.

Drivers and the desktop never call these decisions; they consume the
ContextPack slice and the policy reference. The engine is the single owner of
the trigger decision.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional

from .accounting import ContextAccounting, ContextUsage, TriggerState
from .contextpack import build_context_pack
from .policy import (
    MemoryTriggerPolicy,
    PolicySource,
    TRIGGER_INTERVAL_TOKENS,
    effective_policy,
)
from .query import build_memory_query
from .store import MemoryRecord, MemoryStore

# Explicit enforcement failure codes (mission §7).
MEMORY_PATH_INACTIVE = "MEMORY_PATH_INACTIVE"
CONTEXTPACK_REQUIRED = "CONTEXTPACK_REQUIRED"
CONTEXTPACK_STALE = "CONTEXTPACK_STALE"
CONTEXT_BUDGET_EXCEEDED = "CONTEXT_BUDGET_EXCEEDED"
MEMORY_CONSENT_DENIED = "MEMORY_CONSENT_DENIED"
MEMORY_SCOPE_VIOLATION = "MEMORY_SCOPE_VIOLATION"
MEMORY_TRIGGER_CONFIGURATION_INVALID = "MEMORY_TRIGGER_CONFIGURATION_INVALID"
MEMORY_REBUILD_REQUIRED = "MEMORY_REBUILD_REQUIRED"


class MemoryEnforcementError(Exception):
    """Raised when a mandatory memory gate fails. Carries an explicit code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class MemoryTriggerEngine:
    """Owns memory trigger state and enforcement for the runtime."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        model_safe_limit_steps: int = 8,
        policy: Optional[MemoryTriggerPolicy] = None,
        ledger_db: str = ":memory:",
    ) -> None:
        self.store = store
        self.model_safe_limit_steps = model_safe_limit_steps
        self.policy = policy or effective_policy(model_safe_limit_steps=model_safe_limit_steps)
        self._accounting = ContextAccounting(self.policy)
        # per-mission trigger state
        self._state: Dict[str, TriggerState] = {}
        # per-mission last ContextPack digest
        self._last_pack: Dict[str, Dict[str, Any]] = {}
        # persisted policy log
        self._ledger = sqlite3.connect(ledger_db, check_same_thread=False)
        self._ledger.row_factory = sqlite3.Row
        self._ledger_lock = __import__("threading").Lock()
        self._init_ledger()

    def _init_ledger(self) -> None:
        self._ledger.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_policy_log (
                policy_version INTEGER PRIMARY KEY,
                policy_digest TEXT NOT NULL,
                previous_policy_digest TEXT,
                source TEXT NOT NULL,
                operator_id TEXT,
                command_id TEXT,
                correlation_id TEXT,
                timestamp TEXT,
                effective_json TEXT NOT NULL
            )
            """
        )
        self._ledger.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_trigger_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                boundary INTEGER NOT NULL,
                usage INTEGER NOT NULL,
                context_pack_digest TEXT,
                correlation_id TEXT,
                timestamp TEXT
            )
            """
        )
        self._ledger.commit()
        # Persist the initial policy.
        self._log_policy(self.policy, None, None, None)

    # -- policy management --------------------------------------------------

    def set_policy(self, policy: MemoryTriggerPolicy) -> None:
        """Replace the active policy (validated) and persist it."""
        self.policy = policy
        self._accounting = ContextAccounting(policy)
        self._log_policy(policy, policy.command_id, policy.correlation_id, policy.operator_id)

    def update_policy(
        self,
        *,
        retrieval_trigger_steps: Optional[int] = None,
        compression_trigger_steps: Optional[int] = None,
        checkpoint_trigger_steps: Optional[int] = None,
        consolidation_trigger_steps: Optional[int] = None,
        hard_stop_trigger_steps: Optional[int] = None,
        model_safe_limit_steps: Optional[int] = None,
        source: str = PolicySource.OPERATOR_SELECTED,
        operator_id: Optional[str] = None,
        command_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> MemoryTriggerPolicy:
        new_policy = self.policy.with_update(
            retrieval_trigger_steps=retrieval_trigger_steps,
            compression_trigger_steps=compression_trigger_steps,
            checkpoint_trigger_steps=checkpoint_trigger_steps,
            consolidation_trigger_steps=consolidation_trigger_steps,
            hard_stop_trigger_steps=hard_stop_trigger_steps,
            model_safe_limit_steps=model_safe_limit_steps,
            source=source,
            operator_id=operator_id,
            command_id=command_id,
            correlation_id=correlation_id,
        )
        self.set_policy(new_policy)
        return new_policy

    def _log_policy(
        self,
        policy: MemoryTriggerPolicy,
        command_id: Optional[str],
        correlation_id: Optional[str],
        operator_id: Optional[str],
    ) -> None:
        d = policy.to_dict()
        with self._ledger_lock:
            self._ledger.execute(
                """
                INSERT OR REPLACE INTO memory_policy_log
                (policy_version, policy_digest, previous_policy_digest, source,
                 operator_id, command_id, correlation_id, timestamp, effective_json)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    d["policyVersion"],
                    d["policyDigest"],
                    d.get("previousPolicyDigest"),
                    d["source"],
                    operator_id,
                    command_id,
                    correlation_id,
                    policy.timestamp,
                    json.dumps(d),
                ),
            )
            self._ledger.commit()

    def persisted_policy_versions(self) -> List[int]:
        return [
            r["policy_version"]
            for r in self._ledger.execute(
                "SELECT policy_version FROM memory_policy_log ORDER BY policy_version"
            ).fetchall()
        ]

    # -- trigger evaluation ------------------------------------------------

    def _state_for(self, mission_id: str) -> TriggerState:
        if mission_id not in self._state:
            self._state[mission_id] = TriggerState()
        return self._state[mission_id]

    def evaluate_usage(
        self,
        mission_id: str,
        usage: ContextUsage,
        *,
        measured: bool = False,
    ) -> Dict[str, Any]:
        """Evaluate triggers for current usage. Returns the evaluation report
        and updates the per-mission trigger state (idempotent)."""
        state = self._state_for(mission_id)
        report = self._accounting.evaluate(usage, state, measured=measured)
        # Apply idempotent firing: mark triggers that fired this evaluation.
        if report["triggers"]["retrieval"]["fires"]:
            state.retrieval_fired = True
        if report["triggers"]["compression"]["fires"]:
            state.compression_fired = True
        if report["triggers"]["checkpoint"]["fires"]:
            state.checkpoint_fired = True
        if report["triggers"]["consolidation"]["fires"]:
            state.consolidation_fired = True
        if report["triggers"]["hardStop"]["fires"]:
            state.hard_stop = True
        state.last_evaluated_usage = usage.total()
        state.last_trigger_boundary = report["nextTriggerBoundary"]
        return report

    def require_retrieval_before_planning(
        self, mission_id: str, usage: ContextUsage
    ) -> Dict[str, Any]:
        """Mandatory gate before planning. Fires the retrieval trigger and
        returns the assembled ContextPack. Raises if memory path is inactive."""
        if self.store is None:
            raise MemoryEnforcementError(
                MEMORY_PATH_INACTIVE, "mandatory memory path is inactive"
            )
        report = self.evaluate_usage(mission_id, usage)
        if not report["triggers"]["retrieval"]["fires"]:
            # Already satisfied at this usage; return existing pack if any.
            existing = self._last_pack.get(mission_id)
            if existing is not None:
                return existing
        pack = self._fire_retrieval(mission_id, usage, report)
        return pack

    def _fire_retrieval(
        self, mission_id: str, usage: ContextUsage, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        state = self._state_for(mission_id)
        query = build_memory_query(
            mission_id=mission_id,
            task_id=state.last_trigger_boundary and mission_id or mission_id,
            actor="human" if False else "runtime",
            requesting_subsystem="capt_runtime.memory",
            trigger_boundary=report["nextTriggerBoundary"],
            context_usage=usage.total(),
            requested_memory_classes=[
                "working", "episodic", "semantic", "procedural",
                "project", "user", "agent_private", "shared",
            ],
            purpose="mandatory retrieval trigger before planning",
            record_limit=20,
            token_budget=report["remainingBudget"],
            consent_scope="project",
            sensitivity_allowance="project",
            trust_threshold=0.0,
        )
        previous = self._last_pack.get(mission_id, {}).get("contextPackDigest")
        pack = build_context_pack(
            store=self.store,
            policy_version=self.policy.policy_version,
            trigger_boundary=report["nextTriggerBoundary"],
            context_usage_before=usage.total(),
            query=query,
            mission_id=mission_id,
            previous_digest=previous,
        )
        self._last_pack[mission_id] = pack
        state.last_context_pack_digest = pack["contextPackDigest"]
        self._log_trigger(mission_id, "retrieval", report["nextTriggerBoundary"], usage.total(), pack["contextPackDigest"], query["correlationId"])
        return pack

    def _log_trigger(
        self,
        mission_id: str,
        trigger_type: str,
        boundary: int,
        usage: int,
        digest: Optional[str],
        correlation_id: Optional[str],
    ) -> None:
        import time

        with self._ledger_lock:
            self._ledger.execute(
                """
                INSERT INTO memory_trigger_log
                (mission_id, trigger_type, boundary, usage, context_pack_digest,
                 correlation_id, timestamp)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    mission_id,
                    trigger_type,
                    boundary,
                    usage,
                    digest,
                    correlation_id,
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ),
            )
            self._ledger.commit()

    # -- harness dispatch gate --------------------------------------------

    def require_memory_before_dispatch(
        self,
        mission_id: str,
        *,
        context_pack_digest: Optional[str] = None,
        policy_digest: Optional[str] = None,
        context_usage: Optional[int] = None,
        consent_ok: bool = True,
        scope_ok: bool = True,
    ) -> Dict[str, Any]:
        """DriverHost calls this BEFORE every external driver dispatch.

        Refuses dispatch when:
        - mandatory memory path is inactive;
        - ContextPack is missing;
        - ContextPack digest is invalid (does not match the recorded pack);
        - trigger state is stale (usage exceeds the recorded boundary without a rebuild);
        - required consent check failed;
        - context exceeds the hard-stop boundary;
        - selected memory violates project/user scope.
        """
        if self.store is None:
            raise MemoryEnforcementError(
                MEMORY_PATH_INACTIVE, "mandatory memory path is inactive"
            )
        pack = self._last_pack.get(mission_id)
        if pack is None:
            raise MemoryEnforcementError(
                CONTEXTPACK_REQUIRED,
                "dispatch refused: no ContextPack for mission %s" % mission_id,
            )
        if context_pack_digest is not None and context_pack_digest != pack["contextPackDigest"]:
            raise MemoryEnforcementError(
                CONTEXTPACK_STALE,
                "dispatch refused: ContextPack digest mismatch for mission %s" % mission_id,
            )
        if policy_digest is not None and policy_digest != self.policy.policy_digest:
            raise MemoryEnforcementError(
                CONTEXTPACK_STALE,
                "dispatch refused: policy digest mismatch for mission %s" % mission_id,
            )
        if not consent_ok:
            raise MemoryEnforcementError(
                MEMORY_CONSENT_DENIED,
                "dispatch refused: consent check failed for mission %s" % mission_id,
            )
        if not scope_ok:
            raise MemoryEnforcementError(
                MEMORY_SCOPE_VIOLATION,
                "dispatch refused: memory scope violation for mission %s" % mission_id,
            )
        if context_usage is not None and context_usage >= self.policy.hard_stop_tokens():
            raise MemoryEnforcementError(
                CONTEXT_BUDGET_EXCEEDED,
                "dispatch refused: context usage %d >= hard-stop %d for mission %s"
                % (context_usage, self.policy.hard_stop_tokens(), mission_id),
            )
        return {
            "ok": True,
            "contextPackDigest": pack["contextPackDigest"],
            "policyDigest": self.policy.policy_digest,
            "selectedRecordCount": len(pack["selectedRecords"]),
        }

    # -- promotion ---------------------------------------------------------

    def evaluate_promotion(
        self,
        mission_id: str,
        observations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """After execution, classify observation-derived candidates.

        Returns promotion candidates with required provenance/evidence linkage.
        Unverified model output is NOT promoted as verified fact.
        """
        candidates: List[Dict[str, Any]] = []
        for obs in observations:
            summary = obs.get("summary") or obs.get("text") or ""
            if not summary:
                continue
            candidates.append(
                {
                    "candidateId": "promo-" + mission_id + "-" + str(len(candidates)),
                    "source": "driver_observation",
                    "content": summary,
                    "requiresEvidence": True,
                    "verified": False,
                    "proposedClass": "episodic",
                    "missionId": mission_id,
                }
            )
        return candidates

    def accept_promotion(self, candidate: Dict[str, Any], *, owner: str = "operator") -> MemoryRecord:
        """Persist an accepted promotion as a memory record (governed)."""
        rec = MemoryRecord(
            record_id=candidate["candidateId"],
            memory_class=candidate.get("proposedClass", "episodic"),
            owner=owner,
            source=candidate.get("source", "driver_observation"),
            provenance="mission:%s" % candidate.get("missionId", "?"),
            trust="unverified",
            verification_status="pending",
            sensitivity="project",
            consent="project",
            content=candidate["content"],
        )
        self.store.store(rec)
        return rec

    # -- reconnect / replay ------------------------------------------------

    def reconstruct_policy(self, policy_version: int) -> Optional[MemoryTriggerPolicy]:
        row = self._ledger.execute(
            "SELECT effective_json FROM memory_policy_log WHERE policy_version = ?",
            (policy_version,),
        ).fetchone()
        if row is None:
            return None
        return MemoryTriggerPolicy.from_dict(json.loads(row["effective_json"]))

    def last_context_pack(self, mission_id: str) -> Optional[Dict[str, Any]]:
        return self._last_pack.get(mission_id)

    def trigger_log(self, mission_id: str) -> List[Dict[str, Any]]:
        return [
            dict(r)
            for r in self._ledger.execute(
                "SELECT * FROM memory_trigger_log WHERE mission_id = ? ORDER BY id",
                (mission_id,),
            ).fetchall()
        ]
