"""Runner-side serve loop: boot → emit READY → serve governed turns.

This runs *inside* the canonical CAPT Agent Runner process. It is the other half
of the bridge handshake:

1. boot the mission through ``AgentRunner.boot`` (canonical CAPT governance —
   mission/session/checkpoint recovery, directives, memory selection,
   ContextPack, MemoryUseGate, CTP, KHSB);
2. emit an authenticated ``BridgeReadyEvent`` over the bridge's connect-back
   socket **only** when the boot actually reached GOVERNED;
3. serve governed turns on a private turn socket until shutdown, checkpointing
   coherently on interruption.

Nothing here reimplements governance; it calls canonical CAPT and reports IDs.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import sys
import threading
from pathlib import Path
from typing import Any, Optional

from capt_solo.bridge.contracts import BridgeReadyEvent
from capt_solo.bridge.runner_process import emit_ready_event

_MAX_REQUEST_BYTES = 256 * 1024


class _ServeState:
    def __init__(self) -> None:
        self.shutdown = threading.Event()
        self.runner: Any = None
        self.state: Any = None
        self.boot_result: Any = None


def _ctp_tx_id(runner: Any) -> str:
    """Open a CTP transaction for the governed session, if CTP is available."""
    try:
        return str(runner.rt.ctp.begin(correlation_id="capt-bridge-session") or "")
    except Exception:
        try:
            return str(runner.rt.ctp.begin() or "")
        except Exception:
            return ""


def _khsb_correlation(runner: Any, mission_id: str, run_id: str) -> str:
    """Publish the bridge-ready event on KHSB and return a correlation id."""
    correlation = f"khsb-bridge-{run_id}"
    try:
        runner.rt.bus.publish(
            "agent.bridge.ready",
            {"mission_id": mission_id, "run_id": run_id, "correlation_id": correlation},
        )
    except Exception:
        return ""
    return correlation


def serve(
    *,
    workspace: str,
    mission_id: str,
    output_mode: str = "cave",
    resume: bool = True,
    session_id: str = "",
) -> int:
    """Boot, hand shake, and serve governed turns. Returns a process exit code."""
    from capt_solo.agent import AgentBootRequest
    from capt_solo.agent.runner import AgentRunner

    turn_socket = os.environ.get("CAPT_BRIDGE_TURN_SOCKET", "")
    if not turn_socket:
        # Deterministic fallback so an operator (or the acceptance harness) can
        # reach the turn channel without the launcher's env injection.
        base = Path(workspace) / ".capt" / "bridge" / "sock"
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        turn_socket = str(base / f"turn-{secrets.token_hex(8)}.sock")
    st = _ServeState()

    runner = AgentRunner.load()
    st.runner = runner

    def _shutdown(signum: int, _frame: Any) -> None:
        st.shutdown.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _shutdown)
        except Exception:
            pass

    try:
        boot_result = runner.boot(
            AgentBootRequest(
                workspace_path=workspace,
                mission_id=mission_id,
                output_mode=output_mode,
                session_id=session_id,
            )
        )
        st.boot_result = boot_result

        if boot_result.execution_mode != "GOVERNED":
            # Fail closed: no READY event is emitted, so the bridge blocks.
            sys.stderr.write(
                json.dumps(
                    {
                        "bridge_serve": "BLOCKED",
                        "execution_mode": boot_result.execution_mode,
                        "gate_result": boot_result.gate_result,
                        "block_reason": boot_result.block_reason,
                        "block_codes": list(boot_result.block_codes),
                    }
                )
                + "\n"
            )
            return 3

        trace = boot_result.boot_trace
        run_id = trace.agent_run_id if trace else ""
        tx_id = _ctp_tx_id(runner)
        correlation = _khsb_correlation(runner, boot_result.mission_id, run_id)

        event = BridgeReadyEvent(
            run_id=run_id,
            mission_id=boot_result.mission_id,
            session_id=boot_result.session_id,
            intent_id=trace.intent_id if trace else "",
            checkpoint_id=boot_result.checkpoint_id,
            contextpack_digest=trace.contextpack_digest if trace else "",
            memory_use_decision_id=trace.memory_use_decision_id if trace else "",
            memory_use_gate="PASS" if boot_result.gate_result == "PASS" else boot_result.gate_result,
            ctp_transaction_id=tx_id,
            khsb_correlation_id=correlation,
            provider_owner="CAPT_AGENT_RUNNER",
            execution_mode=boot_result.execution_mode,
        )
        ok, why = emit_ready_event(event)
        if not ok:
            sys.stderr.write(
                json.dumps({"bridge_serve": "READY_EMIT_FAILED", "reason": why}) + "\n"
            )
            return 4

        # Persist the durable session id back to the mission checkpoint so a
        # future fresh bridge process resumes the SAME session (continuity
        # authority lives in CAPT, not Hermes). Stored in a SIDECAR, not the
        # checkpoint body, because the checkpoint body is integrity-digested and
        # mutating it would fail the digest check on the next boot.
        try:
            from capt_solo.bridge.runner_process import _session_sidecar_path

            _session_sidecar_path(Path(workspace), mission_id).write_text(
                boot_result.session_id, encoding="utf-8"
            )
        except Exception:
            pass

        st.state = runner.run_state(boot_result)

        if turn_socket:
            _serve_turns(st, turn_socket)
        else:
            st.shutdown.wait()
        return 0
    except Exception as exc:
        sys.stderr.write(
            json.dumps({"bridge_serve": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
            + "\n"
        )
        return 5
    finally:
        _checkpoint_on_exit(st)
        try:
            from capt_solo.bridge.runner_process import release_runner_lock

            release_runner_lock(Path(workspace), mission_id)
        except Exception:
            pass
        try:
            runner.close()
        except Exception:
            pass


def _serve_turns(st: _ServeState, turn_socket: str) -> None:
    """Accept turn requests until shutdown."""
    path = Path(turn_socket)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        path.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    os.chmod(str(path), 0o600)
    srv.listen(4)
    srv.settimeout(0.5)
    try:
        while not st.shutdown.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            try:
                _handle_turn(st, conn)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    finally:
        try:
            srv.close()
        except Exception:
            pass
        try:
            path.unlink()
        except OSError:
            pass


def _handle_turn(st: _ServeState, conn: socket.socket) -> None:
    conn.settimeout(600.0)
    chunks = []
    total = 0
    while total < _MAX_REQUEST_BYTES:
        data = conn.recv(8192)
        if not data:
            break
        chunks.append(data)
        total += len(data)
        if data.endswith(b"\n"):
            break
    raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
    try:
        req = json.loads(raw) if raw else {}
    except Exception:
        conn.sendall(json.dumps({"ok": False, "error": "malformed turn request"}).encode())
        return

    if req.get("op") == "shutdown":
        st.shutdown.set()
        conn.sendall(json.dumps({"ok": True, "shutdown": True}).encode())
        return

    intent_text = str(req.get("intent") or "")
    resp = _run_governed_turn(st, intent_text)
    conn.sendall(json.dumps(resp, default=str).encode("utf-8"))


def _run_governed_turn(st: _ServeState, intent_text: str) -> dict:
    """Execute one governed turn through canonical CAPT."""
    from capt_solo.agent import AgentTurnRequest, IntentRecord

    runner, state = st.runner, st.state
    if runner is None or state is None:
        return {"ok": False, "error": "runner state unavailable"}

    provider, note = _provider_from_env()
    if provider is None:
        return {
            "ok": False,
            "error": f"no CAPT provider configured: {note}",
            "provider_owner": "CAPT_AGENT_RUNNER",
            "execution_mode": "GOVERNED",
        }

    try:
        intent = IntentRecord.mint(
            mission_id=state.mission_id,
            session_id=state.session_id,
            turn_id=state.next_turn_id(),
            requested_goal=intent_text,
            current_goal=intent_text,
            output_policy=state.output_policy,
        )
        turn = runner.run_turn(
            state,
            AgentTurnRequest(intent=intent, user_input=intent_text),
            provider=provider,
        )
        return {
            "ok": bool(turn.ok),
            "output": turn.visible_output,
            "tx_id": turn.tx_id,
            "checkpoint_id": turn.checkpoint_id,
            "claim_supported": turn.claim_supported,
            "intent_id": intent.intent_id,
            "provider": note,
            "provider_owner": "CAPT_AGENT_RUNNER",
            "execution_mode": "GOVERNED",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "provider_owner": "CAPT_AGENT_RUNNER",
            "execution_mode": "GOVERNED",
        }


def _provider_from_env():
    endpoint = os.environ.get("CAPT_MODEL_ENDPOINT") or os.environ.get("LM_STUDIO_ENDPOINT")
    model_id = os.environ.get("CAPT_MODEL_ID") or os.environ.get("LM_STUDIO_MODEL")
    if not endpoint or not model_id:
        return None, "set CAPT_MODEL_ENDPOINT and CAPT_MODEL_ID"
    from capt_solo.model_task import OpenAICompatibleLocalProvider

    token = os.environ.get("CAPT_MODEL_API_KEY") or os.environ.get("LM_STUDIO_API_KEY")
    provider = OpenAICompatibleLocalProvider(
        endpoint=endpoint, model_id=model_id, api_token=token, local=True
    )
    return provider, f"openai-compatible-local model={model_id} auth={'yes' if token else 'none'}"


def _checkpoint_on_exit(st: _ServeState) -> None:
    """Checkpoint coherently on interruption through canonical CAPT."""
    runner, state = st.runner, st.state
    if runner is None or state is None:
        return
    try:
        checkpoint = getattr(runner, "checkpoint", None)
        if callable(checkpoint):
            checkpoint(state)
    except Exception:
        pass
