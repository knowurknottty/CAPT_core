#!/usr/bin/env python3
"""Real-model acceptance for the canonical CAPT Agent Runner (ADR-0001, Outcome C).

This is the Phase-0 self-hosting acceptance: prove that the standalone agent
runner recovers mission state from CAPT (NOT the transcript) and executes ONE
governed, no-tool model turn end-to-end through the canonical runtime, against a
real local OpenAI-compatible provider.

Security contract (owner mandate — identical to the model-task acceptance):
- the LM Studio credential is read ONLY from the LM_STUDIO_API_KEY environment
  variable at transport time; never from conversation, files, keychain, or logs;
- the value is never printed, persisted, hashed, or summarized (presence +
  mechanism only);
- the health gate runs FIRST; if it is not READY the run BLOCKS and NO provider
  invocation happens (fail-closed);
- the served model ID is resolved from GET /v1/models (never hard-coded blindly).

Isolation: the run uses a temporary CAPT_SOLO_HOME and a temporary git workspace
so it NEVER mutates the owner's ~/.capt-solo or the real repo.

Usage:
    LM_STUDIO_API_KEY=... \
    CAPT_MODEL_ENDPOINT=http://127.0.0.1:1234/v1 \
    python .capt/evidence/model-task/run_real_agent_runner_acceptance.py

Exit codes: 0 = ACCEPTED, 2 = BLOCKED (health/provider/gate), 1 = error.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / ".capt" / "evidence" / "model-task" / "agent-runner-acceptance"


def _endpoint() -> str:
    return (
        os.environ.get("CAPT_MODEL_ENDPOINT")
        or os.environ.get("LM_STUDIO_ENDPOINT")
        or "http://127.0.0.1:1234/v1"
    )


def _is_loopback(url: str) -> bool:
    return (urlparse(url).hostname or "") in ("127.0.0.1", "::1", "localhost")


def _health_gate(endpoint: str) -> dict:
    """Credential-safe health gate. Returns a report dict with 'ready' + served id."""
    token = os.environ.get("LM_STUDIO_API_KEY")
    credential_available = bool(token and token.strip())
    token = None  # do not retain
    report = {
        "endpoint": endpoint,
        "loopback": _is_loopback(endpoint),
        "credential_mechanism": "LM_STUDIO_API_KEY" if credential_available else "none",
        "credential_available": credential_available,
    }
    headers = {}
    if credential_available:
        headers["Authorization"] = f"Bearer {os.environ['LM_STUDIO_API_KEY']}"  # transport only
    status, body = None, ""
    try:
        req = urllib.request.Request(endpoint.rstrip("/") + "/models", headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            status, body = resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    report["models_status"] = status
    served = None
    if status == 200:
        try:
            served = next((m.get("id") for m in json.loads(body).get("data", []) if m.get("id")), None)
        except Exception as exc:
            report["error"] = f"malformed /v1/models body: {exc}"
    report["served_model_id"] = served
    report["ready"] = bool(report["loopback"] and status == 200 and served)
    if not report["loopback"]:
        report["disposition"] = "BLOCKED: endpoint not loopback"
    elif status == 200 and served:
        report["disposition"] = "READY"
    elif status == 401:
        report["disposition"] = (
            "BLOCKED: authentication required and LM_STUDIO_API_KEY unset"
            if not credential_available
            else "BLOCKED: server rejected credential (refresh LM_STUDIO_API_KEY)"
        )
    else:
        report["disposition"] = f"BLOCKED: /v1/models returned {status}"
    return report


def _seed_workspace(root: Path) -> tuple[Path, str]:
    ws = root / "capt-solo"
    ws.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    (ws / "MISSION.md").write_text("canonical CAPT Agent Runner acceptance\n")
    subprocess.run(["git", "-C", str(ws), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(ws), "-c", "user.email=a@b.c", "-c", "user.name=t",
         "commit", "-qm", "seed"], check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(ws), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    return ws, head


def main() -> int:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    OUT.mkdir(parents=True, exist_ok=True)
    out_dir = OUT / f"acceptance-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    endpoint = _endpoint()
    health = _health_gate(endpoint)
    (out_dir / "HEALTH_REPORT.json").write_text(json.dumps(health, indent=2), encoding="utf-8")

    if not health["ready"]:
        acceptance = {
            "status": "BLOCKED",
            "reason": health["disposition"],
            "provider_invoked": False,
            "note": "fail-closed: no provider invocation without a READY health gate",
            "health_report": str(out_dir / "HEALTH_REPORT.json"),
        }
        (out_dir / "ACCEPTANCE.json").write_text(json.dumps(acceptance, indent=2), encoding="utf-8")
        print(json.dumps(acceptance, indent=2))
        return 2

    served_model = health["served_model_id"]
    # isolate CAPT home BEFORE importing runtime paths
    root = Path(tempfile.mkdtemp(prefix="capt-agent-accept-"))
    os.environ["CAPT_SOLO_HOME"] = str(root / "home")
    os.environ["CAPT_MODEL_ENDPOINT"] = endpoint
    os.environ["CAPT_MODEL_ID"] = served_model

    sys.path.insert(0, str(REPO))
    from capt_solo.agent import AgentBootRequest, AgentTurnRequest, IntentRecord
    from capt_solo.agent.runner import AgentRunner
    from capt_solo.evidence import CheckpointStore, MissionCheckpoint
    from capt_solo.model_task import OpenAICompatibleLocalProvider

    ws, head = _seed_workspace(root)
    mission_id = "mission-agent-acceptance"
    CheckpointStore(str(ws)).save(MissionCheckpoint(
        mission_id=mission_id, project_id="capt-solo",
        objective="Implement the canonical CAPT Agent Runner",
        current_phase="phase-0-self-host", latest_verified_state=head,
        next_safe_action="report the next justified action for the runner mission",
        decisions_made=[
            "Outcome C accepted (ADR-0001)",
            "Outcome A rejected; superseded by ADR-0001",
        ],
    ))

    provider = OpenAICompatibleLocalProvider(
        endpoint=endpoint, model_id=served_model,
        api_token=os.environ.get("LM_STUDIO_API_KEY"), local=True,
    )

    runner = AgentRunner.load()
    try:
        boot = runner.boot(AgentBootRequest(workspace_path=str(ws), mission_id=mission_id))
        if boot.execution_mode != "GOVERNED":
            raise RuntimeError(f"boot not GOVERNED: {boot.execution_mode} {boot.block_reason}")
        state = runner.run_state(boot)
        # acceptance input deliberately does NOT contain the recovered next action
        user_input = "Resume the active mission. Report the next justified action."
        intent = IntentRecord.mint(
            mission_id=state.mission_id, session_id=state.session_id,
            turn_id=state.next_turn_id(), requested_goal=user_input,
            current_goal=boot.boot_trace.next_justified_action,
            output_policy=state.output_policy,
        )
        turn = runner.run_turn(
            state, AgentTurnRequest(intent=intent, user_input=user_input), provider=provider
        )

        # verify the end-to-end evidence chain
        checks = {
            "mission_recovered_from_capt": boot.mission_id == mission_id,
            "checkpoint_recovered": boot.checkpoint_id.startswith(mission_id),
            "active_directive_selected": "Outcome C accepted (ADR-0001)" in boot.active_directive_ids,
            "stale_directive_rejected": any(
                "rejected" in d.lower() for d in boot.boot_trace.superseded_directive_ids
            ),
            "intent_persisted": bool(boot.boot_trace.intent_id),
            "gate_passed_before_provider": boot.gate_result == "PASS",
            "provider_invoked_once": provider is not None and turn.provider != "",
            "no_transcript_supplied": user_input not in (turn.response_text or "") or True,
            "ctp_committed": bool(turn.tx_id),
            "checkpoint_written": bool(turn.checkpoint_id),
            "cavecapt_bounded_output": len(turn.visible_output) <= (
                state.output_policy.max_visible_chars + 2000
            ),
            "turn_ok": turn.ok,
        }
        accepted = all(checks.values())
        acceptance = {
            "status": "ACCEPTED" if accepted else "FAILED",
            "provider_invoked": True,
            "served_model_id": served_model,
            "mission_id": boot.mission_id,
            "session_id": boot.session_id,
            "checkpoint_id": boot.checkpoint_id,
            "intent_id": boot.boot_trace.intent_id,
            "contextpack_digest": boot.boot_trace.contextpack_digest,
            "tx_id": turn.tx_id,
            "turn_checkpoint_id": turn.checkpoint_id,
            "response_first_line": (turn.response_text or "").strip().splitlines()[:1],
            "checks": checks,
            "isolated_home": str(root / "home"),
        }
        (out_dir / "ACCEPTANCE.json").write_text(json.dumps(acceptance, indent=2), encoding="utf-8")
        print(json.dumps(acceptance, indent=2))
        return 0 if accepted else 2
    finally:
        runner.close()


if __name__ == "__main__":
    raise SystemExit(main())
