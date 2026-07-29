"""Small, deterministic CVE v0.2 evaluator.

This is an evidence-runtime, not a policy bypass.  Missing, stale, invalid, or
concentrated evidence cannot produce PASS.  It accepts JSON-compatible packs
so users can inspect, export, fork, or delete all continuity records locally.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import yaml


class ContinuityError(ValueError):
    pass


class ContinuityTier(str, Enum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"


class EvaluationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"
    EXPIRED_EVIDENCE = "EXPIRED_EVIDENCE"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class HandoffState(str, Enum):
    PREPARED = "prepared"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVOKED = "revoked"


_REQUIRED_PACK = {
    "pack_id", "component", "tier", "scope", "roles", "claims", "evidence",
    "created_at", "policy_id",
}
_SECRET_KEY = re.compile(r"(secret|token|password|private[_-]?key|credential)", re.I)
_SECRET_VALUE = re.compile(r"(?:sk-|ghp_|AKIA)[A-Za-z0-9_\-]{12,}")
_VALID_EVIDENCE = {"current", "verified", "pass"}
_INVALID_EVIDENCE = {"invalid", "invalidated", "conflicted", "quarantined"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _contains_secret(value: Any, key: str = "") -> bool:
    if _SECRET_KEY.search(key):
        return True
    if isinstance(value, str):
        return bool(_SECRET_VALUE.search(value))
    if isinstance(value, dict):
        return any(_contains_secret(v, str(k)) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_secret(v) for v in value)
    return False


def _parse_time(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ContinuityError(f"invalid ISO-8601 timestamp: {text!r}") from exc


@dataclass
class ContinuityEvidence:
    evidence_id: str
    kind: str
    status: str
    source: str
    collected_at: str
    verifier: str = ""
    expires_at: str = ""
    invalidation_reason: str = ""
    controls: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ContinuityEvidence":
        missing = {"evidence_id", "kind", "status", "source", "collected_at"} - set(raw)
        if missing:
            raise ContinuityError("evidence missing: " + ", ".join(sorted(missing)))
        return cls(**{k: raw.get(k, []) if k == "controls" else raw.get(k, "")
                      for k in cls.__dataclass_fields__})

    def evaluation_status(self, now: Optional[datetime] = None) -> EvaluationStatus:
        if self.status.lower() in _INVALID_EVIDENCE or self.invalidation_reason:
            return EvaluationStatus.INVALID_EVIDENCE
        if self.expires_at and _parse_time(self.expires_at) <= (now or datetime.now(timezone.utc)):
            return EvaluationStatus.EXPIRED_EVIDENCE
        if self.status.lower() not in _VALID_EVIDENCE:
            return EvaluationStatus.UNKNOWN
        return EvaluationStatus.PASS


@dataclass
class ContinuityPack:
    pack_id: str
    component: str
    tier: str
    scope: str
    roles: List[Dict[str, Any]]
    claims: List[Dict[str, Any]]
    evidence: List[ContinuityEvidence]
    created_at: str
    policy_id: str
    handoff: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ContinuityPack":
        missing = _REQUIRED_PACK - set(raw)
        if missing:
            raise ContinuityError("pack missing: " + ", ".join(sorted(missing)))
        if _contains_secret(raw):
            raise ContinuityError("pack contains a secret-bearing field or value")
        try:
            tier = ContinuityTier(raw["tier"])
        except ValueError as exc:
            raise ContinuityError("tier must be one of C0, C1, C2, C3") from exc
        _parse_time(raw["created_at"])
        evidence = [ContinuityEvidence.from_dict(x) for x in raw["evidence"]]
        return cls(pack_id=raw["pack_id"], component=raw["component"], tier=tier.value,
                   scope=raw["scope"], roles=list(raw["roles"]), claims=list(raw["claims"]),
                   evidence=evidence, created_at=raw["created_at"], policy_id=raw["policy_id"],
                   handoff=dict(raw.get("handoff", {})), metadata=dict(raw.get("metadata", {})))

    def to_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        data["evidence"] = [e.__dict__ for e in self.evidence]
        return data


@dataclass
class ContinuityReceipt:
    receipt_version: str
    pack_id: str
    policy_digest: str
    pack_digest: str
    outcome: str
    created_at: str
    evaluator: str = "capt-solo-cve-v0.2"

    def to_dict(self) -> Dict[str, str]:
        return self.__dict__.copy()


def load_policy(path: Union[str, Path]) -> Dict[str, Any]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContinuityError(f"policy load failed: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("csl_version") != "0.2":
        raise ContinuityError("policy must be a CSL v0.2 mapping")
    articles = raw.get("articles")
    if not isinstance(articles, list) or len(articles) != 9:
        raise ContinuityError("policy must define exactly nine constitutional clauses")
    ids = [a.get("id") for a in articles if isinstance(a, dict)]
    if len(set(ids)) != 9 or any(not x for x in ids):
        raise ContinuityError("policy clause IDs must be non-empty and unique")
    return raw


def validate_pack(pack: ContinuityPack, policy: Dict[str, Any]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    if pack.policy_id != policy.get("policy_id"):
        findings.append({"status": "BLOCK", "code": "policy_mismatch", "detail": "pack policy_id differs from loaded policy"})
    role_ids = [str(r.get("identity", "")) for r in pack.roles]
    if not role_ids or any(not x for x in role_ids):
        findings.append({"status": "BLOCK", "code": "role_identity_missing", "detail": "every role needs a stable identity"})
    if len(role_ids) != len(set(role_ids)):
        findings.append({"status": "BLOCK", "code": "role_independence_failed", "detail": "one identity cannot satisfy multiple independent roles"})
    required_roles = {"operator", "reviewer"} if pack.tier in {"C1", "C2", "C3"} else {"operator"}
    have_roles = {str(r.get("role", "")) for r in pack.roles}
    if not required_roles <= have_roles:
        findings.append({"status": "BLOCK", "code": "required_role_missing", "detail": "tier requires: " + ", ".join(sorted(required_roles))})
    if pack.tier in {"C2", "C3"} and not pack.handoff:
        findings.append({"status": "BLOCK", "code": "handoff_missing", "detail": "C2/C3 needs a reversible handoff record"})
    expected = pack.metadata.get("expected_provider_versions")
    observed = pack.metadata.get("provider_versions")
    if expected is not None and expected != observed:
        findings.append({"status": "BLOCK", "code": "provider_version_mismatch",
                         "detail": "provider versions differ from the pack's declared expectation"})
    return findings


def _concentration(evidence: Iterable[ContinuityEvidence]) -> Dict[str, Any]:
    sources = [e.source for e in evidence if e.source]
    total = len(sources)
    largest = max((sources.count(s) for s in set(sources)), default=0)
    return {"total": total, "distinct_sources": len(set(sources)),
            "largest_source_share": (largest / total) if total else 1.0}


_CLAUSES_BY_CODE = {
    "policy_mismatch": ["CVE-08"], "role_identity_missing": ["CVE-05", "CVE-07"],
    "role_independence_failed": ["CVE-07"], "required_role_missing": ["CVE-07"],
    "handoff_missing": ["CVE-09"], "evidence_missing": ["CVE-02", "CVE-06"],
    "invalid_evidence": ["CVE-02", "CVE-06"], "expired_evidence": ["CVE-06"],
    "unknown_evidence": ["CVE-02"], "clock_skew": ["CVE-02", "CVE-06"],
    "provider_version_mismatch": ["CVE-08"], "evidence_concentration": ["CVE-07"],
}
_REMEDIATION_BY_CODE = {
    "policy_mismatch": "rebuild the pack against the loaded policy",
    "role_identity_missing": "supply stable, inspectable role identities",
    "role_independence_failed": "assign independent operator and reviewer identities",
    "required_role_missing": "supply every role required by the selected tier",
    "handoff_missing": "record a reversible handoff before evaluating this tier",
    "evidence_missing": "collect evidence through an approved provider or external pack",
    "invalid_evidence": "replace invalidated evidence and preserve its invalidation reason",
    "expired_evidence": "collect fresh evidence for the same claim",
    "unknown_evidence": "verify the evidence status before evaluating",
    "clock_skew": "correct the source clock or collect evidence after clock reconciliation",
    "provider_version_mismatch": "recollect evidence or update the declared provider-version expectation",
    "evidence_concentration": "add an independent evidence source or lower the tier",
}


def _explain(findings: List[Dict[str, str]], evidence: List[ContinuityEvidence],
             metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    supporting = sorted(item.evidence_id for item in evidence)
    nodes = {str(node.get("node_id")): node for node in
             metadata.get("evidence_graph", {}).get("nodes", []) if isinstance(node, dict)}
    def graph_path() -> List[str]:
        if not supporting: return ["graph:missing-evidence"]
        path = [supporting[0]]
        while nodes.get(path[-1], {}).get("dependencies"):
            path.append(sorted(nodes[path[-1]]["dependencies"])[0])
        return path
    return [{"code": item["code"], "violated_clauses": _CLAUSES_BY_CODE.get(item["code"], []),
             "supporting_evidence": supporting, "missing_evidence": [] if item["code"] not in
             {"evidence_missing", "unknown_evidence"} else ["verified provider evidence"],
             "graph_path": graph_path(), "recommended_remediation": _REMEDIATION_BY_CODE.get(item["code"], "inspect the finding"),
             "confidence": 1.0 if item["status"] == "BLOCK" else 0.5} for item in findings]


def evaluate_pack(pack: ContinuityPack, policy: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    findings = validate_pack(pack, policy)
    statuses = [e.evaluation_status(now) for e in pack.evidence]
    evaluated_at = now or datetime.now(timezone.utc)
    if not pack.evidence:
        findings.append({"status": "BLOCK", "code": "evidence_missing", "detail": "no evidence supplied"})
    elif EvaluationStatus.INVALID_EVIDENCE in statuses:
        findings.append({"status": "BLOCK", "code": "invalid_evidence", "detail": "an evidence record is invalidated or conflicted"})
    elif EvaluationStatus.EXPIRED_EVIDENCE in statuses:
        findings.append({"status": "BLOCK", "code": "expired_evidence", "detail": "an evidence record has expired"})
    elif EvaluationStatus.UNKNOWN in statuses:
        findings.append({"status": "BLOCK", "code": "unknown_evidence", "detail": "evidence is not verified/current"})
    if any(_parse_time(e.collected_at) > evaluated_at for e in pack.evidence):
        findings.append({"status": "BLOCK", "code": "clock_skew", "detail": "evidence timestamp is later than evaluation time"})
    concentration = _concentration(pack.evidence)
    if pack.tier in {"C2", "C3"} and concentration["largest_source_share"] > 0.8:
        findings.append({"status": "WARN", "code": "evidence_concentration", "detail": "over 80% of evidence comes from one source"})
    state = EvaluationStatus.PASS
    if any(x["status"] == "BLOCK" for x in findings):
        state = EvaluationStatus.BLOCK
    elif findings:
        state = EvaluationStatus.WARN
    receipt = ContinuityReceipt("0.2", pack.pack_id, digest(policy), digest(pack.to_dict()), state.value,
                                evaluated_at.isoformat())
    return {"status": state.value, "findings": findings, "concentration": concentration,
            "explanations": _explain(findings, pack.evidence, pack.metadata), "receipt": receipt.to_dict(), "proof_graph": {
                "claim_nodes": [str(c.get("claim_id", "")) for c in pack.claims],
                "evidence_nodes": [e.evidence_id for e in pack.evidence],
                "edges": [{"from": e.evidence_id, "to": c.get("claim_id", "")}
                          for e in pack.evidence for c in pack.claims],
            }}


def verify_receipt(receipt: Dict[str, Any], pack: ContinuityPack, policy: Dict[str, Any]) -> Dict[str, Any]:
    required = {"receipt_version", "pack_id", "policy_digest", "pack_digest", "outcome", "created_at"}
    missing = required - set(receipt)
    reasons = []
    if missing:
        reasons.append("receipt missing: " + ", ".join(sorted(missing)))
    if receipt.get("receipt_version") != "0.2": reasons.append("unsupported receipt version")
    if receipt.get("pack_id") != pack.pack_id: reasons.append("pack id mismatch")
    if receipt.get("pack_digest") != digest(pack.to_dict()): reasons.append("pack digest mismatch")
    if receipt.get("policy_digest") != digest(policy): reasons.append("policy digest mismatch")
    return {"valid": not reasons, "reasons": reasons}


def plan_drill(pack: ContinuityPack, environment: str = "sandbox") -> Dict[str, Any]:
    """Return a non-executing drill plan; production is always refused."""
    if environment != "sandbox":
        raise ContinuityError("drills are planning-only and require environment=sandbox")
    return {"status": "NOT_RUN", "environment": "sandbox", "pack_id": pack.pack_id,
            "steps": ["validate exported pack", "exercise restore in isolated sandbox", "compare receipt digests"],
            "safety": ["no production credentials", "no network target", "no destructive action"]}
