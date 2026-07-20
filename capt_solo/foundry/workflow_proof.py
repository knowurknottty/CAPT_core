"""CAPT Solo v0.4 — Workflow Proof Engine.

A composite workflow does NOT inherit verification merely because its child
skills are verified. Each composed workflow carries a first-class proof
record that is evaluated independently.

Lifecycle (distinct, idempotent where specified):
    candidate -> validated -> proven -> approved -> verified
    -> degraded / deprecated / revoked

Repeated evaluation against unchanged evidence is idempotent: a workflow that
is already ``validated`` stays ``validated`` when re-checked with the same
evidence. A workflow may remain ``candidate`` (unverified) even when all
component skills are individually verified.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.foundry.columns import decode_dict, decode_list
from capt_solo.foundry.skill_foundry import SkillFoundry
from capt_solo.foundry.proof import ProofEngine

WORKFLOW_LIFECYCLE = (
    "candidate", "validated", "proven", "approved", "verified",
    "degraded", "deprecated", "revoked",
)


@dataclass
class WorkflowProof:
    workflow_id: str
    version: str
    components: List[Dict[str, Any]]          # ordered skill id+version+proof ref
    component_proof_refs: List[str]
    io_compatibility: Dict[str, Any]
    dependency_validation: Dict[str, Any]
    permission_union: List[str]
    permission_escalation: List[str]          # findings (non-empty => blocked)
    environment_compatibility: Dict[str, Any]
    transaction_boundary: Dict[str, Any]
    rollback_compatibility: Dict[str, Any]
    integration_evidence: List[str]
    failure_path_evidence: List[str]
    output_contract_evidence: List[str]
    lifecycle_state: str = "candidate"
    verifier: str = ""
    governance_ref: str = ""
    ctp_receipt: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "version": self.version,
            "components": self.components,
            "component_proof_refs": self.component_proof_refs,
            "io_compatibility": self.io_compatibility,
            "dependency_validation": self.dependency_validation,
            "permission_union": self.permission_union,
            "permission_escalation": self.permission_escalation,
            "environment_compatibility": self.environment_compatibility,
            "transaction_boundary": self.transaction_boundary,
            "rollback_compatibility": self.rollback_compatibility,
            "integration_evidence": self.integration_evidence,
            "failure_path_evidence": self.failure_path_evidence,
            "output_contract_evidence": self.output_contract_evidence,
            "lifecycle_state": self.lifecycle_state,
            "verifier": self.verifier,
            "governance_ref": self.governance_ref,
            "ctp_receipt": self.ctp_receipt,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowProof":
        return cls(
            workflow_id=d["workflow_id"],
            version=d.get("version", "1.0.0"),
            components=decode_list(d.get("components"), field="components"),
            component_proof_refs=decode_list(d.get("component_proof_refs"),
                                            field="component_proof_refs"),
            io_compatibility=decode_dict(d.get("io_compatibility"),
                                         field="io_compatibility"),
            dependency_validation=decode_dict(d.get("dependency_validation"),
                                              field="dependency_validation"),
            permission_union=decode_list(d.get("permission_union"),
                                        field="permission_union"),
            permission_escalation=decode_list(d.get("permission_escalation"),
                                              field="permission_escalation"),
            environment_compatibility=decode_dict(d.get("environment_compatibility"),
                                                  field="environment_compatibility"),
            transaction_boundary=decode_dict(d.get("transaction_boundary"),
                                            field="transaction_boundary"),
            rollback_compatibility=decode_dict(d.get("rollback_compatibility"),
                                               field="rollback_compatibility"),
            integration_evidence=decode_list(d.get("integration_evidence"),
                                             field="integration_evidence"),
            failure_path_evidence=decode_list(d.get("failure_path_evidence"),
                                              field="failure_path_evidence"),
            output_contract_evidence=decode_list(d.get("output_contract_evidence"),
                                                 field="output_contract_evidence"),
            lifecycle_state=d.get("lifecycle_state", "candidate"),
            verifier=d.get("verifier", ""),
            governance_ref=d.get("governance_ref", ""),
            ctp_receipt=d.get("ctp_receipt", ""),
            created_at=d.get("created_at", 0.0),
            updated_at=d.get("updated_at", 0.0),
        )


class WorkflowProofEngine:
    """Evaluates and stores independent proof for composite workflows."""

    def __init__(self, conn, foundry: SkillFoundry,
                 proof: Optional[ProofEngine] = None) -> None:
        self._conn = conn
        self._sf = foundry
        self._proof = proof

    # ----- evaluation ----------------------------------------------------
    def evaluate(self, workflow_id: str, version: str,
                 step_skill_ids: List[str],
                 mappings: Optional[List[Dict[str, Any]]] = None,
                 verifier: str = "system") -> WorkflowProof:
        """Independently evaluate a workflow's proof. Does NOT inherit child
        skill verification. Returns a WorkflowProof in ``candidate`` state
        (caller must persist + advance lifecycle explicitly)."""
        mappings = mappings or [{} for _ in step_skill_ids]
        skills = []
        for sid in step_skill_ids:
            s = self._sf.get(sid)
            if s is None:
                raise MemoryError_(f"workflow references missing skill: {sid}")
            skills.append(s)

        # component inventory (id + version + proof ref)
        components = []
        proof_refs = []
        for s in skills:
            ref = f"skill_proof:{s.skill_id}:{s.version}"
            components.append({
                "skill_id": s.skill_id, "version": s.version,
                "proof_ref": ref,
                "supporting_evidence": list(s.supporting_evidence),
            })
            proof_refs.append(ref)

        # I/O compatibility: each step's claimed prior-step input must exist
        io_ok = True
        io_detail: Dict[str, Any] = {"ok": True, "issues": []}
        prior_outputs = set()
        for i, m in enumerate(mappings):
            ins = set(m.get("input_mapping", {}).values())
            claimed = {v for v in ins if v.startswith("step:")}
            for c in claimed:
                src = int(c.split(":")[1])
                if src >= i:
                    io_ok = False
                    io_detail["issues"].append(
                        f"step {i} claims input from step {src} (forward ref)")
        io_detail["ok"] = io_ok

        # dependency graph: linear order is acyclic by construction
        dep_detail = {"acyclic": True, "nodes": len(skills),
                      "edges": max(0, len(skills) - 1)}

        # permission union + escalation detection
        union: List[str] = []
        escalation: List[str] = []
        for s in skills:
            for p in s.permissions:
                if p not in union:
                    union.append(p)
        # escalation: a composed permission not individually held by any step
        # is impossible by construction (union of step perms); we surface any
        # permission that is broader than the documented allowed set.
        from capt_solo.foundry.harness import ALLOWED_PERMISSIONS
        for p in union:
            if p not in ALLOWED_PERMISSIONS:
                escalation.append(f"disallowed permission in union: {p}")

        # environment compatibility: all steps share compatible compatibility tag
        env_tags = {s.compatibility for s in skills if s.compatibility}
        env_detail = {"compatible": True, "tags": sorted(env_tags)}
        if len(env_tags) > 1:
            env_detail["compatible"] = False

        # transaction boundary: each step may open its own CTP tx (structural)
        tx_detail = {"per_step_tx": True, "boundary_ok": True}

        # rollback compatibility: every step must declare a rollback strategy
        rb_ok = all(len(s.rollback_strategy or "") >= 10 for s in skills)
        rb_detail = {"compatible": rb_ok,
                     "missing": [s.skill_id for s in skills
                                 if len(s.rollback_strategy or "") < 10]}

        now = time.time()
        return WorkflowProof(
            workflow_id=workflow_id, version=version,
            components=components, component_proof_refs=proof_refs,
            io_compatibility=io_detail,
            dependency_validation=dep_detail,
            permission_union=union, permission_escalation=escalation,
            environment_compatibility=env_detail,
            transaction_boundary=tx_detail,
            rollback_compatibility=rb_detail,
            integration_evidence=[], failure_path_evidence=[],
            output_contract_evidence=[],
            lifecycle_state="candidate", verifier=verifier,
            created_at=now, updated_at=now)

    # ----- persistence ---------------------------------------------------
    def save(self, wp: WorkflowProof) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO workflow_proofs
               (workflow_id, version, definition, lifecycle_state,
                verifier, governance_ref, ctp_receipt, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (wp.workflow_id, wp.version, json.dumps(wp.to_dict()),
             wp.lifecycle_state, wp.verifier, wp.governance_ref,
             wp.ctp_receipt, wp.created_at, wp.updated_at))
        self._conn.commit()

    def get(self, workflow_id: str) -> Optional[WorkflowProof]:
        row = self._conn.execute(
            "SELECT definition FROM workflow_proofs WHERE workflow_id=?",
            (workflow_id,)).fetchone()
        if row is None:
            return None
        return WorkflowProof.from_dict(json.loads(row["definition"]))

    def set_lifecycle(self, workflow_id: str, state: str,
                      governance_ref: str = "", ctp_receipt: str = "") -> None:
        if state not in WORKFLOW_LIFECYCLE:
            raise MemoryError_(f"invalid workflow lifecycle: {state}")
        wp = self.get(workflow_id)
        if wp is None:
            raise MemoryError_(f"workflow proof not found: {workflow_id}")
        wp.lifecycle_state = state
        wp.governance_ref = governance_ref or wp.governance_ref
        wp.ctp_receipt = ctp_receipt or wp.ctp_receipt
        wp.updated_at = time.time()
        self.save(wp)

    def record_evidence(self, workflow_id: str, kind: str,
                        evidence_id: str) -> None:
        """Attach an evidence id to one of the three evidence lists. Idempotent."""
        wp = self.get(workflow_id)
        if wp is None:
            raise MemoryError_(f"workflow proof not found: {workflow_id}")
        bucket = {
            "integration": "integration_evidence",
            "failure_path": "failure_path_evidence",
            "output_contract": "output_contract_evidence",
        }.get(kind)
        if bucket is None:
            raise MemoryError_(f"unknown evidence kind: {kind}")
        lst = list(getattr(wp, bucket))
        if evidence_id not in lst:
            lst.append(evidence_id)
            setattr(wp, bucket, lst)
            wp.updated_at = time.time()
            self.save(wp)
