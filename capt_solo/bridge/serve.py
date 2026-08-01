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
import logging
import os
import secrets
import signal
import socket
import sys
import threading
import hmac
from pathlib import Path
from typing import Any, Optional

from capt_solo.bridge.contracts import BridgeReadyEvent
from capt_solo.bridge.protocol import (
    BridgeProtocolError,
    ERR_INVALID_AUTH,
    ERR_MALFORMED,
    ERR_MISSING_AUTH,
    ERR_OVERSIZED,
    ERR_REPLAYED,
    ERR_STALE_GENERATION,
    OP_SHUTDOWN,
    OP_TURN,
    TurnEnvelope,
    compute_receipt_digest,
    make_auth_token,
)

logger = logging.getLogger(__name__)
from capt_solo.bridge.runner_process import emit_ready_event

_MAX_REQUEST_BYTES = 256 * 1024


class _ServeState:
    def __init__(self) -> None:
        self.shutdown = threading.Event()
        self.runner: Any = None
        self.state: Any = None
        self.boot_result: Any = None
        self.runtime_id: str = ""
        self.runtime_generation: int = 1
        self.turn_auth: str = ""


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
    turn_auth = os.environ.get("CAPT_BRIDGE_TURN_AUTH", "")
    runtime_id = os.environ.get("CAPT_BRIDGE_RUNTIME_ID", "")
    runtime_generation = int(os.environ.get("CAPT_BRIDGE_RUNTIME_GENERATION", "1") or "1")
    if not turn_socket:
        # Deterministic fallback so an operator can reach the turn channel
        # without the launcher's env injection. The channel is STILL
        # authenticated: we mint a fresh runtime-scoped token and log it. An
        # unauthenticated turn channel is never acceptable, even for debugging.
        base = Path(workspace) / ".capt" / "bridge" / "sock"
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        turn_socket = str(base / f"turn-{secrets.token_hex(8)}.sock")
        turn_auth = make_auth_token()
        logger.warning(
            "TURN_CHANNEL_FALLBACK_AUTH turn_socket=%s auth_token=%s "
            "(launcher env not injected; token required for any turn)",
            turn_socket, turn_auth,
        )
    st = _ServeState()
    st.runtime_id = runtime_id
    st.runtime_generation = runtime_generation
    st.turn_auth = turn_auth

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

        # Persist integrity-bound continuity metadata (replaces plaintext .sid).
        # Authority stays in CAPT's checkpoint; this metadata references and
        # validates it. Failures are structured, never silently ignored.
        try:
            from capt_solo.bridge.continuity import save_continuity

            save_continuity(
                Path(workspace),
                mission_id=boot_result.mission_id,
                session_id=boot_result.session_id,
                checkpoint_id=boot_result.checkpoint_id,
                runtime_id=runtime_id,
                runtime_generation=runtime_generation,
                previous_generation=max(0, runtime_generation - 1),
                checkpoint_digest=boot_result.checkpoint_id,
                fencing_token=secrets.token_hex(16),
            )
        except Exception as exc:
            sys.stderr.write(
                json.dumps(
                    {"bridge_serve": "CONTINUITY_WRITE_FAILED", "reason": f"{type(exc).__name__}: {exc}"}
                )
                + "\n"
            )
            return 6

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
            from capt_solo.bridge.lease import release_runner_lease

            release_runner_lease(
                Path(workspace), mission_id, lease=None
            )
        except Exception:
            pass
        try:
            runner.close()
        except Exception:
            pass


def _serve_turns(st: _ServeState, turn_socket: str) -> None:
    """Accept authenticated turn requests until shutdown."""
    path = Path(turn_socket)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        path.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    os.chmod(str(path), 0o600)
    srv.listen(4)
    srv.settimeout(0.5)
    # Bounded replay protection: remember recent request_ids for this process.
    seen: "set[str]" = set()
    try:
        while not st.shutdown.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            try:
                _handle_turn(st, conn, seen)
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


def _handle_turn(st: _ServeState, conn: socket.socket, seen: "set[str]") -> None:
    conn.settimeout(600.0)
    chunks = []
    total = 0
    oversized = False
    # Read until EOF so the client's sendall always completes (no deadlock).
    # Track oversized against the bound; respond after the full body is drained.
    while True:
        data = conn.recv(8192)
        if not data:
            break
        if total < _MAX_REQUEST_BYTES:
            chunks.append(data)
        total += len(data)
        if total >= _MAX_REQUEST_BYTES:
            oversized = True
    if oversized:
        conn.sendall(
            json.dumps({"ok": False, "error": "TURN_OVERSIZED", "message": "request too large"}).encode()
        )
        return
    raw = b"".join(chunks)
    try:
        req = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
    except Exception:
        conn.sendall(
            json.dumps({"ok": False, "error": "TURN_MALFORMED", "message": "invalid JSON"}).encode()
        )
        return

    # Authenticate + validate the envelope.
    try:
        env = TurnEnvelope.from_mapping(req)
    except BridgeProtocolError as exc:
        conn.sendall(json.dumps(exc.to_dict()).encode())
        return

    # Auth token (bound to runtime identity + generation).
    if not env.auth:
        conn.sendall(
            json.dumps(
                {"ok": False, "error": "TURN_UNAUTHENTICATED", "message": "no auth token presented"}
            ).encode()
        )
        return
    if not st.turn_auth:
        conn.sendall(
            json.dumps(
                {"ok": False, "error": "TURN_UNAUTHENTICATED", "message": "channel not authenticated"}
            ).encode()
        )
        return
    if not hmac.compare_digest(env.auth, st.turn_auth):
        conn.sendall(
            json.dumps({"ok": False, "error": "TURN_INVALID_AUTH", "message": "bad auth token"}).encode()
        )
        return
    if env.runtime_id != st.runtime_id or env.runtime_generation != st.runtime_generation:
        conn.sendall(
            json.dumps(
                {"ok": False, "error": "TURN_STALE_GENERATION", "message": "runtime identity/generation mismatch"}
            ).encode()
        )
        return
    if env.request_id in seen:
        conn.sendall(
            json.dumps({"ok": False, "error": "TURN_REPLAYED", "message": "request_id already seen"}).encode()
        )
        return
    seen.add(env.request_id)

    if env.op == OP_SHUTDOWN:
        st.shutdown.set()
        conn.sendall(json.dumps({"ok": True, "shutdown": True}).encode())
        return

    intent_text = str(env.payload.get("intent") or "")
    resp = _run_governed_turn(st, env, intent_text)
    conn.sendall(json.dumps(resp, default=str).encode("utf-8"))


def _run_governed_turn(st: _ServeState, env: "TurnEnvelope", intent_text: str) -> dict:
    """Execute one governed turn through canonical CAPT; return a TurnReceipt."""
    from capt_solo.agent import AgentTurnRequest, IntentRecord

    runner, state = st.runner, st.state
    if runner is None or state is None:
        return {"ok": False, "error": "runner state unavailable", "provider_owner": "CAPT_AGENT_RUNNER"}

    provider, note = _provider_from_env()
    if provider is None:
        return {
            "ok": False,
            "error": f"no CAPT provider configured: {note}",
            "provider_owner": "CAPT_AGENT_RUNNER",
            "execution_mode": "GOVERNED",
        }

    try:
        ckpt_before = state.checkpoint_id or ""
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
        ckpt_after = turn.checkpoint_id or ckpt_before
        receipt = {
            "request_id": env.request_id,
            "turn_id": intent.intent_id,
            "mission_id": state.mission_id,
            "session_id": state.session_id,
            "runtime_id": st.runtime_id,
            "runtime_generation": st.runtime_generation,
            "provider_owner": "CAPT_AGENT_RUNNER",
            "execution_mode": "GOVERNED",
            "ctp_transaction_id": turn.tx_id or "",
            "checkpoint_before": ckpt_before,
            "checkpoint_after": ckpt_after,
            "claim_supported": bool(turn.claim_supported),
        }
        receipt["receipt_digest"] = compute_receipt_digest(receipt)
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
            "receipt": receipt,
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
