"""Bridge boot orchestration: resolve → doctor → launch → validate READY.

Every failure path returns a fail-closed :class:`BridgeResult`. This module owns
no governance logic: mission/session recovery, ContextPack, MemoryUseGate, CTP,
KHSB, checkpointing and provider invocation all happen **inside** the canonical
CAPT Agent Runner. The bridge only proves that they happened, via the
authenticated READY event.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from capt_solo.bridge.contracts import (
    BLOCK_CAPT_INCOMPLETE,
    BLOCK_CAPT_NOT_IMPORTABLE,
    BLOCK_DOCTOR_FAILED,
    BLOCK_MISSION_REQUIRED,
    BLOCK_WORKSPACE_MISSING,
    BOOT_STATE_FULL,
    BOOT_STATE_PARTIAL,
    BOOT_STATE_SKILL_ONLY,
    BOOT_STATE_UNAVAILABLE,
    OWNER_CAPT_AFTER_READY,
    BridgeResult,
    blocked,
)
from capt_solo.bridge.resolver import CaptSource, resolve_capt_source
from capt_solo.bridge.runner_process import (
    DEFAULT_STARTUP_TIMEOUT_S,
    RunnerHandle,
    launch_runner,
)

DOCTOR_TIMEOUT_S = 60.0


def _recover_session_id(workspace: Path, mission_id: str) -> str:
    """Return the durable session id CAPT already bound to this mission, if any.

    Continuity authority is CAPT's, not Hermes'. When a prior governed run
    checkpointed a session, a fresh bridge process must resume that exact session
    rather than minting a new one — otherwise the "second fresh process resumes
    from CAPT state" acceptance criterion is hollow. The id is read from a
    sidecar written by the runner (never from the integrity-digested checkpoint
    body).
    """
    try:
        from capt_solo.bridge.runner_process import _session_sidecar_path

        p = _session_sidecar_path(workspace, mission_id)
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def run_doctor(source: CaptSource) -> Tuple[bool, dict, str]:
    """Run ``capt --json agent doctor``.

    Note the flag position: ``--json`` is a *top-level* flag in the real CLI.
    ``capt agent doctor --json`` exits non-zero with
    ``unrecognized arguments: --json`` — verified against the implementation.
    """
    argv = [*source.launch_argv, "--json", "agent", "doctor"]
    try:
        out = subprocess.run(  # noqa: S603 - argv list, shell=False
            argv,
            capture_output=True,
            text=True,
            timeout=DOCTOR_TIMEOUT_S,
            check=False,
            cwd=str(source.root),
        )
    except subprocess.TimeoutExpired:
        return False, {}, f"agent doctor timed out after {DOCTOR_TIMEOUT_S:g}s"
    except Exception as exc:
        return False, {}, f"agent doctor failed to run: {type(exc).__name__}: {exc}"
    if out.returncode != 0:
        return False, {}, f"agent doctor exit {out.returncode}: {(out.stderr or '').strip()[:400]}"
    try:
        report = json.loads(out.stdout or "{}")
    except Exception as exc:
        return False, {}, f"agent doctor emitted non-JSON output: {exc}"
    if not isinstance(report, dict):
        return False, {}, "agent doctor report is not an object"
    if not report.get("ok"):
        return False, report, f"agent doctor reported not-ok: {report}"
    return True, report, ""


def boot_bridge(
    *,
    workspace_path: str,
    mission_id: str,
    resume: bool = True,
    timeout_s: float = DEFAULT_STARTUP_TIMEOUT_S,
    skill_present: bool = True,
) -> Tuple[BridgeResult, Optional[RunnerHandle]]:
    """Full bridge boot. Returns ``(result, handle)``; handle is None when blocked
    before launch."""
    # ``skill_present`` distinguishes the two "CAPT can't run" states: with a
    # loaded skill and no runner we are in the exact defect state this mission
    # exists to eliminate, and we name it precisely.
    unavailable_state = BOOT_STATE_SKILL_ONLY if skill_present else BOOT_STATE_UNAVAILABLE

    if not mission_id:
        return (
            blocked(
                "explicit mission id is required; the bridge never infers a mission",
                (BLOCK_MISSION_REQUIRED,),
                boot_state=unavailable_state,
            ),
            None,
        )

    workspace = Path(workspace_path).expanduser().resolve()
    if not workspace.is_dir():
        return (
            blocked(
                f"workspace path does not exist: {workspace}",
                (BLOCK_WORKSPACE_MISSING,),
                boot_state=unavailable_state,
                mission_id=mission_id,
                workspace_path=str(workspace),
            ),
            None,
        )

    source, reason = resolve_capt_source(workspace)
    if source is None:
        return (
            blocked(
                reason or "no canonical CAPT source found",
                (BLOCK_CAPT_NOT_IMPORTABLE,),
                boot_state=unavailable_state,
                mission_id=mission_id,
                workspace_path=str(workspace),
            ),
            None,
        )
    if not source.complete:
        return (
            blocked(
                "resolved CAPT source lacks the Agent Runner: "
                + ", ".join(source.missing_modules)
                + f" (root={source.root})",
                (BLOCK_CAPT_INCOMPLETE,),
                boot_state=unavailable_state,
                mission_id=mission_id,
                workspace_path=str(workspace),
                capt_source_path=str(source.root),
                notes=source.notes,
            ),
            None,
        )

    doctor_ok, report, doctor_reason = run_doctor(source)
    if not doctor_ok:
        return (
            blocked(
                doctor_reason,
                (BLOCK_DOCTOR_FAILED,),
                boot_state=unavailable_state,
                mission_id=mission_id,
                workspace_path=str(workspace),
                capt_source_path=str(source.root),
            ),
            None,
        )

    # Recover CAPT's durable session for this mission so a second fresh process
    # resumes the SAME session (continuity authority lives in CAPT, not Hermes).
    recovered_session_id = _recover_session_id(workspace, mission_id)

    handle = launch_runner(
        source,
        workspace=workspace,
        mission_id=mission_id,
        resume=resume,
        timeout_s=timeout_s,
        session_id=recovered_session_id,
    )

    common = {
        "mission_id": mission_id,
        "workspace_path": str(workspace),
        "capt_source_path": str(source.root),
        "runner_command": handle.argv,
        "runner_pid": handle.pid,
        "doctor_ok": True,
    }

    if not handle.ready:
        # The runner was reachable and doctor passed, so CAPT is present but the
        # governed chain did not complete: PARTIAL, and provider stays blocked.
        return (
            blocked(
                handle.block_reason or "runner did not reach a validated READY state",
                handle.block_codes or ("READY_EVENT_NOT_RECEIVED",),
                boot_state=BOOT_STATE_PARTIAL,
                **common,
            ),
            handle,
        )

    ev = handle.ready_event
    assert ev is not None
    # Persist the durable session id to the sidecar so a future fresh bridge
    # process resumes the SAME session (continuity authority lives in CAPT).
    try:
        from capt_solo.bridge.runner_process import _session_sidecar_path

        _session_sidecar_path(workspace, mission_id).write_text(
            ev.session_id, encoding="utf-8"
        )
    except Exception:
        pass
    return (
        BridgeResult(
            boot_state=BOOT_STATE_FULL,
            provider_owner=OWNER_CAPT_AFTER_READY,
            session_id=ev.session_id,
            checkpoint_id=ev.checkpoint_id,
            intent_id=ev.intent_id,
            contextpack_digest=ev.contextpack_digest,
            memory_use_decision_id=ev.memory_use_decision_id,
            memory_use_gate=ev.memory_use_gate,
            ctp_transaction_id=ev.ctp_transaction_id,
            khsb_correlation_id=ev.khsb_correlation_id,
            execution_mode=ev.execution_mode,
            ready_event=ev,
            **common,
        ),
        handle,
    )


def write_evidence(result: BridgeResult, evidence_dir: Path, name: str) -> Path:
    """Persist a bridge result as evidence with a sidecar digest."""
    import hashlib

    evidence_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = evidence_dir / f"{name}.json"
    body = result.to_json()
    path.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    path.with_suffix(".json.sha256").write_text(
        f"sha256:{digest}  {path.name}\n", encoding="utf-8"
    )
    os.chmod(path, 0o600)
    return path
