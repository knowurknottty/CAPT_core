"""CAPT Solo v0.3 — Procedural Memory.

Reusable methods for performing work. Procedures are versioned; a prior
version is NEVER silently overwritten. A procedure is NOT promoted merely
because it was attempted repeatedly — successful verified runs are
evidence; repetition alone is not.

Public operations:
    procedures.create(...)
    procedures.get(...)
    procedures.list(...)
    procedures.revise(...)
    procedures.record_run(...)
    procedures.deprecate(...)
    procedures.build_execution_context(...)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.memory.engine import MemoryEngine


@dataclass
class Procedure:
    procedure_id: str
    name: str
    trigger: str
    purpose: str
    preconditions: str
    inputs: str
    steps: str
    expected_outputs: str
    verification: str
    failure_modes: str
    recovery_steps: str
    evidence_refs: List[str]
    artifact_refs: List[str]
    version: int
    success_count: int
    failure_count: int
    last_verified_at: Optional[float]
    trust_state: str
    lifecycle_state: str
    namespace: str
    created_at: float
    updated_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "procedure_id": self.procedure_id,
            "name": self.name,
            "trigger": self.trigger,
            "purpose": self.purpose,
            "preconditions": self.preconditions,
            "inputs": self.inputs,
            "steps": self.steps,
            "expected_outputs": self.expected_outputs,
            "verification": self.verification,
            "failure_modes": self.failure_modes,
            "recovery_steps": self.recovery_steps,
            "evidence_refs": self.evidence_refs,
            "artifact_refs": self.artifact_refs,
            "version": self.version,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_verified_at": self.last_verified_at,
            "trust_state": self.trust_state,
            "lifecycle_state": self.lifecycle_state,
            "namespace": self.namespace,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProcedureStore:
    """Versioned procedural memory backed by SQLite (same DB as memories)."""

    def __init__(self, engine: MemoryEngine) -> None:
        self._eng = engine

    # ----- create -------------------------------------------------
    def create(
        self, name: str, *, trigger: str = "", purpose: str = "",
        preconditions: str = "", inputs: str = "", steps: str = "",
        expected_outputs: str = "", verification: str = "",
        failure_modes: str = "", recovery_steps: str = "",
        evidence_refs: Optional[List[str]] = None,
        artifact_refs: Optional[List[str]] = None,
        namespace: str = "default",
        ctp_tx_id: Optional[str] = None,
    ) -> str:
        if not name:
            raise MemoryError_("procedure name must be non-empty")
        pid = uuid.uuid4().hex
        now = time.time()
        self._eng._conn.execute(
            """INSERT INTO procedures
               (procedure_id, name, trigger, purpose, preconditions, inputs,
                steps, expected_outputs, verification, failure_modes,
                recovery_steps, evidence_refs, artifact_refs, version,
                success_count, failure_count, last_verified_at,
                trust_state, lifecycle_state, namespace, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,0,0,NULL,
                       'candidate','candidate',?,?,?)""",
            (pid, name, trigger, purpose, preconditions, inputs, steps,
             expected_outputs, verification, failure_modes, recovery_steps,
             json.dumps(evidence_refs or []), json.dumps(artifact_refs or []),
             namespace, now, now),
        )
        # snapshot version 1
        self._snapshot(pid, 1, name, trigger, purpose, preconditions, inputs,
                      steps, expected_outputs, verification, failure_modes,
                      recovery_steps, evidence_refs or [], artifact_refs or [])
        self._eng._conn.commit()
        return pid

    # ----- get / list ----------------------------------------------
    def get(self, procedure_id: str) -> Optional[Procedure]:
        row = self._eng._conn.execute(
            "SELECT * FROM procedures WHERE procedure_id=?",
            (procedure_id,)).fetchone()
        return self._row_to_procedure(row) if row else None

    def get_version(self, procedure_id: str, version: int) -> Optional[Dict[str, Any]]:
        row = self._eng._conn.execute(
            "SELECT * FROM procedure_versions WHERE procedure_id=? AND version=?",
            (procedure_id, version)).fetchone()
        if row is None:
            return None
        d = dict(row)
        for k in ("evidence_refs", "artifact_refs"):
            d[k] = json.loads(d[k])
        return d

    def list(self, *, namespace: Optional[str] = None,
             lifecycle_state: Optional[str] = None) -> List[Procedure]:
        sql = "SELECT * FROM procedures"
        where = []
        params: List[Any] = []
        if namespace:
            where.append("namespace=?")
            params.append(namespace)
        if lifecycle_state:
            where.append("lifecycle_state=?")
            params.append(lifecycle_state)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated_at DESC"
        return [self._row_to_procedure(r)
                for r in self._eng._conn.execute(sql, params).fetchall()]

    # ----- revise -------------------------------------------------
    def revise(
        self, procedure_id: str, *, trigger: Optional[str] = None,
        purpose: Optional[str] = None, preconditions: Optional[str] = None,
        inputs: Optional[str] = None, steps: Optional[str] = None,
        expected_outputs: Optional[str] = None, verification: Optional[str] = None,
        failure_modes: Optional[str] = None, recovery_steps: Optional[str] = None,
        evidence_refs: Optional[List[str]] = None,
        artifact_refs: Optional[List[str]] = None,
        ctp_tx_id: Optional[str] = None,
    ) -> int:
        """Create a NEW version (never overwrites the prior version)."""
        proc = self.get(procedure_id)
        if proc is None:
            raise MemoryError_(f"procedure not found: {procedure_id}")
        new_version = proc.version + 1
        # apply overrides onto current values
        def pick(cur, new):
            return new if new is not None else cur
        name = proc.name
        trigger = pick(proc.trigger, trigger)
        purpose = pick(proc.purpose, purpose)
        preconditions = pick(proc.preconditions, preconditions)
        inputs = pick(proc.inputs, inputs)
        steps = pick(proc.steps, steps)
        expected_outputs = pick(proc.expected_outputs, expected_outputs)
        verification = pick(proc.verification, verification)
        failure_modes = pick(proc.failure_modes, failure_modes)
        recovery_steps = pick(proc.recovery_steps, recovery_steps)
        evidence_refs = pick(proc.evidence_refs, evidence_refs)
        artifact_refs = pick(proc.artifact_refs, artifact_refs)
        now = time.time()
        self._eng._conn.execute(
            """UPDATE procedures SET
               trigger=?, purpose=?, preconditions=?, inputs=?, steps=?,
               expected_outputs=?, verification=?, failure_modes=?,
               recovery_steps=?, evidence_refs=?, artifact_refs=?,
               version=?, updated_at=?
               WHERE procedure_id=?""",
            (trigger, purpose, preconditions, inputs, steps, expected_outputs,
             verification, failure_modes, recovery_steps,
             json.dumps(evidence_refs), json.dumps(artifact_refs),
             new_version, now, procedure_id),
        )
        # snapshot the new version
        self._snapshot(procedure_id, new_version, name, trigger, purpose,
                      preconditions, inputs, steps, expected_outputs,
                      verification, failure_modes, recovery_steps,
                      evidence_refs, artifact_refs)
        self._eng._conn.commit()
        return new_version

    # ----- record run ----------------------------------------------
    def record_run(
        self, procedure_id: str, *, outcome: str, version_used: Optional[int] = None,
        inputs: str = "", verification_result: str = "",
        failure_reason: str = "", ctp_ref: Optional[str] = None,
        session_ref: Optional[str] = None,
    ) -> str:
        """Record a procedure run. Updates success/failure counts.

        A successful verified run is evidence; repetition alone is NOT
        promotion. The procedure's trust_state is NOT changed here.
        """
        proc = self.get(procedure_id)
        if proc is None:
            raise MemoryError_(f"procedure not found: {procedure_id}")
        v = version_used or proc.version
        success = outcome == "success"
        now = time.time()
        if success:
            self._eng._conn.execute(
                "UPDATE procedures SET success_count=success_count+1, "
                "last_verified_at=? WHERE procedure_id=?",
                (now, procedure_id))
        else:
            self._eng._conn.execute(
                "UPDATE procedures SET failure_count=failure_count+1 "
                "WHERE procedure_id=?", (procedure_id,))
        rid = uuid.uuid4().hex
        self._eng._conn.execute(
            """INSERT INTO procedure_runs
               (run_id, procedure_id, version_used, inputs, outcome,
                verification_result, failure_reason, ctp_ref, session_ref, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (rid, procedure_id, v, inputs, outcome, verification_result,
             failure_reason, ctp_ref, session_ref, now))
        self._eng._conn.commit()
        return rid

    def get_runs(self, procedure_id: str) -> List[Dict[str, Any]]:
        """Return recorded runs for a procedure (public read API)."""
        rows = self._eng._conn.execute(
            "SELECT * FROM procedure_runs WHERE procedure_id=? ORDER BY created_at",
            (procedure_id,)).fetchall()
        return [dict(r) for r in rows]

    # ----- verify (public trust/lifecycle promotion) -----------------
    def verify_procedure(
        self, procedure_id: str, *, min_success: int = 2,
        require_verification_result: bool = True,
        ctp_tx_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Public path to mark a procedure verified.

        Promotion requires REAL evidence, not repetition alone:
          - success_count >= min_success
          - at least one run with a non-empty verification_result (when required)
        Sets trust_state='verified' and records the CTP linkage. This is the
        ONLY sanctioned way to move a procedure into verified state; direct
        SQL mutation is forbidden.
        """
        proc = self.get(procedure_id)
        if proc is None:
            raise MemoryError_(f"procedure not found: {procedure_id}")
        if proc.success_count < min_success:
            raise MemoryError_(
                f"procedure '{procedure_id}' has {proc.success_count} successful "
                f"runs; requires >= {min_success} for verification")
        if require_verification_result:
            has_vr = self._eng._conn.execute(
                "SELECT COUNT(*) AS c FROM procedure_runs "
                "WHERE procedure_id=? AND verification_result != ''",
                (procedure_id,)).fetchone()["c"]
            if has_vr == 0:
                raise MemoryError_(
                    f"procedure '{procedure_id}' has no recorded verification "
                    f"result; verification evidence required")
        self._eng._conn.execute(
            "UPDATE procedures SET trust_state='verified', updated_at=? "
            "WHERE procedure_id=?",
            (time.time(), procedure_id))
        if ctp_tx_id:
            refs = list(proc.evidence_refs) + [ctp_tx_id]
            self._eng._conn.execute(
                "UPDATE procedures SET evidence_refs=? WHERE procedure_id=?",
                (json.dumps(refs), procedure_id))
        self._eng._conn.commit()
        return {"procedure_id": procedure_id, "trust_state": "verified",
                "success_count": proc.success_count}
    def deprecate(self, procedure_id: str, *, reason: str = "",
                  ctp_tx_id: Optional[str] = None) -> None:
        proc = self.get(procedure_id)
        if proc is None:
            raise MemoryError_(f"procedure not found: {procedure_id}")
        self._eng._conn.execute(
            "UPDATE procedures SET lifecycle_state='deprecated', updated_at=? "
            "WHERE procedure_id=?", (time.time(), procedure_id))
        self._eng._conn.commit()

    def missing_fields(self, procedure_id: str) -> List[str]:
        """Return required fields that are empty for a procedure.

        Used by consolidation to flag incomplete candidate procedures
        rather than silently promoting them as reliable.
        """
        proc = self.get(procedure_id)
        if proc is None:
            raise MemoryError_(f"procedure not found: {procedure_id}")
        required = ["trigger", "steps", "verification", "expected_outputs"]
        return [f for f in required if not getattr(proc, f, "").strip()]

    # ----- execution context ---------------------------------------
    def build_execution_context(
        self, procedure_id: str, *, version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return an ADVISORY execution context.

        The returned content is advisory until the active agent validates
        context, authority, and safety. It is NOT auto-executed.
        """
        proc = self.get(procedure_id)
        if proc is None:
            raise MemoryError_(f"procedure not found: {procedure_id}")
        v = version or proc.version
        snap = self.get_version(procedure_id, v) or proc.to_dict()
        return {
            "procedure_id": procedure_id,
            "version": v,
            "name": snap.get("name", proc.name),
            "trigger": snap.get("trigger", proc.trigger),
            "purpose": snap.get("purpose", proc.purpose),
            "preconditions": snap.get("preconditions", proc.preconditions),
            "steps": snap.get("steps", proc.steps),
            "expected_outputs": snap.get("expected_outputs", proc.expected_outputs),
            "verification": snap.get("verification", proc.verification),
            "failure_modes": snap.get("failure_modes", proc.failure_modes),
            "recovery_steps": snap.get("recovery_steps", proc.recovery_steps),
            "advisory": True,
            "note": "advisory until agent validates context, authority, safety",
        }

    # ----- internals ------------------------------------------------
    def _snapshot(self, pid, version, name, trigger, purpose, preconditions,
                   inputs, steps, expected_outputs, verification, failure_modes,
                   recovery_steps, evidence_refs, artifact_refs) -> None:
        self._eng._conn.execute(
            """INSERT OR REPLACE INTO procedure_versions
               (procedure_id, version, name, trigger, purpose, preconditions,
                inputs, steps, expected_outputs, verification, failure_modes,
                recovery_steps, evidence_refs, artifact_refs, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, version, name, trigger, purpose, preconditions, inputs,
             steps, expected_outputs, verification, failure_modes,
             recovery_steps, json.dumps(evidence_refs), json.dumps(artifact_refs),
             time.time()))

    @staticmethod
    def _row_to_procedure(row) -> Procedure:
        return Procedure(
            procedure_id=row["procedure_id"],
            name=row["name"],
            trigger=row["trigger"],
            purpose=row["purpose"],
            preconditions=row["preconditions"],
            inputs=row["inputs"],
            steps=row["steps"],
            expected_outputs=row["expected_outputs"],
            verification=row["verification"],
            failure_modes=row["failure_modes"],
            recovery_steps=row["recovery_steps"],
            evidence_refs=json.loads(row["evidence_refs"]),
            artifact_refs=json.loads(row["artifact_refs"]),
            version=row["version"],
            success_count=row["success_count"],
            failure_count=row["failure_count"],
            last_verified_at=row["last_verified_at"],
            trust_state=row["trust_state"],
            lifecycle_state=row["lifecycle_state"],
            namespace=row["namespace"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
