"""CAPT Operator plugin for Hermes.

Thesis: the model keeps inference and reasoning; CAPT does the rest.

CAPT already defines the exact contract for that split in its own
``capt_runtime/operator_provenance.py::build_prompt_assembly()``: an ordered set
of sections where ``capt-governance`` (order 10) and ``response-mode`` (order 20)
frame the ``human-task`` (order 30). This plugin applies that same framing to a
live Hermes session, without duplicating CAPT's authority:

* the response mode is READ from CAPT's own preference store, never invented here;
* the mode instructions are pinned here but verified against CAPT's source, and
  drift is REPORTED rather than silently tolerated;
* durability goes through RuntimeService over the runtime socket. This plugin
  never opens the ledger database.

Surface (deliberately small — every registered tool is sent on every API call):
    tools: capt_mode, capt_ledger
    hooks: on_session_start, pre_llm_call, transform_llm_output,
           post_api_request, on_session_end, on_session_finalize
    cli:   hermes capt status|mode|checkpoint|recover

Cache safety: Hermes requires a byte-stable system prompt for the life of a
conversation, so nothing here touches the system prompt. The directive rides
``pre_llm_call``'s sanctioned ``{"context": ...}`` channel, which is the same
mechanism skill commands and memory primers use.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import socket
import struct
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths (CAPT owns its own locations; honour its env overrides)
# ---------------------------------------------------------------------------

def _capt_home() -> Path:
    # Core authority only. Legacy CAPT_SOLO_HOME must never redirect this plugin
    # into the disconnected capt_solo runtime/state tree.
    base = os.environ.get("CAPT_STATE_DIR")
    return Path(base) if base else Path.home() / ".capt"


CAPT_HOME = _capt_home()
CAPT_SOCKET = CAPT_HOME / "runtime.sock"
CAPT_TOKEN = CAPT_HOME / "runtime.token"
CAPT_PID = CAPT_HOME / "runtime.pid"
CAPT_PREFS = CAPT_HOME / "ui" / "prompt-preferences.json"

# Where CAPT's canonical source lives, if it is checked out. Used only for the
# drift guard — never imported (different interpreter, different install).
CAPT_SOURCE_CANDIDATES = (
    Path.home() / "CAPT_core" / "capt_runtime" / "operator_provenance.py",
)

# ---------------------------------------------------------------------------
# Response modes — pinned from CAPT, verified against CAPT
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"

# Verbatim from capt_runtime/operator_provenance.py::build_prompt_assembly().
RESPONSE_MODES: Dict[str, str] = {
    "MAX": "Presentation: maximum useful evidence and caveats.",
    "SPOCK": "Presentation: concise, rigorous, technical, high-signal.",
    "CAVE CAPT": "Presentation: plain language, concrete actions, no false certainty.",
    "MIN": "Presentation: only work item, measurement, and PASS/FAIL unless safety requires more.",
}

# Verbatim from the same file — section identity/order/source.
GOVERNANCE_SECTION = (
    "capt-governance",
    10,
    "CAPT governance remains authoritative; return bounded observations.",
    "runtime",
)

DEFAULT_MODE = "SPOCK"            # CAPT's own default when nothing is stored
CONTEXT_BUDGETS = tuple(range(32_000, 256_001, 32_000))

# Verbatim from capt_runtime/verification.py (M0-B). ClaimGuard's statement gate
# accepts ONLY these exact literals, and rejects any statement containing a
# forbidden substring. Pinned here because the plugin must not send a statement
# the gate can never accept, and must be able to apply the overclaim rule locally
# (the forbidden-substring half needs no runtime call at all).
CLAIMGUARD_ALLOWED: Dict[str, str] = {
    "Repository inspected in read-only mode.":
        "claim that a repository was only read",
    "Analysis artifact produced at the recorded artifact location.":
        "claim that an analysis artifact exists at a recorded path",
    "Provider response and immutable artifact recorded for independent verification.":
        "claim that a provider response and artifact were recorded",
    "No repository modification was detected by the specified verification checks.":
        "claim that verification found no repository mutation",
    "The reported observation is supported by the cited source and verification result.":
        "claim that an observation is backed by a cited source",
}

CLAIMGUARD_FORBIDDEN: Tuple[str, ...] = (
    "was fixed",
    "was secured",
    "was merged",
    "was deployed",
    "all vulnerabilities",
    "no mutation was possible",
)

_MODE_STEP = 2                    # minutes between repeated change notices
_LAST_INJECTED: Dict[str, Tuple[str, float]] = {}

# The framing lives in the SESSION PROMPT, not in a per-turn hook. Hermes freezes
# a system-prompt section into each new session and persists it verbatim, so the
# text is charged once per conversation instead of every turn — and the prompt
# stays byte-stable, which is Hermes' own caching invariant.
_SYSTEM_PROMPT_SECTION_ID = "capt-operator-framing"
_SYSTEM_PROMPT_SECTION_MAX_CHARS = 2_000      # cap is 4000; keep well inside it
# session_id -> the mode that was frozen into that session's prompt.
_FRAMING_FROZEN: Dict[str, str] = {}


def _framing_section_content(session_info: Mapping[str, Any]) -> str:
    """Content frozen into each NEW session prompt. Read at session open."""
    return _mode_directive(read_preferences()["responseMode"])


def _claim_vocabulary_drift() -> Optional[Dict[str, Any]]:
    """Check the pinned ClaimGuard vocabulary against CAPT's source."""
    for path in CAPT_SOURCE_CANDIDATES:
        try:
            source = (path.parent / "verification.py").read_text(errors="replace")
        except Exception:
            continue
        allowed = set(re.findall(r'"([^"]{20,})"', source.split("_ALLOWED_CLAIM_STATEMENTS")[1]
                                 .split(")")[0])) if "_ALLOWED_CLAIM_STATEMENTS" in source else set()
        allowed = {a for a in allowed if a.endswith(".")}
        forbidden = set(re.findall(r'"([a-z][a-z ]{4,})"',
                                   source.split("_FORBIDDEN_CLAIM_SUBSTRINGS")[1].split(")")[0])) \
            if "_FORBIDDEN_CLAIM_SUBSTRINGS" in source else set()
        if not allowed and not forbidden:
            continue
        return {
            "source": str(path.parent / "verification.py"),
            "allowedMismatch": sorted(allowed.symmetric_difference(set(CLAIMGUARD_ALLOWED))),
            "forbiddenMismatch": sorted(forbidden.symmetric_difference(set(CLAIMGUARD_FORBIDDEN))),
            "inSync": (not allowed.symmetric_difference(set(CLAIMGUARD_ALLOWED))
                       and not forbidden.symmetric_difference(set(CLAIMGUARD_FORBIDDEN))),
        }
    return None


def find_overclaims(text: str) -> List[str]:
    """CAPT's own overclaim rule, applied locally.

    This is the half of ClaimGuard that needs no runtime: statements containing a
    forbidden substring are overclaims 'unless independently proven (M0-B: never)'.
    Applying it to our own output is real truth-discipline, not decoration.
    """
    lowered = (text or "").lower()
    return [bad for bad in CLAIMGUARD_FORBIDDEN if bad in lowered]


def _mode_drift() -> Optional[Dict[str, Any]]:
    """Compare the pinned mode table against CAPT's canonical source.

    Returns None when there is nothing to compare or nothing disagrees. This is a
    REPORT, not a repair: silently rewriting our copy would hide the divergence,
    which is exactly the failure mode worth catching.
    """
    for path in CAPT_SOURCE_CANDIDATES:
        try:
            if not path.is_file():
                continue
            source = path.read_text(errors="replace")
        except Exception:
            continue
        found: Dict[str, str] = {}
        for mode in RESPONSE_MODES:
            m = re.search(
                r'"%s"\s*:\s*"([^"]+)"' % re.escape(mode), source
            )
            if m:
                found[mode] = m.group(1)
        if not found:
            continue
        mismatched = {
            mode: {"pinned": RESPONSE_MODES[mode], "capt": found[mode]}
            for mode in found
            if found[mode] != RESPONSE_MODES.get(mode)
        }
        return {
            "source": str(path),
            "modesCompared": len(found),
            "drift": mismatched,
            "inSync": not mismatched,
        }
    return None


# ---------------------------------------------------------------------------
# CAPT preference store (authoritative — read it, don't shadow it)
# ---------------------------------------------------------------------------

def read_preferences() -> Dict[str, Any]:
    """Read CAPT's own preference file, applying CAPT's validation defaults."""
    prefs: Dict[str, Any] = {
        "responseMode": DEFAULT_MODE,
        "contextBudget": 32_000,
        "humanVerificationRequired": True,
    }
    try:
        loaded = json.loads(CAPT_PREFS.read_text())
        if isinstance(loaded, dict):
            prefs.update(loaded)
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.debug("[capt-operator] preference read failed: %s", exc)

    # Mirror CAPT's PromptPreferences._validate()
    if prefs.get("responseMode") not in RESPONSE_MODES:
        prefs["responseMode"] = DEFAULT_MODE
    if prefs.get("contextBudget") not in CONTEXT_BUDGETS:
        prefs["contextBudget"] = 32_000
    prefs["humanVerificationRequired"] = bool(prefs.get("humanVerificationRequired", True))
    return prefs


def write_preferences(*, response_mode: str, context_budget: int,
                      human_verification_required: bool) -> Tuple[bool, str]:
    """Write CAPT's preference file in its own format. Fail closed on bad input."""
    if response_mode not in RESPONSE_MODES:
        return False, "RESPONSE_MODE_INVALID: %s (valid: %s)" % (
            response_mode, ", ".join(RESPONSE_MODES))
    if context_budget not in CONTEXT_BUDGETS:
        return False, "REQUESTED_CONTEXT_BUDGET_INVALID: %s (valid: %s)" % (
            context_budget, ", ".join(str(b) for b in CONTEXT_BUDGETS))
    payload = {
        "responseMode": response_mode,
        "contextBudget": int(context_budget),
        "humanVerificationRequired": bool(human_verification_required),
    }
    try:
        CAPT_PREFS.parent.mkdir(parents=True, exist_ok=True)
        CAPT_PREFS.write_text(json.dumps(payload, indent=2, sort_keys=True))
    except Exception as exc:
        return False, "PREFERENCE_WRITE_FAILED: %s" % exc
    return True, _mode_directive(response_mode)


def _mode_directive(mode: str) -> str:
    identity, order, text, source = GOVERNANCE_SECTION
    return (
        "[%s]\n%s\n\n[response-mode]\n%s"
        % (identity, text, RESPONSE_MODES.get(mode, RESPONSE_MODES[DEFAULT_MODE]))
    )


# ---------------------------------------------------------------------------
# CAPT runtime ledger — RuntimeService over the socket, never the database
# ---------------------------------------------------------------------------

class CaptUnavailable(RuntimeError):
    """Raised when the governed runtime is not reachable. Never faked."""


def _send_frame(sock: socket.socket, obj: Dict[str, Any]) -> None:
    blob = json.dumps(obj).encode()
    sock.sendall(struct.pack(">I", len(blob)) + blob)


def _recv_frame(sock: socket.socket) -> Optional[Dict[str, Any]]:
    header = b""
    while len(header) < 4:
        chunk = sock.recv(4 - len(header))
        if not chunk:
            return None
        header += chunk
    (length,) = struct.unpack(">I", header)
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(length - len(buf))
        if not chunk:
            return None
        buf += chunk
    return json.loads(buf)


def _connect(timeout: float = 6.0) -> Tuple[socket.socket, str, str]:
    """Authenticate to the CAPT runtime. The token is never logged or returned.

    Liveness is checked before connecting (socket present AND pid alive) so the
    failure reported is the real one rather than a connect timeout.
    """
    if not CAPT_SOCKET.exists():
        raise CaptUnavailable("CAPT runtime socket not present at %s" % CAPT_SOCKET)
    try:
        pid = int(CAPT_PID.read_text().strip())
        os.kill(pid, 0)
    except FileNotFoundError:
        raise CaptUnavailable("CAPT runtime pid file missing (%s)" % CAPT_PID)
    except (OSError, ValueError):
        raise CaptUnavailable("CAPT runtime pid dead or unreadable (%s)" % CAPT_PID)
    try:
        token = CAPT_TOKEN.read_text().strip()
    except Exception as exc:
        raise CaptUnavailable("CAPT runtime token unreadable: %s" % exc)
    if not token:
        raise CaptUnavailable("CAPT runtime token empty")

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(CAPT_SOCKET))
        _send_frame(sock, {"token": token})
        reply = _recv_frame(sock)
    except Exception as exc:
        sock.close()
        raise CaptUnavailable("CAPT runtime connect failed: %s" % exc)

    # The runtime answers the auth frame with a boolean `authenticated` flag.
    if not isinstance(reply, dict) or not reply.get("authenticated"):
        sock.close()
        raise CaptUnavailable(
            "CAPT runtime authentication rejected (stale token? runtime restarted?)")
    operator_id = str(reply.get("operatorId") or "")
    session_id = str(reply.get("sessionId") or "")
    if not operator_id or not session_id:
        sock.close()
        raise CaptUnavailable("CAPT runtime bound no operator/session identity")
    return sock, operator_id, session_id


def _query(sock: socket.socket, op: str, **extra: Any) -> Dict[str, Any]:
    _send_frame(sock, {"op": op, **extra})
    reply = _recv_frame(sock)
    return reply if isinstance(reply, dict) else {}


def _command(sock: socket.socket, operator_id: str, session_id: str, op: str,
             payload: Dict[str, Any]) -> Dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    envelope = {
        "commandId": "cmd-hermes-" + secrets.token_hex(6),
        "operatorId": operator_id,
        "sessionId": session_id,
        "schemaVersion": SCHEMA_VERSION,
        "correlationId": "corr-hermes-" + secrets.token_hex(4),
        "idempotencyKey": "idem-hermes-" + secrets.token_hex(6),
        "timestamp": now,
        "op": op,
        "payload": payload,
    }
    _send_frame(sock, {"op": "command", "command": envelope})
    reply = _recv_frame(sock)
    return reply if isinstance(reply, dict) else {}


def capt_status() -> Dict[str, Any]:
    """Identity, integrity and head from the governed runtime."""
    sock, op_id, sess_id = _connect()
    try:
        identity = _query(sock, "identity")
        res = identity.get("result", identity)
        policy = _query(sock, "get_memory_policy").get("result", {})
        status = {
            "runtime": "alive",
            "socket": str(CAPT_SOCKET),
            "headSequence": res.get("headSequence"),
            "integrity": res.get("integrity"),
            "ledgerPath": res.get("ledgerPath"),
            "chainDigest": res.get("ledgerChainDigest"),
            "policyVersion": policy.get("policyVersion"),
            "triggerIntervalTokens": policy.get("triggerIntervalTokens"),
        }
    finally:
        sock.close()
    prefs = read_preferences()
    status["responseMode"] = prefs["responseMode"]
    status["contextBudget"] = prefs["contextBudget"]
    status["humanVerificationRequired"] = prefs["humanVerificationRequired"]
    drift = _mode_drift()
    if drift:
        status["modeTable"] = drift
    return status


def capt_checkpoint(reason: str) -> Dict[str, Any]:
    """Write a governed checkpoint. One per milestone, not per tool call."""
    if not reason or not reason.strip():
        return {"status": "refused", "error": "checkpoint requires a reason"}
    sock, op_id, sess_id = _connect(timeout=10.0)
    try:
        reply = _command(sock, op_id, sess_id, "checkpoint_runtime",
                         {"reason": reason.strip()})
    finally:
        sock.close()
    status = str(reply.get("status") or "unknown")
    result = reply.get("result") or {}
    out = {
        "status": status,
        "checkpointId": result.get("checkpointId"),
        "accepted": status in {"accepted", "idempotent"},
    }
    if not out["accepted"]:
        out["error"] = str(reply)[:400]
    return out


def capt_recover(limit: int = 12) -> Dict[str, Any]:
    """Post-compaction digest: WHEN/THAT work happened, never WHAT.

    Checkpoint manifests and event payloads are enc:v1 at rest, so this returns
    pointers (ids, sequence, digests) by design. Human-readable state belongs in
    artifacts the checkpoint references.
    """
    sock, op_id, sess_id = _connect()
    try:
        identity = _query(sock, "identity")
        res = identity.get("result", identity)
        events = _query(sock, "event_timeline", limit=max(1, min(limit, 100)))
        items = events.get("result", events)
        if isinstance(items, dict):
            items = items.get("events", items.get("timeline", []))
        recent = [
            {
                "sequence": e.get("globalSequence") or e.get("seq"),
                "eventType": e.get("eventType") or e.get("event_type"),
                "streamId": e.get("streamId") or e.get("stream_id"),
            }
            for e in (items or [])[-limit:]
            if isinstance(e, dict)
        ]
    finally:
        sock.close()
    return {
        "headSequence": res.get("headSequence"),
        "integrity": res.get("integrity"),
        "chainDigest": res.get("ledgerChainDigest"),
        "recentEvents": recent,
        "note": "Payloads are enc:v1 at rest; this is a handle-based digest.",
    }


# ---------------------------------------------------------------------------
# Governed read surface — CAPT's own queries, exposed without reinterpretation
# ---------------------------------------------------------------------------

def capt_govern(action: str, *, statement: str = "", stream_id: str = "",
                limit: int = 20) -> Dict[str, Any]:
    """Read the governed runtime's own state. Read-only; never a command."""
    sock, op_id, sess_id = _connect()
    ops = {
        "capabilities": lambda: _query(sock, "capabilities"),
        "verification": lambda: _query(sock, "verification"),
        "memory_state": lambda: _query(sock, "get_memory_state"),
        "managed_skills": lambda: _query(sock, "managed_skills"),
        "mcp_servers": lambda: _query(sock, "mcp_servers"),
    }
    try:
        if action == "claimguard":
            if not statement.strip():
                return {"success": False,
                        "error": "claimguard requires a statement"}
            reply = _query(sock, "claimguard", statement=statement.strip())
            result = reply.get("result", reply)
            if isinstance(result, dict) and result.get("verdict"):
                # CAPT's own semantics, preserved exactly: a 'rejected' verdict means
                # the statement is not in the evidence-backed allowed set — it is NOT
                # a finding that the statement is false. 'advisory' means nothing was
                # committed. Reinterpreting this as "disproven" would invent authority
                # CAPT did not assert.
                return {
                    "success": True,
                    "statement": result.get("statement"),
                    "verdict": result.get("verdict"),
                    "reason": result.get("reason"),
                    "advisory": result.get("advisory"),
                    "committed": result.get("committed"),
                    "verdictMeans": ("rejected = not in the evidence-backed allowed set; "
                                     "it is not a finding that the claim is false"),
                }
            return {"success": False, "error": str(reply)[:300]}
        if action == "state":
            if not stream_id.strip():
                return {"success": False, "error": "state requires a stream_id"}
            reply = _query(sock, "get_state", streamId=stream_id.strip())
            return {"success": True, **(reply.get("result", reply) or {})}
        if action == "stream_events":
            if not stream_id.strip():
                return {"success": False, "error": "stream_events requires a stream_id"}
            reply = _query(sock, "get_stream_events",
                           streamId=stream_id.strip(), limit=max(1, min(limit, 200)))
            result = reply.get("result", reply)
            items = result if isinstance(result, list) else (result or {}).get("events", [])
            return {"success": True, "streamId": stream_id, "events": items[-limit:]}
        if action == "claim_vocabulary":
            return {
                "success": True,
                "allowed": sorted(CLAIMGUARD_ALLOWED),
                "forbidden": list(CLAIMGUARD_FORBIDDEN),
                "gate": ("The runtime accepts ONLY the allowed literals. Any other "
                         "statement is refused as 'not in the allowed set' — which is "
                         "NOT a finding that it is false. The forbidden substrings are "
                         "overclaims 'unless independently proven (M0-B: never)' and are "
                         "rejected locally without any runtime call."),
                "drift": _claim_vocabulary_drift(),
            }
        if action not in ops:
            return {"success": False,
                    "error": "unknown action %r (valid: %s)"
                             % (action, ", ".join(sorted(list(ops) + ["claimguard",
                                                                      "claim_vocabulary",
                                                                      "state",
                                                                      "stream_events"])))}
        reply = ops[action]()
        return {"success": True, **(reply.get("result", reply) or {})}
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# Verbosity measurement — evidence, not vibes
# ---------------------------------------------------------------------------

_VERBOSITY: Dict[str, Any] = {
    "turns": 0,
    "output_tokens": 0,
    "response_chars": 0,
    "transform_chars_saved": 0,
    "by_mode": {},
}


def _record_turn(mode: str, output_tokens: int, response_chars: int) -> None:
    _VERBOSITY["turns"] += 1
    _VERBOSITY["output_tokens"] += int(output_tokens or 0)
    _VERBOSITY["response_chars"] += int(response_chars or 0)
    bucket = _VERBOSITY["by_mode"].setdefault(mode, {"turns": 0, "output_tokens": 0})
    bucket["turns"] += 1
    bucket["output_tokens"] += int(output_tokens or 0)


# ---------------------------------------------------------------------------
# Conservative output transform
# ---------------------------------------------------------------------------

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_TRAILING_SIGNOFF = re.compile(
    r"\n+(?:Let me know if[^\n]*|I hope this helps[^\n]*|"
    r"Feel free to[^\n]*|Hope (?:this|that) helps[^\n]*)[.!]?\s*$",
    re.IGNORECASE,
)
_EXCESS_BLANK = re.compile(r"\n{4,}")


def _transform_for_mode(text: str, mode: str) -> Tuple[str, int]:
    """Apply a deliberately narrow transform. Returns (text, chars_saved).

    This intentionally does NOT summarise or delete content. Rewriting a
    substantive answer to hit a style target would trade information for
    cosmetics, and the directive in ``pre_llm_call`` is what actually shapes the
    response. What this does is remove padding a reader would not miss, and it
    never touches fenced code.
    """
    if mode not in ("MIN", "CAVE CAPT") or not text:
        return text, 0

    fences: List[str] = []

    def _stash(match: "re.Match[str]") -> str:
        fences.append(match.group(0))
        return "\x00FENCE%d\x00" % (len(fences) - 1)

    protected = _FENCE.sub(_stash, text)
    transformed = _EXCESS_BLANK.sub("\n\n\n", protected)
    transformed = _TRAILING_SIGNOFF.sub("", transformed)

    for index, block in enumerate(fences):
        transformed = transformed.replace("\x00FENCE%d\x00" % index, block)

    saved = len(text) - len(transformed)
    return (transformed, saved) if saved > 0 else (text, 0)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

MODE_TOOL_SCHEMA = {
    "name": "capt_mode",
    "description": (
        "Read or set the CAPT response mode that shapes how replies are presented. "
        "Modes: MAX, SPOCK, CAVE CAPT (plain language, concrete actions, no false "
        "certainty), MIN (work item, measurement, PASS/FAIL only). Reads and writes "
        "CAPT's own preference store, so the setting is shared with the CAPT cockpit."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": list(RESPONSE_MODES),
                "description": "Mode to set. Omit to read the current mode.",
            },
            "context_budget": {
                "type": "integer",
                "enum": list(CONTEXT_BUDGETS),
                "description": "Requested context budget in tokens (32K-256K). Optional.",
            },
        },
        "required": [],
    },
}

LEDGER_TOOL_SCHEMA = {
    "name": "capt_ledger",
    "description": (
        "Talk to the CAPT runtime ledger. action=status shows identity/integrity/head "
        "and the recorded policy; action=checkpoint logs a milestone (requires reason; "
        "one per milestone, not per tool call); action=recover returns a post-compaction "
        "digest of recent event types and ids. Never reports success it did not observe."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "checkpoint", "recover"]},
            "reason": {
                "type": "string",
                "description": "For checkpoint: what changed, why, and the artifact paths.",
            },
            "limit": {"type": "integer", "description": "For recover: events to list."},
        },
        "required": ["action"],
    },
}


GOVERN_TOOL_SCHEMA = {
    "name": "capt_govern",
    "description": (
        "Read the CAPT governed runtime's own state, or adjudicate a claim. "
        "action=capabilities lists every query and command op the runtime accepts; "
        "action=claimguard (requires statement) asks CAPT to adjudicate a claim "
        "against its evidence-backed allowed set — a 'rejected' verdict means the "
        "claim is NOT in that set, not that it is false; "
        "action=verification shows the mission verification state; "
        "action=memory_state, managed_skills, mcp_servers read the runtime's memory, "
        "skill pack and MCP client; action=state / stream_events take a stream_id. "
        "Read-only: this tool never issues a command."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["capabilities", "claimguard", "claim_vocabulary", "verification",
                         "memory_state", "managed_skills", "mcp_servers", "state",
                         "stream_events"],
            },
            "statement": {"type": "string",
                          "description": "For claimguard: the claim to adjudicate."},
            "stream_id": {"type": "string",
                          "description": "For state / stream_events: the stream to read."},
            "limit": {"type": "integer", "description": "For stream_events: max events."},
        },
        "required": ["action"],
    },
}


def handle_capt_govern(args: Dict[str, Any], **kwargs: Any) -> str:
    try:
        result = capt_govern(
            str(args.get("action") or "").strip().lower(),
            statement=str(args.get("statement") or ""),
            stream_id=str(args.get("stream_id") or ""),
            limit=int(args.get("limit") or 20),
        )
        return json.dumps(result)
    except CaptUnavailable as exc:
        # Hard stop: report the exact reason. Never fabricate governed state.
        return json.dumps({"success": False, "capt": "unavailable", "error": str(exc)})
    except Exception as exc:
        return json.dumps({"success": False,
                           "error": "%s: %s" % (type(exc).__name__, exc)})


def handle_capt_mode(args: Dict[str, Any], **kwargs: Any) -> str:
    preds = read_preferences()
    mode = args.get("mode")
    budget = args.get("context_budget")

    if mode is None and budget is None:
        return json.dumps({
            "success": True,
            "responseMode": preds["responseMode"],
            "contextBudget": preds["contextBudget"],
            "humanVerificationRequired": preds["humanVerificationRequired"],
            "directive": RESPONSE_MODES[preds["responseMode"]],
            "modes": RESPONSE_MODES,
        })

    target = mode or preds["responseMode"]
    target_budget = int(budget) if budget is not None else preds["contextBudget"]
    ok, detail = write_preferences(
        response_mode=target,
        context_budget=target_budget,
        human_verification_required=preds["humanVerificationRequired"],
    )
    if not ok:
        return json.dumps({"success": False, "error": detail})
    return json.dumps({
        "success": True,
        "responseMode": target,
        "contextBudget": target_budget,
        "directive": RESPONSE_MODES[target],
        "note": "Applies from the next turn; CAPT cockpit shares this setting.",
    })


def handle_capt_ledger(args: Dict[str, Any], **kwargs: Any) -> str:
    action = str(args.get("action") or "").strip().lower()
    try:
        if action == "status":
            return json.dumps({"success": True, **capt_status()})
        if action == "checkpoint":
            result = capt_checkpoint(str(args.get("reason") or ""))
            return json.dumps({"success": bool(result.get("accepted")), **result})
        if action == "recover":
            limit = int(args.get("limit") or 12)
            return json.dumps({"success": True, **capt_recover(limit)})
        return json.dumps({"success": False, "error": "unknown action: %s" % action})
    except CaptUnavailable as exc:
        # Hard stop: report unavailability with the exact reason. Never fake it.
        return json.dumps({"success": False, "capt": "unavailable", "error": str(exc)})
    except Exception as exc:
        return json.dumps({"success": False, "error": "%s: %s" % (type(exc).__name__, exc)})


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

def on_session_start(**kwargs: Any) -> None:
    """Record the mode frozen into this session's prompt, then report readiness.

    The framing itself is delivered by the registered system-prompt section. This
    hook records which mode that was, so a later mid-session change can be told
    apart from the frozen baseline.
    """
    try:
        session_id = str(kwargs.get("session_id") or "")
        mode = read_preferences()["responseMode"]
        if session_id:
            _FRAMING_FROZEN[session_id] = mode
    except Exception as exc:
        logger.debug("[capt-operator] session-start bookkeeping skipped: %s", exc)
        mode = "?"

    drift = _mode_drift()
    logger.info(
        "[capt-operator] ready mode=%s budget=%s socket=%s drift=%s",
        mode, read_preferences()["contextBudget"], CAPT_SOCKET.exists(),
        (drift or {}).get("inSync", "unchecked"),
    )


def on_pre_llm_call(**kwargs: Any) -> Optional[Dict[str, str]]:
    """Inject ONLY a mid-session mode change.

    The baseline framing is already in the session prompt (registered as a
    system-prompt section), so when the mode is unchanged this returns None and
    costs nothing. It speaks only when the operator changed the mode after the
    session opened, which the frozen prompt cannot know about.
    """
    try:
        session_id = str(kwargs.get("session_id") or "")
        mode = read_preferences()["responseMode"]
        frozen = _FRAMING_FROZEN.get(session_id)

        if frozen == mode:
            return None

        now = time.time()
        last_at = _LAST_INJECTED.get(session_id, ("", 0.0))[1]
        if (now - last_at) < _MODE_STEP * 60:
            return None
        _LAST_INJECTED[session_id] = (mode, now)

        return {"context": (
            "[response-mode-changed]\n"
            "The operator changed the CAPT response mode this session. It was %s "
            "at session start and is now %s.\n\n%s"
            % (frozen or "unspecified", mode, RESPONSE_MODES[mode])
        )}
    except Exception as exc:  # never let a plugin break a turn
        logger.debug("[capt-operator] pre_llm_call skipped: %s", exc)
        return None


def transform_llm_output(**kwargs: Any) -> Optional[str]:
    """Enforce the response mode on the final text (first string wins)."""
    try:
        text = kwargs.get("response_text")
        if not isinstance(text, str) or not text:
            return None
        mode = read_preferences()["responseMode"]
        transformed, saved = _transform_for_mode(text, mode)
        if saved > 0:
            _VERBOSITY["transform_chars_saved"] += saved
            logger.debug("[capt-operator] mode=%s trimmed %d chars", mode, saved)
            return transformed
        return None
    except Exception as exc:
        logger.debug("[capt-operator] transform skipped: %s", exc)
        return None


def post_api_request(**kwargs: Any) -> None:
    """Record real output volume per mode — the verbosity claim, measured."""
    try:
        usage = kwargs.get("usage") or {}
        mode = read_preferences()["responseMode"]
        _record_turn(
            mode,
            int(usage.get("output_tokens") or 0),
            int(kwargs.get("assistant_content_chars") or 0),
        )
    except Exception:
        return None


_COMPLETION_CLAIM = re.compile(
    r"\b((?:all\s+)?\d*\s*tests?\s+(?:pass|passed|are\s+passing)|"
    r"tests?\s+pass|verified|fully\s+verified|production[- ]ready|it\s+works)\b",
    re.IGNORECASE,
)
_CLAIMGUARD_LOG: List[Dict[str, Any]] = []
_OVERCLAIMS_FLAGGED: List[Dict[str, Any]] = []


def _extract_completion_claims(text: str, limit: int = 2) -> List[str]:
    """Pull the sentence around an explicit completion/verification assertion."""
    found: List[str] = []
    for match in _COMPLETION_CLAIM.finditer(text or ""):
        start = text.rfind(".", 0, match.start()) + 1
        end = text.find(".", match.end())
        sentence = text[start:end if end != -1 else len(text)].strip()
        if sentence and sentence not in found:
            found.append(sentence[:300])
        if len(found) >= limit:
            break
    return found


def on_pre_verify(**kwargs: Any) -> None:
    """Apply ClaimGuard to the final response before Hermes' verification pass.

    Two halves, and they are emphatically not the same thing:

    1. The OVERCLAIM rule runs locally, always. CAPT rejects the forbidden
       substrings "unless independently proven (M0-B: never)" — and that check
       needs no runtime call, so it holds even when CAPT is unreachable. Applying
       it to our own wording is the whole point; it is the cheap, real half.

    2. The runtime gate is consulted ONLY for statements that are in CAPT's
       allowed set. It accepts five exact literals and refuses everything else, so
       sending it ordinary prose produces 'rejected' verdicts that mean nothing.
       A rejection is reported as "not in the allowed set" — never as "false".

    Observer only: this never blocks, edits or delays the response.
    """
    try:
        text = str(kwargs.get("final_response") or "")
        if not text:
            return None

        overclaims = find_overclaims(text)
        if overclaims:
            _OVERCLAIMS_FLAGGED.append({
                "substrings": overclaims,
                "response_chars": len(text),
                "attempt": kwargs.get("attempt"),
            })
            logger.warning(
                "[capt-operator] response uses CAPT-forbidden overclaim vocabulary: %s",
                ", ".join(overclaims))

        if not CAPT_SOCKET.exists():
            return None

        # Two ways a statement can be worth putting to the gate: it carries
        # completion phrasing, or it is one of the allowed literals verbatim. The
        # second is the ONLY way the gate can ever accept, so a literal present in
        # the response is exactly what should be adjudicated.
        candidates = set(_extract_completion_claims(text))
        candidates.update(lit for lit in CLAIMGUARD_ALLOWED if lit in text)

        for statement in sorted(candidates):
            if statement.strip() not in CLAIMGUARD_ALLOWED:
                # Not in the allowed set: asking would only generate a rejection
                # that says nothing about truth.
                continue
            verdict = capt_govern("claimguard", statement=statement.strip())
            _CLAIMGUARD_LOG.append({
                "claim": statement.strip(),
                "verdict": verdict.get("verdict"),
                "advisory": verdict.get("advisory"),
                "success": verdict.get("success"),
            })
            logger.info("[capt-operator] claimguard verdict=%s claim=%r",
                        verdict.get("verdict"), statement.strip()[:90])
    except CaptUnavailable as exc:
        logger.debug("[capt-operator] pre_verify runtime half skipped: %s", exc)
    except Exception as exc:
        logger.debug("[capt-operator] pre_verify skipped: %s", exc)
    return None


def on_session_end(**kwargs: Any) -> None:
    """Log a governed checkpoint when a session ends with real work in it."""
    try:
        turns = _VERBOSITY.get("turns") or 0
        if turns < 2:
            return None
        capt_checkpoint(
            "Hermes session ended (%s) after %d turns; mode=%s; "
            "output_tokens=%s; transform_saved=%s chars"
            % (
                kwargs.get("session_id") or "unknown",
                turns,
                read_preferences()["responseMode"],
                _VERBOSITY["output_tokens"],
                _VERBOSITY["transform_chars_saved"],
            )
        )
    except CaptUnavailable as exc:
        logger.warning("[capt-operator] session-end checkpoint skipped: %s", exc)
    except Exception as exc:
        logger.debug("[capt-operator] session-end skipped: %s", exc)
    return None


def on_session_finalize(**kwargs: Any) -> None:
    return on_session_end(**kwargs)


# ---------------------------------------------------------------------------
# CLI — `hermes capt ...`
# ---------------------------------------------------------------------------

def _cli_setup(parser: Any) -> None:
    sub = parser.add_subparsers(dest="capt_action")
    sub.add_parser("status", help="Runtime identity, integrity, mode, drift")
    p_mode = sub.add_parser("mode", help="Show or set the response mode")
    p_mode.add_argument("value", nargs="?", choices=list(RESPONSE_MODES),
                        help="MAX | SPOCK | CAVE CAPT | MIN")
    p_mode.add_argument("--budget", type=int, choices=list(CONTEXT_BUDGETS))
    p_ck = sub.add_parser("checkpoint", help="Log a milestone to the ledger")
    p_ck.add_argument("reason", help="What changed, why, artifact paths")
    sub.add_parser("recover", help="Post-compaction digest from the ledger")
    sub.add_parser("capabilities", help="Every op the governed runtime accepts")
    sub.add_parser("verification", help="Mission verification state + claim verdicts")
    p_claim = sub.add_parser("claim", help="Ask CAPT to adjudicate a claim")
    p_claim.add_argument("statement", help="The claim to adjudicate")
    sub.add_parser("skills", help="The CAPT managed skill pack")
    sub.add_parser("mcp", help="The CAPT MCP client's servers")
    parser.set_defaults(capt_action="status")


def _cli_handler(args: Any) -> int:
    action = getattr(args, "capt_action", "status") or "status"
    try:
        if action == "status":
            status = capt_status()
            print("runtime       : %s" % status["runtime"])
            print("head          : %s" % status.get("headSequence"))
            print("integrity     : %s" % status.get("integrity"))
            print("chain         : %s" % str(status.get("chainDigest"))[:32])
            print("mode          : %s" % status.get("responseMode"))
            print("budget        : %s" % status.get("contextBudget"))
            table = status.get("modeTable")
            if table:
                verdict = "in sync" if table["inSync"] else "DRIFT"
                print("mode table    : %s vs %s" % (verdict, table["source"]))
                for mode, delta in (table.get("drift") or {}).items():
                    print("   %s:" % mode)
                    print("     pinned: %s" % delta["pinned"])
                    print("     capt  : %s" % delta["capt"])
            else:
                print("mode table    : not checked (CAPT source not found)")
            print("directive     : %s" % RESPONSE_MODES[status["responseMode"]])
            if _VERBOSITY["turns"]:
                print("this process  : %d turns, %d output tokens, %d chars trimmed"
                      % (_VERBOSITY["turns"], _VERBOSITY["output_tokens"],
                         _VERBOSITY["transform_chars_saved"]))
            return 0

        if action == "mode":
            value = getattr(args, "value", None)
            budget = getattr(args, "budget", None)
            payload = json.loads(handle_capt_mode(
                {"mode": value, "context_budget": budget}, ))
            if not payload.get("success"):
                print("refused: %s" % payload.get("error"))
                return 1
            print("mode    : %s" % payload["responseMode"])
            print("budget  : %s" % payload["contextBudget"])
            print("directive: %s" % payload["directive"])
            return 0

        if action == "checkpoint":
            result = capt_checkpoint(getattr(args, "reason", ""))
            if result.get("accepted"):
                print("accepted  checkpointId=%s" % result.get("checkpointId"))
                return 0
            print("refused: %s" % result.get("error"))
            return 1

        if action == "recover":
            digest = capt_recover(12)
            print("head=%s integrity=%s" % (digest["headSequence"], digest["integrity"]))
            for event in digest["recentEvents"]:
                print("  %s | %s | %s" % (event["sequence"], event["eventType"],
                                          event["streamId"]))
            return 0

        if action == "capabilities":
            caps = capt_govern("capabilities")
            q = caps.get("queryOperations") or []
            c = caps.get("commandOperations") or []
            print("query ops (%d):" % len(q))
            for op in q:
                print("   %s" % op)
            print("command ops (%d):" % len(c))
            for op in c:
                print("   %s" % op)
            comps = caps.get("runtimeComponents") or {}
            live = [k for k, v in comps.items() if v]
            print("runtime components live (%d): %s" % (len(live), ", ".join(sorted(live))))
            return 0

        if action == "verification":
            v = capt_govern("verification")
            print("verification : %s" % json.dumps(v.get("status")))
            print("trust        : %s" % v.get("trust"))
            vocab = capt_govern("claim_vocabulary")
            drift = vocab.get("drift") or {}
            print("claim gate   : %d allowed literals, %d forbidden substrings (%s)"
                  % (len(vocab["allowed"]), len(vocab["forbidden"]),
                     "in sync" if drift.get("inSync") else "DRIFT/unchecked"))
            if _OVERCLAIMS_FLAGGED:
                print("overclaims   : %d response(s) used CAPT-forbidden wording"
                      % len(_OVERCLAIMS_FLAGGED))
                for entry in _OVERCLAIMS_FLAGGED[-5:]:
                    print("   %s" % ", ".join(entry["substrings"]))
            else:
                print("overclaims   : none flagged this process")
            if _CLAIMGUARD_LOG:
                print("adjudicated  : %d statement(s) put to the runtime gate"
                      % len(_CLAIMGUARD_LOG))
                for entry in _CLAIMGUARD_LOG[-5:]:
                    print("   %-9s %s" % (entry.get("verdict"), (entry.get("claim") or "")[:64]))
            return 0

        if action == "claim":
            v = capt_govern("claimguard", statement=getattr(args, "statement", ""))
            if not v.get("success"):
                print("refused: %s" % v.get("error"))
                return 1
            print("claim   : %s" % v.get("statement"))
            print("verdict : %s" % v.get("verdict"))
            print("reason  : %s" % v.get("reason"))
            print("advisory: %s  committed: %s" % (v.get("advisory"), v.get("committed")))
            print("note    : %s" % v.get("verdictMeans"))
            return 0

        if action == "skills":
            s = capt_govern("managed_skills")
            print("pack    : %s@%s (%s)" % (s.get("packName"), s.get("packVersion"),
                                           s.get("trust")))
            print("root    : %s" % s.get("packRoot"))
            print("digest  : %s" % str(s.get("manifestDigest"))[:40])
            skills = s.get("skills") or []
            print("skills  : %d" % len(skills))
            for skill in skills[:20]:
                print("   %-28s %s" % (skill.get("name"), str(skill.get("version"))))
            if len(skills) > 20:
                print("   ... +%d more" % (len(skills) - 20))
            return 0

        if action == "mcp":
            servers = capt_govern("mcp_servers").get("servers") or []
            print("config  : %s" % capt_govern("mcp_servers").get("configPath"))
            for srv in servers:
                print("   %-10s %-12s tools=%-3s %s" % (
                    srv.get("serverId"), srv.get("status"), srv.get("toolCount"),
                    str(srv.get("transport"))))
                if srv.get("status") != "available":
                    print("       reason: %s" % str(srv.get("reason"))[:110])
            return 0
    except CaptUnavailable as exc:
        print("CAPT unavailable: %s" % exc)
        print("falling back to local sources is required; nothing was logged.")
        return 2
    except Exception as exc:
        print("error: %s: %s" % (type(exc).__name__, exc))
        return 1
    return 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(ctx: Any) -> None:
    """Plugin entry point."""
    always = lambda: True

    ctx.register_tool(
        name="capt_mode", toolset="capt", schema=MODE_TOOL_SCHEMA,
        handler=handle_capt_mode, check_fn=always, emoji="🏛",
    )
    ctx.register_tool(
        name="capt_ledger", toolset="capt", schema=LEDGER_TOOL_SCHEMA,
        handler=handle_capt_ledger, check_fn=always, emoji="🧾",
    )
    ctx.register_tool(
        name="capt_govern", toolset="capt", schema=GOVERN_TOOL_SCHEMA,
        handler=handle_capt_govern, check_fn=always, emoji="⚖",
    )

    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("transform_llm_output", transform_llm_output)
    ctx.register_hook("post_api_request", post_api_request)
    ctx.register_hook("pre_verify", on_pre_verify)
    ctx.register_hook("on_session_end", on_session_end)
    ctx.register_hook("on_session_finalize", on_session_finalize)

    try:
        ctx.register_system_prompt_section(
            _SYSTEM_PROMPT_SECTION_ID,
            _framing_section_content,
            position="after_memory",
            max_chars=_SYSTEM_PROMPT_SECTION_MAX_CHARS,
        )
    except Exception as exc:
        # Registration is a real capability, not decoration: if it fails we say so
        # rather than quietly falling back to no framing at all.
        logger.warning("[capt-operator] system prompt section NOT registered: %s", exc)

    try:
        ctx.register_cli_command(
            name="capt",
            help="CAPT operator surface (status, mode, checkpoint, recover)",
            setup_fn=_cli_setup,
            handler_fn=_cli_handler,
            description="Inspect the CAPT runtime and control response governance.",
        )
    except Exception as exc:
        logger.debug("[capt-operator] CLI registration skipped: %s", exc)

    logger.info(
        "[capt-operator] registered 2 tools, 6 hooks, 1 CLI command, 1 prompt section")
