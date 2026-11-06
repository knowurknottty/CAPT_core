#!/usr/bin/env python3
"""Compute the R0.4 Node service-identity enforcement status from test evidence.

The status is derived, never asserted: every declared effect maps to the real-user E2E
tests that exercise it, and an effect counts as enforced on a platform only when each of
those tests is present in that platform's JUnit evidence and passed. The overall status is
ENFORCED_FOR_DECLARED_EFFECT_SET only when every effect is enforced on every required
platform; otherwise PARTIAL (with what is missing) or NOT_ENFORCED (a mapped test failed).

  python scripts/r04_enforcement_report.py --junit linux=path.xml --junit macos=path.xml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MODULE = "test_node_service_identity_e2e"

# effect -> tests (function names in tests/capt_runtime/test_node_service_identity_e2e.py)
DECLARED_EFFECTS: dict[str, list[str]] = {
    "node_runs_as_dedicated_service_uid": ["test_node_runs_as_the_service_uid", "test_restart_keeps_identity_and_replays_not_redispatches"],
    "node_refuses_human_or_agent_uid": ["test_preflight_refuses_human_and_agent_uids"],
    "human_credential_unreadable_by_remote_exec": ["test_shell_exec_cannot_read_human_token_or_home", "test_symlinks_do_not_launder_reach"],
    "signing_keys_unreadable_by_remote_exec": ["test_shell_exec_cannot_read_human_token_or_home"],
    "trust_config_code_immutable_by_remote_exec": ["test_shell_exec_cannot_rewrite_trust_anchors_config_or_code"],
    "unsafe_deployment_refused_at_start": ["test_preflight_refuses_reachable_human_credential",
                                           "test_preflight_refuses_service_owned_trust_and_writable_code",
                                           "test_preflight_only_reports_without_serving"],
    "workspace_scope_enforced": ["test_scope_violations_fail_closed", "test_symlinks_do_not_launder_reach"],
    "capability_cannot_widen_deployed_roots": ["test_scope_violations_fail_closed"],
    "only_human_peer_reaches_node": ["test_only_the_human_peer_reaches_the_socket"],
    "node_spawned_process_cannot_drive_node": ["test_only_the_human_peer_reaches_the_socket"],
    "durable_receipts_and_denials": ["test_receipts_and_denials_are_durable_and_readable_by_the_human",
                                     "test_restart_keeps_identity_and_replays_not_redispatches"],
    "operation_id_dispatches_once": ["test_concurrent_reuse_of_one_operation_id_dispatches_once",
                                     "test_restart_keeps_identity_and_replays_not_redispatches"],
    "no_privilege_escalation_from_service": ["test_service_has_no_sudo"],
    "emergency_revocation_leaves_nothing": ["test_operation_close_is_not_revocation_but_service_revocation_is"],
    "permitted_work_still_works": ["test_permitted_work_executes_and_human_reads_result"],
}


def _results(path: Path) -> tuple[dict[str, str], str]:
    data = path.read_bytes()
    out: dict[str, str] = {}
    for case in ET.fromstring(data).iter("testcase"):
        if MODULE not in (case.get("classname") or "") + (case.get("file") or ""):
            continue
        name = case.get("name", "").split("[")[0]
        if case.find("failure") is not None or case.find("error") is not None:
            state = "failed"
        elif case.find("skipped") is not None:
            state = "skipped"
        else:
            state = "passed"
        if out.get(name) != "failed":  # a failure anywhere wins
            out[name] = state
    return out, "sha256:" + hashlib.sha256(data).hexdigest()


def compute(evidence: dict[str, Path], required: tuple[str, ...] = ("linux", "macos")) -> dict[str, object]:
    platforms = {}
    for label, path in evidence.items():
        results, digest = _results(path)
        platforms[label] = {"source": str(path), "sha256": digest, "results": results}
    effects = {}
    overall_failed = False
    overall_missing = False
    for effect, tests in DECLARED_EFFECTS.items():
        per = {}
        for label, info in platforms.items():
            states = {t: info["results"].get(t, "missing") for t in tests}
            if any(s == "failed" for s in states.values()):
                per[label] = "NOT_ENFORCED"
                overall_failed = True
            elif all(s == "passed" for s in states.values()):
                per[label] = "ENFORCED"
            else:
                per[label] = "UNPROVEN"
                overall_missing = True
            per[label + "_tests"] = states
        effects[effect] = per
    absent = sorted(set(required) - set(platforms))
    status = ("NOT_ENFORCED" if overall_failed else "PARTIAL" if overall_missing or absent or not platforms
              else "ENFORCED_FOR_DECLARED_EFFECT_SET")
    return {
        "schema": "capt.r04.enforcement-report.v1",
        "status": status,
        "requiredPlatforms": list(required),
        "missingPlatforms": absent,
        "declaredEffects": len(DECLARED_EFFECTS),
        "effects": effects,
        "evidence": {k: {"source": v["source"], "sha256": v["sha256"]} for k, v in platforms.items()},
        "scope": "CAPT Node service identity only; parallel uid-501 surfaces are out of this effect set",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", action="append", default=[], metavar="PLATFORM=PATH")
    parser.add_argument("--require", default="linux,macos", help="platforms that must all be evidenced")
    args = parser.parse_args()
    evidence = {}
    for item in args.junit:
        label, _, path = item.partition("=")
        if not label or not path:
            parser.error("--junit takes PLATFORM=PATH")
        evidence[label] = Path(path)
    report = compute(evidence, tuple(x for x in args.require.split(",") if x))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ENFORCED_FOR_DECLARED_EFFECT_SET" else 1


if __name__ == "__main__":
    sys.exit(main())
