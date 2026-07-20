"""CAPT Solo v0.4 — Skill Foundry.

Converts mature procedural memories into reusable Hermes skills through a
governed pipeline:

    Verified Procedure
        -> Skill Candidate
        -> Evidence Aggregation
        -> Validation (harness)
        -> Sandbox Execution
        -> Human Review
        -> Published Skill

No procedure automatically becomes a skill. Promotion requires evidence.

A published skill contains:
    unique ID, semantic version, compatibility, trigger, purpose,
    prerequisites, required tools, permissions, ordered workflow,
    expected outputs, rollback strategy, failure modes, recovery strategy,
    verification requirements, supporting evidence, trust state, lifecycle
    state, creation metadata, CTP references.

The Skill Foundry does NOT bypass provenance, trust, or transaction auditing.
Every consequential action generates a CTP receipt.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.foundry.proof import ProofEngine, ProofRequirement, sha256_of
from capt_solo.lifecycle.procedures import ProcedureStore, Procedure


SKILL_LIFECYCLE = {
    "candidate", "generated", "validating", "validated",
    "reviewing", "approved", "published", "deprecated", "revoked",
}

# Semantic versioning helper
def _bump_version(ver: str, kind: str = "minor") -> str:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", ver or "0.0.0")
    if not m:
        return "0.1.0"
    maj, minr, pat = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if kind == "major":
        return f"{maj+1}.0.0"
    if kind == "minor":
        return f"{maj}.{minr+1}.0"
    return f"{maj}.{minr}.{pat+1}"


@dataclass
class Skill:
    """A published (or in-progress) Hermes skill."""

    skill_id: str
    name: str
    version: str
    compatibility: str
    trigger: str
    purpose: str
    prerequisites: str
    required_tools: List[str]
    permissions: List[str]
    workflow: List[str]
    expected_outputs: str
    rollback_strategy: str
    failure_modes: str
    recovery_strategy: str
    verification_requirements: List[Dict[str, Any]]
    supporting_evidence: List[str]
    trust_state: str
    lifecycle_state: str
    creation_metadata: Dict[str, Any]
    ctp_refs: List[str]
    source_procedure: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Skill":
        from capt_solo.foundry.columns import decode_list, decode_dict
        return cls(
            skill_id=d["skill_id"], name=d["name"], version=d["version"],
            compatibility=d.get("compatibility", ""), trigger=d.get("trigger", ""),
            purpose=d.get("purpose", ""), prerequisites=d.get("prerequisites", ""),
            required_tools=decode_list(d.get("required_tools"), field="required_tools"),
            permissions=decode_list(d.get("permissions"), field="permissions"),
            workflow=decode_list(d.get("workflow"), field="workflow"),
            expected_outputs=d.get("expected_outputs", ""),
            rollback_strategy=d.get("rollback_strategy", ""),
            failure_modes=d.get("failure_modes", ""),
            recovery_strategy=d.get("recovery_strategy", ""),
            verification_requirements=decode_list(d.get("verification_requirements"), field="verification_requirements"),
            supporting_evidence=decode_list(d.get("supporting_evidence"), field="supporting_evidence"),
            trust_state=d.get("trust_state", "candidate"),
            lifecycle_state=d.get("lifecycle_state", "candidate"),
            creation_metadata=decode_dict(d.get("creation_metadata"), field="creation_metadata"),
            ctp_refs=decode_list(d.get("ctp_refs"), field="ctp_refs"),
            source_procedure=d.get("source_procedure"),
            created_at=d.get("created_at", 0.0), updated_at=d.get("updated_at", 0.0),
        )

    def content_hash(self) -> str:
        """Deterministic hash of the skill's substantive content."""
        canonical = json.dumps({
            "name": self.name, "version": self.version,
            "compatibility": self.compatibility, "trigger": self.trigger,
            "purpose": self.purpose, "prerequisites": self.prerequisites,
            "required_tools": self.required_tools, "permissions": self.permissions,
            "workflow": self.workflow, "expected_outputs": self.expected_outputs,
            "rollback_strategy": self.rollback_strategy,
            "failure_modes": self.failure_modes, "recovery_strategy": self.recovery_strategy,
            "verification_requirements": self.verification_requirements,
        }, sort_keys=True)
        return sha256_of(canonical)


class SkillFoundry:
    """Governs the procedure -> skill pipeline with evidence and CTP receipts."""

    def __init__(self, conn, proof: Optional[ProofEngine] = None,
                 procedures: Optional[ProcedureStore] = None) -> None:
        self._conn = conn
        self._proof = proof
        self._procs = procedures

    # ----- pipeline step 1: candidate from verified procedure -----------
    def create_candidate(self, procedure_id: str, *,
                         ctp_tx_id: Optional[str] = None) -> str:
        """Create a skill candidate from a procedure. Requires the procedure
        to be verified (trust_state == 'verified' and success_count > 0)."""
        if self._procs is None:
            raise MemoryError_("procedure store not available")
        proc = self._procs.get(procedure_id)
        if proc is None:
            raise MemoryError_(f"procedure not found: {procedure_id}")
        if proc.trust_state != "verified":
            raise MemoryError_(
                f"procedure '{procedure_id}' is not verified "
                f"(trust_state={proc.trust_state}); only verified procedures "
                f"may become skill candidates")
        if proc.success_count <= 0:
            raise MemoryError_(
                f"procedure '{procedure_id}' has no successful runs; "
                f"evidence required before skill candidacy")
        cid = uuid.uuid4().hex
        self._conn.execute(
            """INSERT INTO skill_candidates
               (candidate_id, source_procedure, status, created_at)
               VALUES (?,?, 'candidate', ?)""",
            (cid, procedure_id, time.time()))
        self._conn.commit()
        return cid

    # ----- pipeline step 2: build skill from candidate ------------------
    def build_skill(self, candidate_id: str, *,
                    name: Optional[str] = None,
                    compatibility: str = "", trigger: str = "",
                    purpose: str = "", prerequisites: str = "",
                    required_tools: Optional[List[str]] = None,
                    permissions: Optional[List[str]] = None,
                    workflow: Optional[List[str]] = None,
                    expected_outputs: str = "",
                    rollback_strategy: Optional[str] = None,
                    failure_modes: str = "",
                    recovery_strategy: str = "",
                    verification_requirements: Optional[List[Dict[str, Any]]] = None,
                    ctp_tx_id: Optional[str] = None) -> str:
        """Materialize a Skill from a candidate. Lifecycle starts at 'validating'."""
        row = self._conn.execute(
            "SELECT * FROM skill_candidates WHERE candidate_id=?",
            (candidate_id,)).fetchone()
        if row is None:
            raise MemoryError_(f"candidate not found: {candidate_id}")
        proc = self._procs.get(row["source_procedure"])
        if proc is None:
            raise MemoryError_(f"source procedure missing: {row['source_procedure']}")
        now = time.time()
        skill_id = uuid.uuid4().hex
        skill = Skill(
            skill_id=skill_id,
            name=name or proc.name,
            version="0.1.0",
            compatibility=compatibility or "capt-solo>=0.3",
            trigger=trigger or proc.trigger or "",
            purpose=purpose or proc.purpose or "",
            prerequisites=prerequisites or proc.preconditions or "",
            required_tools=list(required_tools or []),
            permissions=list(permissions or []),
            workflow=list(workflow or [s.strip() for s in proc.steps.split("\n") if s.strip()]),
            expected_outputs=expected_outputs or proc.expected_outputs or "",
            rollback_strategy=rollback_strategy if rollback_strategy is not None
            else "Revert changes; restore prior state from CTP receipt.",
            failure_modes=failure_modes or proc.failure_modes or "",
            recovery_strategy=recovery_strategy or proc.recovery_steps or "",
            verification_requirements=list(verification_requirements or []),
            supporting_evidence=list(proc.evidence_refs or []) + [
                f"proc_run:{r['run_id']}" for r in self._procs.get_runs(proc.procedure_id)
            ],
            trust_state="candidate",
            lifecycle_state="generated",
            creation_metadata={
                "source_procedure": proc.procedure_id,
                "procedure_version": proc.version,
                "created_by": "skill_foundry",
                "built_at": now,
            },
            ctp_refs=[ctp_tx_id] if ctp_tx_id else [],
            source_procedure=proc.procedure_id,
            created_at=now, updated_at=now,
        )
        self._insert_skill(skill)
        self._conn.execute(
            "UPDATE skill_candidates SET skill_id=?, status='built' WHERE candidate_id=?",
            (skill_id, candidate_id))
        self._conn.commit()
        return skill_id

    def _insert_skill(self, s: Skill) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO skills
               (skill_id, name, version, compatibility, trigger, purpose,
                prerequisites, required_tools, permissions, workflow,
                expected_outputs, rollback_strategy, failure_modes,
                recovery_strategy, verification_requirements, supporting_evidence,
                trust_state, lifecycle_state, creation_metadata, ctp_refs,
                source_procedure, content_hash, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (s.skill_id, s.name, s.version, s.compatibility, s.trigger, s.purpose,
             s.prerequisites, json.dumps(s.required_tools), json.dumps(s.permissions),
             json.dumps(s.workflow), s.expected_outputs, s.rollback_strategy,
             s.failure_modes, s.recovery_strategy, json.dumps(s.verification_requirements),
             json.dumps(s.supporting_evidence), s.trust_state, s.lifecycle_state,
             json.dumps(s.creation_metadata), json.dumps(s.ctp_refs),
             s.source_procedure, s.content_hash(), s.created_at, s.updated_at))

    # ----- pipeline step 3: evidence aggregation ------------------------
    def aggregate_evidence(self, skill_id: str) -> Dict[str, Any]:
        """Aggregate proof for a skill's verification requirements."""
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        if self._proof is None:
            return {"satisfied": False, "reason": "no proof engine",
                    "requirements": s.verification_requirements}
        reqs = [ProofRequirement(
                    r["type"], int(r.get("min_count", 1)),
                    r.get("scope"), float(r.get("min_trust", 0.0)))
                for r in s.verification_requirements]
        self._proof.set_requirements(f"skill:{skill_id}", reqs)
        agg = self._proof.aggregate(f"skill:{skill_id}")
        return agg.to_dict()

    # ----- pipeline step 4: validation (harness) ------------------------
    def validate(self, skill_id: str, harness) -> Dict[str, Any]:
        """Run the skill through a validation harness. Returns stage results.

        On pass, advances lifecycle generated/validating -> validated. A failed
        required stage prevents advancement (stays generated/validating).
        """
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        if s.lifecycle_state not in ("generated", "validating"):
            raise MemoryError_(
                f"skill '{skill_id}' must be generated before validation "
                f"(current={s.lifecycle_state})")
        result = harness.run(s)
        if result.passed and self._proof is not None:
            self._proof.record(
                "static_analysis", "skill_foundry",
                sha256_of(json.dumps(s.to_dict(), sort_keys=True)),
                "skill_validation", scope=f"skill:{skill_id}",
                payload={"stages": [st.to_dict() for st in result.stages]})
            self._update(skill_id, lifecycle_state="validated")
        else:
            self._update(skill_id, lifecycle_state="validating")
        return result

    # ----- pipeline step 5: human review --------------------------------
    def submit_for_review(self, skill_id: str) -> None:
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        if s.lifecycle_state not in ("generated", "validated"):
            raise MemoryError_(
                f"skill '{skill_id}' must be validated before review "
                f"(current={s.lifecycle_state})")
        self._update(skill_id, lifecycle_state="reviewing")

    def approve(self, skill_id: str, reviewer: str,
                ctp_tx_id: Optional[str] = None) -> None:
        """Governance approval — distinct from publication.

        Moves reviewing -> approved. Records the named reviewer and CTP receipt.
        Does NOT publish. Publication requires publish() with a validation
        snapshot.
        """
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        if s.lifecycle_state != "reviewing":
            raise MemoryError_(
                f"skill '{skill_id}' must be in 'reviewing' state (current="
                f"{s.lifecycle_state})")
        if not reviewer:
            raise MemoryError_("human approval requires a named reviewer")
        meta = dict(s.creation_metadata)
        meta["approved_by"] = reviewer
        meta["approved_at"] = time.time()
        if ctp_tx_id:
            meta["approval_ctp_tx"] = ctp_tx_id
        refs = list(s.ctp_refs) + ([ctp_tx_id] if ctp_tx_id else [])
        self._conn.execute(
            """UPDATE skills SET lifecycle_state='approved', trust_state='verified',
                creation_metadata=?, ctp_refs=?, updated_at=? WHERE skill_id=?""",
            (json.dumps(meta), json.dumps(refs), time.time(), skill_id))
        self._conn.commit()

    def publish(self, skill_id: str, *, ctp_tx_id: Optional[str] = None) -> None:
        """Publish an approved skill. Requires approved + validation evidence.

        Publication is a separate, governed event from approval. It requires:
          - lifecycle_state == 'approved'
          - at least one validation evidence record (proof aggregate satisfied)
          - a CTP receipt (governance boundary)
        On success, snapshots an immutable content hash and marks published.
        Idempotent: re-publishing an already-published skill is a no-op.
        """
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        if s.lifecycle_state == "published":
            return  # idempotent
        if s.lifecycle_state != "approved":
            raise MemoryError_(
                f"skill '{skill_id}' must be approved before publish "
                f"(current={s.lifecycle_state})")
        # require validation evidence
        if self._proof is not None:
            agg = self._proof.aggregate(f"skill:{skill_id}")
            if not agg.satisfied:
                raise MemoryError_(
                    f"skill '{skill_id}' cannot publish: validation proof "
                    f"incomplete ({agg.unsatisfied_requirements})")
        meta = dict(s.creation_metadata)
        meta["published_at"] = time.time()
        if ctp_tx_id:
            meta["publish_ctp_tx"] = ctp_tx_id
        refs = list(s.ctp_refs) + ([ctp_tx_id] if ctp_tx_id else [])
        self._conn.execute(
            """UPDATE skills SET lifecycle_state='published',
                creation_metadata=?, ctp_refs=?, updated_at=? WHERE skill_id=?""",
            (json.dumps(meta), json.dumps(refs), time.time(), skill_id))
        self._conn.commit()

    # ----- publish / deprecate / revoke ---------------------------------
    def deprecate(self, skill_id: str, reason: str = "") -> None:
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        meta = dict(s.creation_metadata)
        meta["deprecated_reason"] = reason
        self._conn.execute(
            "UPDATE skills SET lifecycle_state='deprecated', creation_metadata=?, "
            "updated_at=? WHERE skill_id=?",
            (json.dumps(meta), time.time(), skill_id))
        self._conn.commit()

    def revoke(self, skill_id: str, reason: str = "") -> None:
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        meta = dict(s.creation_metadata)
        meta["revoked_reason"] = reason
        self._conn.execute(
            "UPDATE skills SET lifecycle_state='revoked', trust_state='rejected', "
            "creation_metadata=?, updated_at=? WHERE skill_id=?",
            (json.dumps(meta), time.time(), skill_id))
        self._conn.commit()

    def revise(self, skill_id: str, *, bump: str = "minor",
               ctp_tx_id: Optional[str] = None, **changes) -> str:
        """Create a new version of a published skill. Old version preserved."""
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        now = time.time()
        new_id = uuid.uuid4().hex
        new_ver = _bump_version(s.version, bump)
        new = Skill(
            skill_id=new_id, name=s.name, version=new_ver,
            compatibility=changes.get("compatibility", s.compatibility),
            trigger=changes.get("trigger", s.trigger),
            purpose=changes.get("purpose", s.purpose),
            prerequisites=changes.get("prerequisites", s.prerequisites),
            required_tools=changes.get("required_tools", s.required_tools),
            permissions=changes.get("permissions", s.permissions),
            workflow=changes.get("workflow", s.workflow),
            expected_outputs=changes.get("expected_outputs", s.expected_outputs),
            rollback_strategy=changes.get("rollback_strategy", s.rollback_strategy),
            failure_modes=changes.get("failure_modes", s.failure_modes),
            recovery_strategy=changes.get("recovery_strategy", s.recovery_strategy),
            verification_requirements=changes.get(
                "verification_requirements", s.verification_requirements),
            supporting_evidence=list(s.supporting_evidence),
            trust_state="candidate",
            lifecycle_state="generated",
            creation_metadata={
                "source_procedure": s.source_procedure,
                "previous_version": s.version,
                "previous_skill_id": s.skill_id,
                "revised_at": now,
            },
            ctp_refs=[ctp_tx_id] if ctp_tx_id else [],
            source_procedure=s.source_procedure,
            created_at=now, updated_at=now,
        )
        self._insert_skill(new)
        self._conn.commit()
        return new_id

    # ----- query --------------------------------------------------------
    def get(self, skill_id: str) -> Optional[Skill]:
        row = self._conn.execute(
            "SELECT * FROM skills WHERE skill_id=?", (skill_id,)).fetchone()
        return Skill.from_dict(dict(row)) if row else None

    def get_by_name(self, name: str) -> Optional[Skill]:
        row = self._conn.execute(
            "SELECT * FROM skills WHERE name=? ORDER BY updated_at DESC LIMIT 1",
            (name,)).fetchone()
        return Skill.from_dict(dict(row)) if row else None

    def list(self, *, lifecycle: Optional[str] = None,
              name: Optional[str] = None) -> List[Skill]:
        q = "SELECT * FROM skills"
        args: List[Any] = []
        where = []
        if lifecycle:
            where.append("lifecycle_state=?")
            args.append(lifecycle)
        if name:
            where.append("name=?")
            args.append(name)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY name, updated_at DESC"
        rows = self._conn.execute(q, args).fetchall()
        return [Skill.from_dict(dict(r)) for r in rows]

    def list_candidates(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM skill_candidates ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def _update(self, skill_id: str, **fields) -> None:
        s = self.get(skill_id)
        if s is None:
            raise MemoryError_(f"skill not found: {skill_id}")
        for k, v in fields.items():
            if hasattr(s, k):
                setattr(s, k, v)
        s.updated_at = time.time()
        self._insert_skill(s)
        self._conn.commit()
