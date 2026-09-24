#!/usr/bin/env python3
"""Human-facing launcher for the CAPT donor convergence council mission.

This script does not bypass RuntimeService. It creates exact approval requests,
prints/saves only non-secret receipt identities, and will run the council only
after the human explicitly invokes approve-and-run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from desktop.desktop_runtime_client import RuntimeClient

TARGET = Path("/Users/knowurknot/.capt/worktrees/openworker-convergence-r1")
STATE_ROOT = Path.home() / ".capt"
SOCKET = STATE_ROOT / "runtime.sock"
TOKEN = STATE_ROOT / "runtime.token"
MISSION_ID = "m-capt-donor-convergence-r1-20260924"
COUNCIL_ID = "council-capt-donor-convergence-r1-20260924"
MANIFEST = "docs/missions/CAPT_DONOR_CHERRYPICK_INTEGRATION_R1.json"
STATE_FILE = TARGET / ".capt-mission" / "donor-convergence-r1-r3.json"
EXPIRES_AT = "2026-09-25T06:00:00Z"
REQUESTED_CONTEXT_BUDGET = 128_000

COHORTS = (
    {
        "cohortId": "qwen38-flash",
        "provider": "openrouter",
        "model": "qwen/qwen3.8-flash",
        "taskId": "t-capt-donor-qwen38-r3",
        "driverRunId": "dr-capt-donor-qwen38-r3",
        "phase": (
            "You are sequential cohort 1/3. Establish the source/provenance matrix "
            "across the entire donor manifest, then perform the strongest justified "
            "first-pass integrations. Prioritize architecture, orchestration, memory, "
            "protocols, tools, search/research, security, media/image/voice plumbing, "
            "and developer/runtime mechanisms that fit CAPT. Do not merely recommend: "
            "implement justified changes and tests. Leave a precise handoff in the "
            "donor ledger/report for the next cohorts."
        ),
    },
    {
        "cohortId": "mimo26-flash",
        "provider": "openrouter",
        "model": "xiaomi/mimo-v2.6-flash",
        "taskId": "t-capt-donor-mimo26-r3",
        "driverRunId": "dr-capt-donor-mimo26-r3",
        "phase": (
            "You are sequential cohort 2/3. Treat the current worktree, including "
            "cohort 1 changes, as the working artifact. Independently challenge every "
            "donor disposition and implementation. Focus on missed high-value mechanisms, "
            "architectural mismatch, licensing/provenance, failure recovery, security "
            "boundaries, interoperability, and tests. Repair weak integrations and "
            "complete additional justified integrations without undoing valid work for style."
        ),
    },
    {
        "cohortId": "glm53-flash",
        "provider": "openrouter",
        "model": "z-ai/glm-5.3-flash",
        "taskId": "t-capt-donor-glm53-r3",
        "driverRunId": "dr-capt-donor-glm53-r3",
        "phase": (
            "You are sequential cohort 3/3 and final convergence gate. Treat prior "
            "cohort changes as inputs, not conclusions. Close every remaining donor row, "
            "implement any still-justified missing capability, deduplicate competing "
            "mechanisms, harden CAPT authority/provenance/security semantics, and run "
            "the required verification gates. If a real blocker prevents completion, "
            "preserve it exactly and mark it UNPROVEN rather than manufacturing success."
        ),
    },
)

SHARED_OBJECTIVE = f"""Execute the CAPT donor cherry-pick and integration mission defined in {MANIFEST}.
Read AGENTS.md, README.md, docs/OPENWORKER_CONVERGENCE.md, the current convergence workflow,
and the mission manifest before changing code. Work only in the assigned isolated worktree.
The mission manifest's complete donor list is mandatory: every donor must end with a frozen
upstream SHA/license and explicit disposition. Integrate or CAPT-native-reimplement only
capabilities that materially improve CAPT; preserve upstream provenance/license notices for
copied code. RuntimeService/EventStore remains authoritative; imported runtimes/providers/
agents may not become a second control plane, self-grant authority, self-verify evidence,
or bypass ToolBroker/approval/provenance/verification boundaries. Preserve existing valid
work. No push, merge, release, force operations, destructive cleanup, credential exposure,
or unrelated repository mutation. Add discriminating tests for consequential behavior.
Maintain docs/convergence/DONOR_LEDGER_OPENWORKER_OPENJIUWEN_R1.md and
docs/convergence/DONOR_INTEGRATION_REPORT_R1.md. Completion requires every donor accounted
for, accepted integrations actually implemented, contract drift checked, relevant targeted
tests plus the full CAPT suite run, git diff checks clean, and remaining blockers explicitly
UNPROVEN rather than hand-waved."""

AUTHORITY_PROFILE = {
    "filesystemScope": "project",
    "filesystemRoot": str(TARGET),
    "fileMutationAllowed": True,
    "shellAccessAllowed": True,
    "providerNetworkPolicy": "remote_allowed",
}

COHORT_SPEC_BASE = {
    "vesselsPerCohort": 11,
    "configurationId": "donor-convergence-r1",
    "vesselCharterPolicy": {"schemaVersion": "2.0.0"},
}


def _client() -> RuntimeClient:
    c = RuntimeClient(
        str(SOCKET), str(TOKEN), connect_timeout=2.0, command_timeout=None
    )
    c.connect()
    return c


def _require_capability(client: RuntimeClient) -> None:
    caps = client.capabilities()
    ops = set(caps.get("commandOperations") or [])
    required = {
        "request_model_prompt_approval",
        "submit_approval_decision",
        "run_approved_council_inspection",
    }
    missing = sorted(required - ops)
    if missing:
        raise RuntimeError("scheduler_surface_unavailable:" + ",".join(missing))


def _request_payload(cohort: dict[str, Any]) -> dict[str, Any]:
    spec = dict(COHORT_SPEC_BASE)
    spec["cohortId"] = cohort["cohortId"]
    return {
        "objective": SHARED_OBJECTIVE + "\n\n" + cohort["phase"],
        "targetRoot": str(TARGET),
        "provider": cohort["provider"],
        "model": cohort["model"],
        "missionId": MISSION_ID,
        "taskId": cohort["taskId"],
        "driverRunId": cohort["driverRunId"],
        "requestedContextBudget": REQUESTED_CONTEXT_BUDGET,
        "humanVerificationRequired": True,
        "responseMode": "SPOCK",
        "promptEnhancement": "OFF",
        "cohortSpec": spec,
        "authorityProfile": dict(AUTHORITY_PROFILE),
        "expiresAt": EXPIRES_AT,
    }


def _safe_request_record(cohort: dict[str, Any], planned: dict[str, Any]) -> dict[str, Any]:
    return {
        "cohortId": cohort["cohortId"],
        "provider": cohort["provider"],
        "model": cohort["model"],
        "requestId": planned["requestId"],
        "missionId": planned["missionId"],
        "taskId": planned["taskId"],
        "driverRunId": planned["driverRunId"],
        "promptAssemblyDigest": planned["promptAssemblyDigest"],
        "dispatchPromptDigest": planned["dispatchPromptDigest"],
        "expiresAt": planned["expiresAt"],
        "cohortSpec": planned["cohortSpec"],
        "authorityProfile": planned["authorityProfile"],
    }


def request() -> dict[str, Any]:
    client = _client()
    records = []
    run_items = []
    try:
        _require_capability(client)
        for index, cohort in enumerate(COHORTS, 1):
            payload = _request_payload(cohort)
            receipt = client.command(
                "request_model_prompt_approval",
                payload,
                f"idem-capt-donor-r1-r3-approval-{index}-20260924",
            )
            if receipt.get("status") not in {"accepted", "idempotent"}:
                raise RuntimeError("approval request failed: " + json.dumps(receipt))
            planned = receipt["result"]
            records.append(_safe_request_record(cohort, planned))
            run_items.append({
                **payload,
                "approvalRequestId": planned["requestId"],
                "missionId": planned["missionId"],
                "taskId": planned["taskId"],
                "driverRunId": planned["driverRunId"],
            })
    finally:
        client.disconnect()

    state = {
        "schemaVersion": "1.0.0",
        "missionId": MISSION_ID,
        "councilId": COUNCIL_ID,
        "maxConcurrentCohorts": 1,
        "providerCallInvariant": "one_call_per_cohort",
        "requests": records,
        "executions": run_items,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return state


def status() -> dict[str, Any]:
    if not STATE_FILE.exists():
        raise RuntimeError("mission state absent; run request first")
    state = json.loads(STATE_FILE.read_text())
    client = _client()
    rows = []
    try:
        _require_capability(client)
        for item in state["requests"]:
            authoritative = client.get_state("human_approval-" + item["requestId"])
            rows.append({
                "cohortId": item["cohortId"],
                "model": item["model"],
                "requestId": item["requestId"],
                "state": authoritative.get("state"),
                "remainingUses": authoritative.get("remainingUses"),
                "expiresAt": authoritative.get("expiresAt"),
                "promptAssemblyDigest": authoritative.get("promptAssemblyDigest"),
            })
    finally:
        client.disconnect()
    return {"missionId": MISSION_ID, "councilId": COUNCIL_ID, "approvals": rows}


def approve_and_run() -> dict[str, Any]:
    if not STATE_FILE.exists():
        raise RuntimeError("mission state absent; run request first")
    state = json.loads(STATE_FILE.read_text())
    client = _client()
    try:
        _require_capability(client)
        rows = []
        for item in state["requests"]:
            authoritative = client.get_state("human_approval-" + item["requestId"])
            rows.append({
                "cohortId": item["cohortId"],
                "model": item["model"],
                "requestId": item["requestId"],
                "state": authoritative.get("state"),
                "remainingUses": authoritative.get("remainingUses"),
                "expiresAt": authoritative.get("expiresAt"),
            })
        bad = [row for row in rows if row["state"] not in {"requested", "approved"}]
        if bad:
            raise RuntimeError("approval_not_actionable:" + json.dumps(bad))
        for index, row in enumerate(rows, 1):
            if row["state"] == "requested":
                decision = client.command(
                    "submit_approval_decision",
                    {"requestId": row["requestId"], "decision": "approve",
                     "note": "Explicit human approval for CAPT donor convergence council."},
                    f"idem-capt-donor-r1-r3-decision-{index}-20260924",
                )
                if decision.get("status") not in {"accepted", "idempotent"}:
                    raise RuntimeError("approval decision failed: " + json.dumps(decision))
        return client.command(
            "run_approved_council_inspection",
            {
                "councilId": COUNCIL_ID,
                "maxConcurrentCohorts": 1,
                "executions": state["executions"],
            },
            "idem-capt-donor-r1-r3-council-run-20260924",
        )
    finally:
        client.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("request", "status", "approve-and-run"))
    args = parser.parse_args()
    if args.action == "request":
        result = request()
    elif args.action == "status":
        result = status()
    else:
        result = approve_and_run()
    safe = dict(result)
    if args.action == "request":
        safe.pop("executions", None)
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
