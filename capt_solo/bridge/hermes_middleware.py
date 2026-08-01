"""Hermes ``llm_execution`` middleware — the actual authority transfer.

This is the only component that touches Hermes. It is registered through the
documented plugin API (``PluginContext.register_middleware``) and is invoked by
Hermes at ``agent/conversation_loop.py`` where **every** main-loop provider call is
routed through ``run_llm_execution_middleware``.

THE CRITICAL CONSTRAINT (verified in Hermes source, ``hermes_cli/middleware.py``
``_run_execution_chain``):

    except Exception as exc:
        logger.warning(...)
        if next_succeeded: return next_result
        if next_called:    raise
        return call_at(index + 1, payload)   # <-- FALLS THROUGH TO THE PROVIDER

A middleware that *raises* does **not** block the provider; Hermes swallows the
exception and calls the provider anyway. Raising is the fail-OPEN path.

Therefore this middleware blocks by **returning a synthetic response** and never
lets an exception escape. The outermost handler catches ``BaseException`` and
still returns a blocked response. ``next_call`` is invoked in exactly one branch:
``HERMES_BEFORE_BRIDGE``, before any transfer has been attempted.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from capt_solo.bridge.contracts import (
    OWNER_CAPT_AFTER_READY,
    OWNER_HERMES_BEFORE_BRIDGE,
    OWNER_NONE_WHEN_BLOCKED,
    BridgeResult,
    ProviderOwnership,
)

logger = logging.getLogger(__name__)

FALLBACK_AUTH_ENV = "CAPT_BRIDGE_ALLOW_HERMES_FALLBACK"


# ---------------------------------------------------------------------------
# synthetic responses (OpenAI chat-completions shape Hermes already parses)
# ---------------------------------------------------------------------------
@dataclass
class _Message:
    role: str = "assistant"
    content: str = ""
    tool_calls: Optional[list] = None
    reasoning_content: Optional[str] = None


@dataclass
class _Choice:
    message: _Message
    finish_reason: str = "stop"
    index: int = 0


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class BridgeResponse:
    """A provider-shaped response produced by the bridge, not by a provider.

    ``bridge_origin`` marks it unambiguously so evidence can distinguish a
    CAPT-owned turn from a Hermes-owned one.
    """

    def __init__(self, content: str, *, owner: str, blocked: bool) -> None:
        self.choices = [_Choice(message=_Message(content=content))]
        self.usage = _Usage()
        self.model = "capt-agent-runner"
        self.id = "capt-bridge"
        self.bridge_origin = True
        self.bridge_provider_owner = owner
        self.bridge_blocked = blocked


def _blocked_text(result: Optional[BridgeResult], detail: str = "") -> str:
    codes = list(result.block_codes) if result else []
    reason = (result.block_reason if result else "") or detail
    state = result.boot_state if result else "CAPT_UNAVAILABLE"
    payload = {
        "capt_bridge": "BLOCKED",
        "boot_state": state,
        "provider_owner": OWNER_NONE_WHEN_BLOCKED,
        "block_codes": codes,
        "block_reason": reason,
        "hermes_native_provider": "SUPPRESSED",
        "silent_fallback": False,
        "remedy": (
            "The CAPT Agent Runner did not reach a validated READY state. "
            "Hermes-native provider execution is not a permitted fallback. "
            "Resolve the block codes, or set "
            f"{FALLBACK_AUTH_ENV}=1 to explicitly authorize Hermes-native execution."
        ),
    }
    return (
        "CAPT BOOTSTRAP BRIDGE — PROVIDER BLOCKED\n\n"
        + json.dumps(payload, indent=2, sort_keys=True)
    )


# ---------------------------------------------------------------------------
# bridge session state
# ---------------------------------------------------------------------------
class BridgeSession:
    """Holds provider ownership and the validated bridge result for a process."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.ownership = ProviderOwnership(OWNER_HERMES_BEFORE_BRIDGE)
        self.result: Optional[BridgeResult] = None
        self.handle: Any = None
        self.transfer_attempted = False
        self.invocations: list = []

    # -- state transitions --------------------------------------------------
    def record_ready(self, result: BridgeResult, handle: Any = None) -> None:
        with self._lock:
            self.transfer_attempted = True
            self.result = result
            self.handle = handle
            if result.provider_allowed:
                self.ownership.transition(OWNER_CAPT_AFTER_READY)
            else:
                self.ownership.transition(OWNER_NONE_WHEN_BLOCKED)

    def record_block(self, result: BridgeResult) -> None:
        with self._lock:
            self.transfer_attempted = True
            self.result = result
            if self.ownership.owner != OWNER_NONE_WHEN_BLOCKED:
                self.ownership.transition(OWNER_NONE_WHEN_BLOCKED)

    def authorize_hermes_fallback(self) -> bool:
        """Explicit owner authorization; never inferred, never automatic."""
        if os.environ.get(FALLBACK_AUTH_ENV) != "1":
            return False
        with self._lock:
            try:
                self.ownership.transition(
                    OWNER_HERMES_BEFORE_BRIDGE, owner_authorized=True
                )
            except Exception:
                return False
        return True

    def note_invocation(self, owner: str, blocked: bool) -> None:
        with self._lock:
            self.invocations.append(
                {"t": time.time(), "owner": owner, "blocked": blocked}
            )

    @property
    def hermes_native_invocations(self) -> int:
        return sum(
            1
            for i in self.invocations
            if i["owner"] == OWNER_HERMES_BEFORE_BRIDGE and not i["blocked"]
        )

    @property
    def capt_owned_invocations(self) -> int:
        return sum(1 for i in self.invocations if i["owner"] == OWNER_CAPT_AFTER_READY)


_SESSION: Optional[BridgeSession] = None
_SESSION_LOCK = threading.Lock()


def get_session() -> BridgeSession:
    global _SESSION
    with _SESSION_LOCK:
        if _SESSION is None:
            _SESSION = BridgeSession()
        return _SESSION


def reset_session() -> BridgeSession:
    """Test/CLI helper — a fresh process starts with a fresh session anyway."""
    global _SESSION
    with _SESSION_LOCK:
        _SESSION = BridgeSession()
        return _SESSION


# ---------------------------------------------------------------------------
# the middleware
# ---------------------------------------------------------------------------
def llm_execution_middleware(
    request: Dict[str, Any],
    next_call: Callable[[Dict[str, Any]], Any],
    **context: Any,
) -> Any:
    """Own, block, or pass through provider execution.

    Contract with Hermes: returning a value suppresses the provider; calling
    ``next_call`` executes it. This function must NEVER raise (see module
    docstring — Hermes treats a raising middleware as fail-open).
    """
    session = get_session()
    try:
        owner = session.ownership.owner

        # 1. CAPT owns the provider: return CAPT output, never call next_call.
        if owner == OWNER_CAPT_AFTER_READY:
            result = session.result
            handle = session.handle
            # Runner death after READY blocks; it does not fall back.
            if handle is not None:
                try:
                    from capt_solo.bridge.runner_process import runner_alive

                    if not runner_alive(handle):
                        from capt_solo.bridge.contracts import (
                            BLOCK_RUNNER_DIED,
                            BOOT_STATE_PARTIAL,
                            blocked as _blocked,
                        )

                        dead = _blocked(
                            "CAPT Agent Runner died after READY; "
                            "Hermes-native fallback is not permitted",
                            (BLOCK_RUNNER_DIED,),
                            boot_state=BOOT_STATE_PARTIAL,
                            mission_id=result.mission_id if result else "",
                        )
                        session.record_block(dead)
                        session.note_invocation(OWNER_NONE_WHEN_BLOCKED, True)
                        return BridgeResponse(
                            _blocked_text(dead),
                            owner=OWNER_NONE_WHEN_BLOCKED,
                            blocked=True,
                        )
                except Exception:
                    pass
            session.note_invocation(OWNER_CAPT_AFTER_READY, False)
            return _capt_turn(session, request, context)

        # 2. Blocked: return a blocked response. next_call is NOT invoked.
        if owner == OWNER_NONE_WHEN_BLOCKED:
            if session.authorize_hermes_fallback():
                session.note_invocation(OWNER_HERMES_BEFORE_BRIDGE, False)
                logger.warning(
                    "CAPT bridge: Hermes-native provider execution explicitly "
                    "authorized via %s",
                    FALLBACK_AUTH_ENV,
                )
                return next_call(request)
            session.note_invocation(OWNER_NONE_WHEN_BLOCKED, True)
            return BridgeResponse(
                _blocked_text(session.result),
                owner=OWNER_NONE_WHEN_BLOCKED,
                blocked=True,
            )

        # 3. Bridge inert (no transfer attempted): Hermes keeps ownership.
        session.note_invocation(OWNER_HERMES_BEFORE_BRIDGE, False)
        return next_call(request)

    except BaseException as exc:  # noqa: BLE001 - intentional: raising is fail-OPEN
        logger.error("CAPT bridge middleware internal error: %r", exc)
        try:
            from capt_solo.bridge.contracts import BLOCK_BRIDGE_INTERNAL_ERROR, blocked as _b

            err = _b(
                f"bridge internal error: {type(exc).__name__}: {exc}",
                (BLOCK_BRIDGE_INTERNAL_ERROR,),
            )
            session.record_block(err)
        except Exception:
            err = None
        return BridgeResponse(
            _blocked_text(err, detail=f"{type(exc).__name__}: {exc}"),
            owner=OWNER_NONE_WHEN_BLOCKED,
            blocked=True,
        )


def _capt_turn(
    session: BridgeSession, request: Dict[str, Any], context: Dict[str, Any]
) -> Any:
    """Route the Intent into CAPT and return bounded CAPT output.

    The Hermes-built ``request`` (system prompt, tool schemas, transcript) is
    deliberately **discarded** except for the user Intent: CAPT owns context
    construction through its own ContextPack. Hermes is transport here.
    """
    result = session.result
    intent = _extract_intent(request)
    from capt_solo.bridge.turn import execute_governed_turn

    text = execute_governed_turn(result, intent, handle=session.handle)
    return BridgeResponse(text, owner=OWNER_CAPT_AFTER_READY, blocked=False)


def _extract_intent(request: Dict[str, Any]) -> str:
    """Pull the latest user Intent out of Hermes' request payload."""
    messages = request.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                return "\n".join(t for t in parts if t)
    return ""
