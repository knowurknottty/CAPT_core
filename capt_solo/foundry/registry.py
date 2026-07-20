"""CAPT Solo v0.4 — Capability Registry.

Every capability CAPT can perform is registered here with explicit evidence,
trust, lifecycle, and degradation state. The registry is the single source of
truth for "can CAPT do X?" — ClaimGuard queries it before any completion claim.

Lifecycle states:
    candidate, validated, verified, deprecated, revoked, degraded, experimental

A capability is NEVER reported as Verified unless its ProofEngine aggregate is
satisfied. Degraded/Revoked capabilities are reported with downgraded language.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from capt_solo.core.errors import MemoryError_
from capt_solo.foundry.proof import ProofEngine, ProofRequirement


# Explicit degradation reason codes. Each carries a default human-readable
# explanation; operators may supply a more specific one at degradation time.
DEGRADATION_REASONS = {
    "dependency_missing": "A required dependency is no longer available.",
    "environment_changed": "The runtime environment changed in a way that invalidates prior verification.",
    "proof_expired": "The supporting proof evidence has expired or is stale.",
    "compatibility_failed": "The capability is incompatible with the current platform/version.",
    "security_revoked": "The capability was revoked for a security reason.",
    "manual_disable": "The capability was manually disabled by an operator.",
    "superseded": "The capability has been superseded by a newer implementation.",
    "verification_failed": "Re-verification of the capability failed.",
    "component_degraded": "A component skill or sub-capability was degraded.",
    "tool_contract_changed": "The underlying tool's contract changed incompatibly.",
    "permission_policy_changed": "The permission policy no longer permits this capability.",
    "artifact_missing": "A required artifact (binary, model, data file) is missing.",
}


CAPABILITY_LIFECYCLE = {
    "candidate", "validated", "verified", "deprecated",
    "revoked", "degraded", "experimental",
}

# Claims that require proof before they may be stated as fact.
PROOF_REQUIRED_CLAIMS = {
    "complete", "completed", "fixed", "migrated", "production-ready",
    "tested", "secure", "verified", "successful", "ready",
}


@dataclass
class Capability:
    identifier: str
    description: str
    provider: str
    required_environment: str = ""
    required_tools: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    supported_versions: List[str] = field(default_factory=list)
    trust: float = 0.0
    lifecycle: str = "candidate"
    evidence: List[str] = field(default_factory=list)  # evidence_ids
    last_verification: float = 0.0
    degradation_state: str = "none"  # none | partial | full
    compatibility_matrix: Dict[str, str] = field(default_factory=dict)
    creation_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Capability":
        from capt_solo.foundry.columns import decode_list, decode_dict
        return cls(
            identifier=d["identifier"], description=d["description"],
            provider=d["provider"], required_environment=d.get("required_environment", ""),
            required_tools=decode_list(d.get("required_tools"), field="required_tools"),
            permissions=decode_list(d.get("permissions"), field="permissions"),
            dependencies=decode_list(d.get("dependencies"), field="dependencies"),
            supported_versions=decode_list(d.get("supported_versions"), field="supported_versions"),
            trust=d.get("trust", 0.0), lifecycle=d.get("lifecycle", "candidate"),
            evidence=decode_list(d.get("evidence"), field="evidence"),
            last_verification=d.get("last_verification", 0.0),
            degradation_state=d.get("degradation_state", "none"),
            compatibility_matrix=decode_dict(d.get("compatibility_matrix"), field="compatibility_matrix"),
            creation_metadata=decode_dict(d.get("creation_metadata"), field="creation_metadata"),
            created_at=d.get("created_at", 0.0), updated_at=d.get("updated_at", 0.0),
        )


class CapabilityRegistry:
    """SQLite-backed registry of demonstrable capabilities."""

    def __init__(self, conn, proof: Optional[ProofEngine] = None) -> None:
        self._conn = conn
        self.proof = proof

    # ----- register / update -------------------------------------------
    def register(self, identifier: str, description: str, provider: str,
                 **kwargs) -> Capability:
        now = time.time()
        cap = Capability(
            identifier=identifier, description=description, provider=provider,
            required_environment=kwargs.get("required_environment", ""),
            required_tools=list(kwargs.get("required_tools", [])),
            permissions=list(kwargs.get("permissions", [])),
            dependencies=list(kwargs.get("dependencies", [])),
            supported_versions=list(kwargs.get("supported_versions", [])),
            trust=kwargs.get("trust", 0.0),
            lifecycle=kwargs.get("lifecycle", "candidate"),
            evidence=list(kwargs.get("evidence", [])),
            last_verification=kwargs.get("last_verification", 0.0),
            degradation_state=kwargs.get("degradation_state", "none"),
            compatibility_matrix=dict(kwargs.get("compatibility_matrix", {})),
            creation_metadata=dict(kwargs.get("creation_metadata", {})),
            created_at=now, updated_at=now)
        self._conn.execute(
            """INSERT OR REPLACE INTO capabilities
               (identifier, description, provider, required_environment,
                required_tools, permissions, dependencies, supported_versions,
                trust, lifecycle, evidence, last_verification, degradation_state,
                compatibility_matrix, creation_metadata, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cap.identifier, cap.description, cap.provider, cap.required_environment,
             json.dumps(cap.required_tools), json.dumps(cap.permissions),
             json.dumps(cap.dependencies), json.dumps(cap.supported_versions),
             cap.trust, cap.lifecycle, json.dumps(cap.evidence),
             cap.last_verification, cap.degradation_state,
             json.dumps(cap.compatibility_matrix), json.dumps(cap.creation_metadata),
             cap.created_at, cap.updated_at))
        self._conn.commit()
        return cap

    def update(self, identifier: str, **kwargs) -> Capability:
        cap = self.get(identifier)
        if cap is None:
            raise MemoryError_(f"capability not found: {identifier}")
        for k, v in kwargs.items():
            if hasattr(cap, k):
                setattr(cap, k, v)
        cap.updated_at = time.time()
        self._conn.execute(
            """UPDATE capabilities SET description=?, provider=?, required_environment=?,
                required_tools=?, permissions=?, dependencies=?, supported_versions=?,
                trust=?, lifecycle=?, evidence=?, last_verification=?, degradation_state=?,
                compatibility_matrix=?, creation_metadata=?, updated_at=? WHERE identifier=?""",
            (cap.description, cap.provider, cap.required_environment,
             json.dumps(cap.required_tools), json.dumps(cap.permissions),
             json.dumps(cap.dependencies), json.dumps(cap.supported_versions),
             cap.trust, cap.lifecycle, json.dumps(cap.evidence),
             cap.last_verification, cap.degradation_state,
             json.dumps(cap.compatibility_matrix), json.dumps(cap.creation_metadata),
             cap.updated_at, cap.identifier))
        self._conn.commit()
        return cap

    # ----- query --------------------------------------------------------
    def get(self, identifier: str) -> Optional[Capability]:
        row = self._conn.execute(
            "SELECT * FROM capabilities WHERE identifier=?",
            (identifier,)).fetchone()
        return Capability.from_dict(dict(row)) if row else None

    def list(self, *, lifecycle: Optional[str] = None) -> List[Capability]:
        if lifecycle:
            rows = self._conn.execute(
                "SELECT * FROM capabilities WHERE lifecycle=? ORDER BY identifier",
                (lifecycle,)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM capabilities ORDER BY identifier").fetchall()
        return [Capability.from_dict(dict(r)) for r in rows]

    def query(self, claim: str) -> Optional[Capability]:
        """Find a capability whose identifier or description matches a claim.

        Used by ClaimGuard: before asserting a capability, look it up.
        """
        claim_l = claim.lower()
        for cap in self.list():
            if cap.identifier.lower() == claim_l or claim_l in cap.description.lower():
                return cap
        return None

    # ----- verification linkage ----------------------------------------
    def verify(self, identifier: str, proof: ProofEngine,
               requirements: List[ProofRequirement]) -> Dict[str, Any]:
        """Validate proof requirements and promote candidate -> validated.

        Lifecycle semantics (explicit, idempotent):
            candidate --(proof requirements satisfied)--> validated
            validated --(mark_proven: proof still satisfied)--> proven
            proven --(govern_approve: DISTINCT governance event)--> verified

        A repeated verify() call with unchanged evidence is IDEMPOTENT: a
        'validated' capability stays 'validated' (it does NOT auto-advance to
        'proven'). Only mark_proven() advances validated -> proven, and only
        govern_approve() advances proven -> verified. This prevents "call
        verify twice" from independently increasing epistemic status.
        """
        cap = self.get(identifier)
        if cap is None:
            raise MemoryError_(f"capability not found: {identifier}")
        proof.set_requirements(identifier, requirements)
        agg = proof.aggregate(identifier)
        promoted = False
        if agg.satisfied:
            if cap.lifecycle in ("candidate", "experimental"):
                cap.lifecycle = "validated"
                promoted = True
            # validated/proven/verified/degraded: unchanged evidence does NOT advance
            cap.trust = min(1.0, 0.5 + 0.5 * (agg.evidence_count / max(
                1, sum(r["min_count"] for r in agg.satisfied_requirements))))
            cap.last_verification = time.time()
        else:
            # evidence incomplete: downgrade, do not claim verified/proven
            if cap.lifecycle == "verified":
                cap.lifecycle = "degraded"
                cap.degradation_state = "partial"
            elif cap.lifecycle in ("proven", "validated"):
                cap.lifecycle = "candidate"
        self.update(identifier, lifecycle=cap.lifecycle, trust=cap.trust,
                    evidence=cap.evidence, last_verification=cap.last_verification,
                    degradation_state=cap.degradation_state)
        return {"aggregate": agg.to_dict(), "lifecycle": cap.lifecycle,
                "trust": cap.trust, "promoted": promoted}

    def mark_proven(self, identifier: str) -> Dict[str, Any]:
        """DISTINCT event: validated -> proven once proof is satisfied.

        Requires the capability to be 'validated' with satisfied proof. This is
        a separate, explicit step from verify() (which only reaches 'validated')
        and from govern_approve() (which reaches 'verified'). Idempotent: a
        'proven' or 'verified' capability is unchanged.
        """
        cap = self.get(identifier)
        if cap is None:
            raise MemoryError_(f"capability not found: {identifier}")
        if cap.lifecycle in ("proven", "verified"):
            return {"lifecycle": cap.lifecycle, "promoted": False,
                    "reason": "already proven/verified (idempotent)"}
        if cap.lifecycle != "validated":
            raise MemoryError_(
                f"cannot mark_proven '{identifier}': must be 'validated' "
                f"(current='{cap.lifecycle}')")
        cap.lifecycle = "proven"
        self.update(identifier, lifecycle=cap.lifecycle)
        return {"lifecycle": "proven", "promoted": True,
                "reason": "proof satisfied; marked proven"}

    def govern_approve(self, identifier: str, approver: str,
                       ctp_tx_id: Optional[str] = None) -> Dict[str, Any]:
        """DISTINCT event: move proven -> verified via explicit governance approval.

        Requires the capability to be in 'proven' state (proof already
        satisfied). Records the approver and CTP receipt. Idempotent: calling
        again on an already-verified capability is a no-op (returns current state).
        """
        cap = self.get(identifier)
        if cap is None:
            raise MemoryError_(f"capability not found: {identifier}")
        if cap.lifecycle == "verified":
            return {"lifecycle": "verified", "promoted": False,
                    "reason": "already verified (idempotent)"}
        if cap.lifecycle != "proven":
            raise MemoryError_(
                f"cannot govern-approve '{identifier}': must be 'proven' "
                f"(current='{cap.lifecycle}'); proof requirements must be "
                f"satisfied first via verify() then mark_proven()")
        if not approver:
            raise MemoryError_("governance approval requires a named approver")
        cap.lifecycle = "verified"
        cap.trust = min(1.0, cap.trust + 0.1)
        meta = dict(cap.creation_metadata)
        meta["governance_approved_by"] = approver
        meta["governance_approved_at"] = time.time()
        if ctp_tx_id:
            meta["governance_ctp_tx"] = ctp_tx_id
        self.update(identifier, lifecycle=cap.lifecycle, trust=cap.trust,
                    creation_metadata=meta)
        return {"lifecycle": "verified", "promoted": True,
                "reason": "governance approval recorded"}

    def set_degraded(self, identifier: str, state: str = "partial") -> None:
        self.update(identifier, lifecycle="degraded", degradation_state=state)

    def degrade(self, identifier: str, reason: str, *,
                explanation: str = "", affected_scope: str = "global",
                triggering_evidence: str = "", previous_state: str = "",
                actor: str = "system", remediation: str = "",
                ctp_tx_id: Optional[str] = None) -> Dict[str, Any]:
        """Record a structured capability degradation with an explicit reason code.

        Reason codes (see DEGRADATION_REASONS): dependency_missing,
        environment_changed, proof_expired, compatibility_failed,
        security_revoked, manual_disable, superseded, verification_failed,
        component_degraded, tool_contract_changed, permission_policy_changed,
        artifact_missing.

        A degradation record captures: reason code, human-readable
        explanation, affected scope, triggering evidence, previous state,
        resulting state, timestamp, actor, remediation guidance, and an
        optional CTP receipt. The capability moves to 'degraded' (or 'revoked'
        for security_revoked) and its degradation_state is set to the reason.
        """
        if reason not in DEGRADATION_REASONS:
            raise MemoryError_(f"unknown degradation reason: {reason}")
        cap = self.get(identifier)
        if cap is None:
            raise MemoryError_(f"capability not found: {identifier}")
        previous = cap.lifecycle
        resulting = "revoked" if reason == "security_revoked" else "degraded"
        record = {
            "capability": identifier,
            "reason": reason,
            "explanation": explanation or DEGRADATION_REASONS[reason],
            "affected_scope": affected_scope,
            "triggering_evidence": triggering_evidence,
            "previous_state": previous_state or previous,
            "resulting_state": resulting,
            "timestamp": time.time(),
            "actor": actor,
            "remediation": remediation,
            "ctp_tx_id": ctp_tx_id,
        }
        self._conn.execute(
            """INSERT INTO capability_degradations
               (capability, reason, record, created_at)
               VALUES (?,?,?,?)""",
            (identifier, reason, json.dumps(record), record["timestamp"]))
        self.update(identifier, lifecycle=resulting, degradation_state=reason)
        return record

    def get_degradations(self, identifier: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT record FROM capability_degradations WHERE capability=? "
            "ORDER BY created_at DESC", (identifier,)).fetchall()
        return [json.loads(r["record"]) for r in rows]

    def revoke(self, identifier: str) -> None:
        self.update(identifier, lifecycle="revoked", degradation_state="full")

    def deprecate(self, identifier: str) -> None:
        self.update(identifier, lifecycle="deprecated")
