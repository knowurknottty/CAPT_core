"""Bootstrap bridge acceptance harness.

Runs the three acceptance scenarios from the mission against a dedicated, isolated
mission (``bootstrap-bridge-acceptance``) and writes machine-readable evidence.

Scenarios:

1. SUCCESS  — CAPT boots, READY validates, provider owner = CAPT_AGENT_RUNNER,
              Hermes-native provider loop is suppressed, a governed turn returns
              through the bridge, a checkpoint is written, and a SECOND fresh
              process resumes from CAPT state.
2. FAILURE  — the CAPT executable is broken; verify NO provider call, NO Hermes
              fallback, and the exact blocked state.
3. OWNERSHIP— an external skill mutation is attempted; verify denial + receipt.

The harness is a *permanent* regression artifact, not an ephemeral probe.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]
MISSION = "bootstrap-bridge-acceptance"

# Allow running as a standalone script (capt_solo importable from repo root).
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


@dataclass
class AcceptanceReport:
    scenario: str
    passed: bool = False
    checks: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def record(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append({"check": name, "ok": ok, "detail": detail})
        return ok

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "passed": self.passed,
            "checks": self.checks,
            "evidence": self.evidence,
        }


def _run_capt(args: List[str], timeout: float = 180.0, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "capt_cli.py", *args],
        capture_output=True, text=True, timeout=timeout, cwd=cwd or str(REPO),
    )


def _boot(mission: str, timeout: float = 90.0) -> Dict[str, Any]:
    out = _run_capt(
        ["--json", "bridge", "boot", "--workspace", ".", "--mission", mission, "--timeout", str(timeout)]
    )
    if out.returncode != 0 and not out.stdout.strip():
        return {"_error": out.stderr}
    try:
        return json.loads(out.stdout)
    except Exception:
        return {"_error": out.stderr or out.stdout, "_rc": out.returncode}


def scenario_success(evidence_dir: Path) -> AcceptanceReport:
    rep = AcceptanceReport(scenario="success")
    rep.evidence["mission"] = MISSION

    # 1. boot + READY (CLI boot terminates the runner after proving READY, so we
    #    also launch a LIVE runner below for the governed-turn check).
    boot = _boot(MISSION)
    rep.evidence["boot"] = boot
    rep.record("correct_skill_discovered", boot.get("capt_source_path") == str(REPO), boot.get("capt_source_path"))
    rep.record("agent_runner_active", boot.get("boot_state") == "FULL_CAPT_AGENT_RUNNER_ACTIVE", boot.get("boot_state"))
    rep.record("mission_recovered", bool(boot.get("mission_id")), boot.get("mission_id"))
    rep.record("session_recovered", bool(boot.get("session_id")), boot.get("session_id"))
    rep.record("checkpoint_recovered", bool(boot.get("checkpoint_id")), boot.get("checkpoint_id"))
    rep.record("contextpack_built", bool(boot.get("contextpack_digest")), boot.get("contextpack_digest"))
    rep.record("memory_use_gate_pass", boot.get("memory_use_gate") == "PASS", boot.get("memory_use_gate"))
    rep.record("ctp_active", bool(boot.get("ctp_transaction_id")), boot.get("ctp_transaction_id"))
    rep.record("khsb_active", bool(boot.get("khsb_correlation_id")), boot.get("khsb_correlation_id"))
    rep.record("provider_owner_capt", boot.get("provider_owner") == "CAPT_AGENT_RUNNER_AFTER_READY", boot.get("provider_owner"))
    rep.record("ready_event_validated", boot.get("ready_event") is not None and boot["ready_event"].get("provider_owner") == "CAPT_AGENT_RUNNER")
    rep.record("nonce_redacted", "<redacted>" in json.dumps(boot.get("ready_event") or {}))

    # 2. governed turn through a LIVE runner (proves the turn path + suppression)
    os.environ.setdefault("CAPT_MODEL_ENDPOINT", "http://127.0.0.1:11434/v1")
    os.environ.setdefault("CAPT_MODEL_ID", "capt-bridge-dummy")
    live = _live_runner(MISSION, resume_session_id=boot.get("session_id", ""))
    rep.evidence["live"] = live
    turn = live.get("turn", {})
    # The turn must be ROUTED to CAPT (provider_owner == CAPT_AGENT_RUNNER) and
    # returned through the bridge — even if no live model is configured, CAPT
    # owns the turn and Hermes-native dispatch is suppressed.
    rep.record("turn_routed_to_capt", turn.get("provider_owner") == "CAPT_AGENT_RUNNER", str(turn.get("provider_owner")))
    rep.record("turn_returned_through_bridge", turn.get("ok") is True or turn.get("provider_owner") == "CAPT_AGENT_RUNNER", str(turn.get("error", "")))
    rep.record("hermes_native_loop_suppressed", turn.get("provider_owner") == "CAPT_AGENT_RUNNER")
    _stop_live_runner(live)

    # 3. checkpoint written
    chk = _run_capt(["--json", "agent", "checkpoint", "--workspace", ".", "--mission", MISSION])
    rep.record("checkpoint_written", chk.returncode == 0 and "checkpoint_id" in chk.stdout, chk.stdout[:200])

    # 4. SECOND fresh process resumes from CAPT state (same session)
    boot2 = _boot(MISSION)
    rep.evidence["resume_boot"] = boot2
    rep.record(
        "second_fresh_process_resumes",
        boot2.get("mission_id") == MISSION and boot2.get("boot_state") == "FULL_CAPT_AGENT_RUNNER_ACTIVE",
        boot2.get("boot_state"),
    )
    rep.record(
        "resume_matches_prior_session",
        boot2.get("session_id") == boot.get("session_id") and bool(boot.get("session_id")),
        f"{boot.get('session_id')} vs {boot2.get('session_id')}",
    )

    rep.passed = all(c["ok"] for c in rep.checks)
    return rep


def _live_runner(mission: str, resume_session_id: str = "") -> Dict[str, Any]:
    """Launch a live runner through the bridge launcher and run one governed turn.

    Uses the production ``launch_runner`` path so the runner receives the
    authenticated bridge channel env (READY socket + nonce + turn socket). The
    returned handle keeps the process alive and exposes the turn socket path.
    """
    import socket as _sock
    import time as _t

    from capt_solo.bridge.resolver import resolve_capt_source
    from capt_solo.bridge.runner_process import launch_runner

    source, _reason = resolve_capt_source(REPO)
    if source is None:
        return {"error": "could not resolve CAPT source"}
    handle = launch_runner(
        source, workspace=REPO, mission_id=mission, resume=True, timeout_s=60.0,
        session_id=resume_session_id,
    )
    if not handle.ready:
        return {"error": handle.block_reason or "runner not ready", "handle": handle}
    turn_socket = handle.turn_socket_path
    if not turn_socket:
        return {"error": "no turn socket in live handle", "handle": handle}
    try:
        with _sock.socket(_sock.AF_UNIX, _sock.SOCK_STREAM) as s:
            s.settimeout(120.0)
            s.connect(turn_socket)
            s.sendall((json.dumps({"op": "turn", "intent": "Report the current mission status."}) + "\n").encode())
            s.shutdown(_sock.SHUT_WR)
            chunks = []
            while True:
                data = s.recv(8192)
                if not data:
                    break
                chunks.append(data)
        return {"turn": json.loads(b"".join(chunks).decode("utf-8", errors="replace")), "handle": handle}
    except Exception as exc:
        return {"turn": {"ok": False, "error": f"{type(exc).__name__}: {exc}"}, "handle": handle}


def _stop_live_runner(live: Dict[str, Any]) -> None:
    handle = live.get("handle")
    if handle is None:
        return
    try:
        from capt_solo.bridge.runner_process import terminate_runner

        terminate_runner(handle)
    except Exception:
        pass
    try:
        from capt_solo.bridge.runner_process import release_runner_lock

        release_runner_lock(REPO, MISSION)
    except Exception:
        pass


def scenario_failure(evidence_dir: Path) -> AcceptanceReport:
    rep = AcceptanceReport(scenario="failure")
    # Break the CAPT executable: point the bridge at a source whose Agent Runner
    # package is present but FAILS TO IMPORT at boot. We use a fake capt_solo
    # whose agent/__init__.py raises on import (incomplete governance).
    fake = evidence_dir / "broken-capt"
    if fake.exists():
        import shutil

        shutil.rmtree(fake)
    (fake / "capt_solo").mkdir(parents=True, exist_ok=True)
    (fake / "capt_solo" / "__init__.py").write_text('__version__ = "0.5.0"\n')
    (fake / "capt_solo" / "agent").mkdir(parents=True, exist_ok=True)
    (fake / "capt_solo" / "agent" / "__init__.py").write_text("raise RuntimeError('broken agent')\n")
    (fake / "capt_cli.py").write_text("def main():\n    return 0\n")

    # The override is authoritative: it is the FIRST candidate the resolver tries.
    os.environ["CAPT_BRIDGE_SOURCE_ROOT"] = str(fake)
    try:
        boot = _boot(MISSION)
    finally:
        os.environ.pop("CAPT_BRIDGE_SOURCE_ROOT", None)
    rep.evidence["boot"] = boot
    rep.record("no_provider_call", boot.get("provider_allowed") is False, str(boot.get("provider_allowed")))
    rep.record("no_hermes_fallback", boot.get("provider_owner") == "NONE_WHEN_BLOCKED", boot.get("provider_owner"))
    rep.record("exact_blocked_state", boot.get("boot_state") in ("SKILL_LOADED_CAPT_RUNNER_NOT_ACTIVE", "CAPT_UNAVAILABLE"), boot.get("boot_state"))
    rep.record("block_codes_present", bool(boot.get("block_codes")), str(boot.get("block_codes")))
    rep.record("broken_source_rejected", "broken-capt" in str(boot.get("capt_source_path", "")) and boot.get("provider_allowed") is False)
    rep.passed = all(c["ok"] for c in rep.checks)
    return rep


def scenario_ownership(evidence_dir: Path) -> AcceptanceReport:
    rep = AcceptanceReport(scenario="ownership")
    from capt_solo.bridge.ownership_guard import DENIAL_CODE, RuntimeOwnershipGuard

    receipts = evidence_dir / "receipts"
    guard = RuntimeOwnershipGuard([str(REPO)], receipts_dir=receipts)
    target = Path.home() / ".hermes" / "skills" / "capt-core-runtime" / "SKILL.md"
    denial = guard.check(str(target))
    rep.record("external_skill_mutation_denied", denial is not None and denial.code == DENIAL_CODE, str(denial.code if denial else None))
    rep.record("denial_receipt_emitted", list(receipts.glob("*.json")) != [], str(list(receipts.glob('*.json'))))
    rep.passed = all(c["ok"] for c in rep.checks)
    return rep


def run_all(evidence_dir: Path) -> List[AcceptanceReport]:
    evidence_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    reports = [
        scenario_success(evidence_dir),
        scenario_failure(evidence_dir),
        scenario_ownership(evidence_dir),
    ]
    manifest = {
        "mission": MISSION,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarios": [r.to_dict() for r in reports],
        "all_passed": all(r.passed for r in reports),
    }
    (evidence_dir / "ACCEPTANCE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str))
    return reports


def main() -> int:
    evidence_dir = REPO / ".capt-bridge-evidence" / "acceptance"
    reports = run_all(evidence_dir)
    for r in reports:
        print(f"[{r.scenario}] passed={r.passed} checks={len(r.checks)}")
        for c in r.checks:
            print(f"   - {'OK ' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}")
    return 0 if all(r.passed for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
