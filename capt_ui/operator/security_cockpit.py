"""Truthful security-gate cockpit projection (CAPT-UPG-019).

This module shapes SecurityGateResult data for operator surfaces. It does not
run security controls, authorize release, or turn a gate result into a global
claim that CAPT is secure.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping


def project_security_cockpit(result: Mapping[str, Any]) -> Dict[str, Any]:
    source_sha = str(result.get("sourceSha") or "")
    rows: List[Dict[str, Any]] = []
    computed_counts = {
        "pass": 0,
        "fail": 0,
        "not_verified": 0,
        "not_applicable": 0,
    }
    blocking = set(str(x) for x in (result.get("blockingControls") or []))

    for raw in result.get("results", []) or []:
        status = str(raw.get("status") or "not_verified")
        if status not in computed_counts:
            status = "not_verified"
        reason = str(raw.get("reason") or "")
        control_id = str(raw.get("control_id") or raw.get("controlId") or "")
        refs = raw.get("evidence_refs")
        if refs is None:
            refs = raw.get("evidenceRefs") or []
        refs = list(refs or [])
        # A PASS without an exact source identity or evidence reference cannot
        # be represented as verified by the Cockpit, even if a malformed or
        # hand-crafted upstream object says PASS. Fail closed in projection.
        if status == "pass" and not source_sha:
            status = "not_verified"
            reason = "PASS result is missing exact source SHA binding"
        elif status == "pass" and not refs:
            status = "not_verified"
            reason = "PASS result is missing verification evidence reference"
        computed_counts[status] += 1
        stale = status == "not_verified" and "stale:" in reason.lower()
        missing = status == "not_verified" and not stale
        rows.append(
            {
                "controlId": control_id,
                "title": raw.get("title"),
                "status": status,
                "severity": raw.get("severity"),
                "releaseBlocking": bool(raw.get("release_blocking", raw.get("releaseBlocking", True))),
                "blocksCurrentGate": control_id in blocking,
                "reason": reason,
                "evidenceRefs": refs,
                "sourceSha": source_sha,
                "evidenceStale": stale,
                "evidenceMissing": missing,
                "isPass": status == "pass",
                "isNotApplicable": status == "not_applicable",
            }
        )

    # Preserve the gate's own decision but label it narrowly. It is a gate
    # decision over this profile/source SHA, not a universal security verdict.
    projected_blockers = sorted(
        row["controlId"] for row in rows
        if row["releaseBlocking"] and row["status"] in ("fail", "not_verified")
    )
    blocking.update(projected_blockers)
    decision = str(result.get("decision") or "BLOCKED")
    if blocking and decision == "PASS":
        decision = "BLOCKED"

    return {
        "schemaVersion": "1.0.0",
        "kind": "SecurityClosureCockpit",
        "profile": result.get("profile"),
        "sourceSha": source_sha,
        "gateDecision": decision,
        "counts": computed_counts,
        "blockingControls": sorted(blocking),
        "controls": rows,
        "authority": "projection_only",
        "releaseAuthorized": False,
        "globalSecurityVerdict": None,
        "semantics": {
            "passMeans": "control verified for the supplied exact source SHA/evidence scope",
            "notApplicableIsPass": False,
            "notVerifiedIsPass": False,
            "gatePassIsUniversalSecurityClaim": False,
        },
    }


def render_security_summary(cockpit: Mapping[str, Any], max_blockers: int = 12) -> str:
    counts = cockpit.get("counts") or {}
    lines = [
        "CAPT Security Closure Cockpit — projection only",
        "profile=%s source=%s gate=%s" % (
            cockpit.get("profile") or "unknown",
            cockpit.get("sourceSha") or "unknown",
            cockpit.get("gateDecision") or "unknown",
        ),
        "PASS=%d FAIL=%d NOT_VERIFIED=%d N/A=%d" % (
            int(counts.get("pass", 0)),
            int(counts.get("fail", 0)),
            int(counts.get("not_verified", 0)),
            int(counts.get("not_applicable", 0)),
        ),
        "No universal 'CAPT is secure' verdict is emitted by this view.",
    ]
    blockers = list(cockpit.get("blockingControls") or [])
    if blockers:
        lines.append("Blocking controls: %s" % ", ".join(blockers[:max_blockers]))
        if len(blockers) > max_blockers:
            lines.append("... %d more blocker(s)" % (len(blockers) - max_blockers))
    return "\n".join(lines)
