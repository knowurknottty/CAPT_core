"""CAPT Discovery Governor + Bounded SEAL Scanner (v0.7).

A governed, evidence-producing discovery capability. See README in
``capt_runtime/discovery/docs`` and V07 archaeology for design intent.

Architecture
    mission/task
      -> DiscoveryGovernor      (strategy state machine)
      -> bounded strategy
      -> BoundedLocalScanner    (SEAL: read-only, allow-listed, symlink-safe)
      -> candidate observations + provenance + rejection ledger
      -> EvidenceRecord / verification boundary

Authority invariant: discovery observations can NEVER create, enlarge, or
mutate a capability lease. The scanner's API is read-only by construction; the
governor only recommends the next strategy. Any follow-on authority stays at
RuntimeService / the capability-lease boundary.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .governor import DiscoveryGovernor
from .models import (
    AMBIGUOUS,
    COMPILED_ARTIFACT_ONLY,
    EXHAUSTED,
    NOT_APPLICABLE,
    NOT_FOUND,
    PERMISSION_DENIED,
    POSSIBLE_REPOSITORY,
    REJECTED,
    SOURCE_NOT_PROVEN,
    SOURCE_PRESENT,
    UNAVAILABLE,
    UNKNOWN,
    Candidate,
    DiscoveryResult,
    GovernorDecision,
    RejectionRecord,
    ScanLimits,
)
from .policy import (
    ESCALATION_LADDER,
    BOUNDED_RESULT_VOCAB,
    ClassificationPolicy,
    DEFAULT_POLICY,
)
from .provenance import (
    build_run_provenance,
    new_run_id,
    observation_provenance,
)
from .redaction import (
    normalize_path,
    redact_json,
    redact_jsonl,
    redact_text,
)
from .scanner import BoundedLocalScanner, PathSafetyError

__all__ = [
    "BoundedLocalScanner", "DiscoveryGovernor", "PathSafetyError",
    "Candidate", "ClassificationPolicy", "DEFAULT_POLICY", "DiscoveryResult",
    "GovernorDecision", "RejectionRecord", "ScanLimits",
    "ESCALATION_LADDER", "BOUNDED_RESULT_VOCAB",
    "build_run_provenance", "new_run_id", "observation_provenance",
    "normalize_path", "redact_json", "redact_jsonl", "redact_text",
    "run_discovery", "to_evidence",
]


def run_discovery(
    *,
    targets: Sequence[str],
    allowed_roots: Optional[Sequence[str]] = None,
    enumeration_root: Optional[str] = None,
    limits: Optional[ScanLimits] = None,
    guess_budget: int = 3,
    requester: str = "operator",
    request_id: str = "",
    expected_markers: Optional[Sequence[str]] = None,
) -> DiscoveryResult:
    """Governed discovery over an ordered set of direct path hypotheses.

    Read-only. Records candidates/rejections/negative evidence and an explicit
    termination. Stops (never infinite-retries). Returns a DiscoveryResult.

    ``expected_markers`` (optional) is the target-criteria gate: when set, a
    scan is only a terminal SOURCE_PRESENT if at least one marker is present;
    a repo-like dir lacking them is classified possible_repository (Case D).

    The escalation ladder is simulated for unsupported remote strategies (they
    yield an explicit bounded result) so discovery always terminates.
    """
    if not request_id:
        request_id = new_run_id()
    req_id = request_id
    governor = DiscoveryGovernor(guess_budget=guess_budget)
    scanner = BoundedLocalScanner(limits=limits,
                                  allowed_roots=allowed_roots or None,
                                  expected_markers=expected_markers)
    result = DiscoveryResult(request_id=req_id)
    result.provenance = build_run_provenance(
        requester=requester, request_id=req_id,
        allowed_roots=list(allowed_roots or []) or [str(t) for t in targets],
        limits=_limits_dict(limits), policy_name="capt_runtime.discovery.policy")

    strategy = governor.current_strategy()  # KNOWN_PATH
    run_id = result.provenance.get("run_id", "")

    # (A) Direct-guess phase over the provided targets (KNOWN_PATH).
    for tgt in targets:
        scan = scanner.scan(str(tgt), strategy=strategy,
                            run_id=run_id, request_id=req_id)
        classification = scan.get("classification", UNKNOWN)
        redactions = []
        for c in scan.get("candidates", []):
            result.candidates.append(dict(c))
        for (p, reason) in scan.get("rejections", []):
            result.rejections.append(
                RejectionRecord(path=p, reason=reason, strategy=strategy).to_dict())
        if scan.get("termination") in (NOT_FOUND, PERMISSION_DENIED, REJECTED):
            result.negative_evidence.append(_neg(str(tgt), classification))
        result.strategy_trace.append({
            "strategy": strategy, "target": normalize_path(str(tgt)),
            "classification": classification,
            "confidence": scan.get("confidence"),
            "termination": scan.get("termination"),
        })
        if classification == SOURCE_PRESENT:
            return _finish(result, termination=SOURCE_PRESENT,
                           stop_reason="source located",
                           recommended_next="proceed",
                           confidence=scan.get("confidence", "high"))
        # Feed the governor; enforce the three-guess rule.
        decision = governor.observe(strategy=strategy,
                                    classification=classification)
        result.strategy_trace.append({"decision": decision.to_dict()})
        if decision.action == "FILESYSTEM_ENUMERATION" or not decision.ok:
            break
        strategy = decision.action  # advance ladder

    # (B) FILESYSTEM_ENUMERATION over an EXPLICIT enumeration root only.
    #     Missing targets never auto-sweep an unrelated parent tree, so
    #     enum_root is honored only when explicitly provided.
    if enumeration_root:
        es = scanner.with_roots(allowed_roots or [enumeration_root])
        scan = es.scan(enumeration_root, strategy="FILESYSTEM_ENUMERATION",
                       run_id=run_id, request_id=req_id)
        result.strategy_trace.append({
            "strategy": "FILESYSTEM_ENUMERATION",
            "target": normalize_path(enumeration_root),
            "classification": scan.get("classification"),
            "termination": scan.get("termination"),
        })
        for c in scan.get("candidates", []):
            result.candidates.append(dict(c))
        for (p, reason) in scan.get("rejections", []):
            result.rejections.append(
                RejectionRecord(path=p, reason=reason,
                                strategy="FILESYSTEM_ENUMERATION").to_dict())
        if scan.get("classification") == SOURCE_PRESENT:
            return _finish(result, termination=SOURCE_PRESENT,
                           stop_reason="source located via enumeration",
                           recommended_next="proceed",
                           confidence=scan.get("confidence", "high"))

    # (C) Unsupported remote strategies produce an explicit bounded result.
    result.strategy_trace.append({
        "strategy": "CONTAINER_METADATA",
        "classification": UNAVAILABLE,
        "termination": UNAVAILABLE,
    })
    result.negative_evidence.append(_neg("(container metadata)", UNAVAILABLE))

    return _finish(result,
                   termination=EXHAUSTED if result.candidates
                   else NOT_FOUND,
                   stop_reason="bounded discovery exhausted strategies; "
                               "no unproven source located",
                   recommended_next="owner_clarification",
                   confidence="low" if not result.candidates else "medium")


def to_evidence(result: DiscoveryResult, *, mission_id: str,
                collected_by: Dict[str, Any], evidence_id: Optional[str] = None
                ) -> Dict[str, Any]:
    """Map a DiscoveryResult onto CAPT's canonical EvidenceRecord shape.

    This is a pure mapper: it produces a dict conforming to the generated
    ``EvidenceRecord`` contract (see contracts/generated/.../types.py). The
    runtime's ``record_evidence`` performs authoritative validation; this mapper
    does NOT itself record or grant. ``sourceObservationId`` is set so a driver-
    like observation never transfers authority.
    """
    if evidence_id is None:
        evidence_id = "ev-" + new_run_id()
    digest = hashlib.sha256(
        _canonical_payload(result).encode("utf-8")).hexdigest()
    evidence = {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "evidenceId": evidence_id,
        "collectedAt": _rfc3339(),
        "collectedBy": collected_by,
        "trust": "capt_authoritative",
        "sourceObservationId": result.request_id,
        "evidence": {
            "kind": "artifact_hash",
            "artifactPath": "discovery/" + result.request_id,
            "artifactDigest": "sha256:" + digest,
        },
    }
    return evidence


def _canonical_payload(result: DiscoveryResult) -> str:
    """Deterministic canonical serialization for evidence hashing.

    Hashes OBSERVATION CONTENT only (reproducible): redacted normalized paths,
    classification, confidence, strategy, evidence, accepted/rejection state,
    plus a stable policy fingerprint. It deliberately EXCLUDES volatile
    execution metadata (request_id, run_id, candidate_id, timestamps,
    collectedBy) so identical observation content hashes identically across
    runs (SP3 DecisionRecord D-003).
    """
    import json as _json

    def _candidate_content(c: dict) -> dict:
        # provenance (run linkage) is metadata, not observation content
        return {
            "path": c.get("path"),
            "classification": c.get("classification"),
            "confidence": c.get("confidence"),
            "strategy": c.get("strategy"),
            "kind": c.get("kind"),
            "evidence": sorted(c.get("evidence", [])),
            "accepted": c.get("accepted"),
        }

    class_terms = {t.get("classification") for t in result.strategy_trace}
    return _json.dumps({
        "termination": result.termination,
        "stop_reason": result.stop_reason,
        "recommended_next": result.recommended_next,
        "source_location_confidence": result.source_location_confidence,
        "candidates": sorted(
            (_candidate_content(c) for c in result.candidates),
            key=lambda c: str(c.get("path"))),
        "rejections": sorted(
            (r.get("path"), r.get("reason"), r.get("strategy"))
            for r in result.rejections if isinstance(r, dict)),
        "negative_evidence": sorted(
            (n.get("target"), n.get("classification"))
            for n in result.negative_evidence if isinstance(n, dict)),
        "strategy_classes": sorted(cls for cls in class_terms if cls),
        "policy_fingerprint": _policy_fingerprint(result),
    }, sort_keys=True, default=str)


def _policy_fingerprint(result: DiscoveryResult) -> str:
    """Stable fingerprint of the discovery run's configured policy/limits.

    Included so a policy or bounds change invalidates prior evidence rather than
    being silently treated as identical content.
    """
    import json as _json
    p = result.provenance or {}
    allowed_roots = sorted(str(r) for r in p.get("allowed_roots", []))
    limits = {k: v for k, v in (p.get("limits") or {}).items()}
    return _json.dumps({
        "policy": p.get("policy"),
        "allowed_roots": allowed_roots,
        "limits": {k: limits[k] for k in sorted(limits)},
        "three_guess_rule": p.get("three_guess_rule"),
    }, sort_keys=True, default=str)


def _neg(target: str, classification: str) -> Dict[str, Any]:
    return {"target": target, "classification": classification,
            "accepted": False}


def _finish(result, *, termination, stop_reason, recommended_next, confidence):
    result.termination = termination
    result.stop_reason = stop_reason
    result.recommended_next = recommended_next
    result.source_location_confidence = confidence
    return result


def _limits_dict(limits):
    return {k: getattr(limits, k) for k in
            ("max_depth", "max_files", "max_directories", "max_bytes_per_file",
             "max_total_bytes", "max_candidates", "timeout_seconds")
            } if limits else {}


def _rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
