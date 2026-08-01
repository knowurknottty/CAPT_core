"""Bootstrap bridge contracts — boot states, READY event, machine-readable result.

This module defines the wire/return shapes for the CAPT Bootstrap Bridge. It
contains **no** memory retrieval, ContextPack construction, MemoryUseGate, CTP,
KHSB, checkpoint, or provider logic; all of those remain inside canonical CAPT
(``capt_solo.agent.boot`` / ``capt_solo.runtime``). The bridge is a launcher and
an authority gate, not a second runtime.

Security notes:

* ``BridgeReadyEvent.bridge_nonce`` is a launch-scoped shared secret. It is
  compared with ``hmac.compare_digest`` and is redacted from every serialisation
  produced by this module (see ``BridgeReadyEvent.redacted_dict``).
* No field here may carry a credential. ``redacted_dict`` is the only shape that
  may be written to evidence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# boot states (workflow-mandated, exhaustive)
# ---------------------------------------------------------------------------
BOOT_STATE_FULL = "FULL_CAPT_AGENT_RUNNER_ACTIVE"
BOOT_STATE_PARTIAL = "CAPT_RUNNER_PARTIALLY_ACTIVE"
BOOT_STATE_SKILL_ONLY = "SKILL_LOADED_CAPT_RUNNER_NOT_ACTIVE"
BOOT_STATE_UNAVAILABLE = "CAPT_UNAVAILABLE"

BOOT_STATES: Tuple[str, ...] = (
    BOOT_STATE_FULL,
    BOOT_STATE_PARTIAL,
    BOOT_STATE_SKILL_ONLY,
    BOOT_STATE_UNAVAILABLE,
)

# ---------------------------------------------------------------------------
# provider ownership invariant: EXACTLY_ONE_PROVIDER_OWNER
# ---------------------------------------------------------------------------
OWNER_HERMES_BEFORE_BRIDGE = "HERMES_BEFORE_BRIDGE"
OWNER_CAPT_AFTER_READY = "CAPT_AGENT_RUNNER_AFTER_READY"
OWNER_NONE_WHEN_BLOCKED = "NONE_WHEN_BLOCKED"

PROVIDER_OWNERS: Tuple[str, ...] = (
    OWNER_HERMES_BEFORE_BRIDGE,
    OWNER_CAPT_AFTER_READY,
    OWNER_NONE_WHEN_BLOCKED,
)

# The only legal transitions. Any other pair is an invariant violation.
_LEGAL_TRANSITIONS: frozenset = frozenset(
    {
        (OWNER_HERMES_BEFORE_BRIDGE, OWNER_CAPT_AFTER_READY),
        (OWNER_HERMES_BEFORE_BRIDGE, OWNER_NONE_WHEN_BLOCKED),
        (OWNER_CAPT_AFTER_READY, OWNER_NONE_WHEN_BLOCKED),
        (OWNER_NONE_WHEN_BLOCKED, OWNER_CAPT_AFTER_READY),
        # Return to Hermes requires explicit owner authorization; the state
        # machine permits the edge only when the authorization flag is set, which
        # is enforced by ProviderOwnership.transition (not by this table alone).
        (OWNER_NONE_WHEN_BLOCKED, OWNER_HERMES_BEFORE_BRIDGE),
        (OWNER_CAPT_AFTER_READY, OWNER_HERMES_BEFORE_BRIDGE),
    }
)

# ---------------------------------------------------------------------------
# block codes
# ---------------------------------------------------------------------------
BLOCK_CAPT_NOT_IMPORTABLE = "CAPT_NOT_IMPORTABLE"
BLOCK_CAPT_INCOMPLETE = "CAPT_SOURCE_INCOMPLETE"
BLOCK_ENTRYPOINT_MISSING = "CAPT_ENTRYPOINT_MISSING"
BLOCK_DOCTOR_FAILED = "CAPT_DOCTOR_FAILED"
BLOCK_MISSION_REQUIRED = "MISSION_REQUIRED"
BLOCK_RUNNER_START_FAILED = "RUNNER_START_FAILED"
BLOCK_RUNNER_TIMEOUT = "RUNNER_STARTUP_TIMEOUT"
BLOCK_RUNNER_DIED = "RUNNER_DIED"
BLOCK_DUPLICATE_RUNNER = "DUPLICATE_RUNNER"
BLOCK_READY_MALFORMED = "READY_EVENT_MALFORMED"
BLOCK_READY_UNAUTHENTICATED = "READY_EVENT_UNAUTHENTICATED"
BLOCK_READY_NOT_RECEIVED = "READY_EVENT_NOT_RECEIVED"
BLOCK_GATE_NOT_PASSED = "MEMORY_USE_GATE_NOT_PASSED"
BLOCK_NOT_GOVERNED = "EXECUTION_MODE_NOT_GOVERNED"
BLOCK_WORKSPACE_MISSING = "WORKSPACE_MISSING"
BLOCK_BRIDGE_INTERNAL_ERROR = "BRIDGE_INTERNAL_ERROR"

# Fields a READY event must carry. Absence of any one is fatal.
REQUIRED_READY_FIELDS: Tuple[str, ...] = (
    "run_id",
    "mission_id",
    "session_id",
    "intent_id",
    "checkpoint_id",
    "contextpack_digest",
    "memory_use_decision_id",
    "memory_use_gate",
    "ctp_transaction_id",
    "khsb_correlation_id",
    "provider_owner",
    "execution_mode",
)

_REDACTED = "<redacted>"


def canonical_digest(payload: Mapping[str, Any]) -> str:
    """Stable sha256 over a mapping, excluding the digest and the nonce."""
    body = {
        k: v
        for k, v in payload.items()
        if k not in ("event_digest", "bridge_nonce")
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


class ProviderOwnershipViolation(RuntimeError):
    """Raised only inside CAPT-side tests/CLI — never across the middleware seam."""


@dataclass
class BridgeReadyEvent:
    """Structured readiness proof emitted by the canonical CAPT Agent Runner.

    Constructed **only** from bytes received over the authenticated local runner
    channel. Never from model text, log scraping, or a hand-written file.
    """

    run_id: str = ""
    mission_id: str = ""
    session_id: str = ""
    intent_id: str = ""
    checkpoint_id: str = ""
    contextpack_digest: str = ""
    memory_use_decision_id: str = ""
    memory_use_gate: str = ""
    ctp_transaction_id: str = ""
    khsb_correlation_id: str = ""
    provider_owner: str = ""
    execution_mode: str = ""
    runner_pid: int = 0
    bridge_nonce: str = ""
    event_digest: str = ""

    # -- construction -------------------------------------------------------
    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "BridgeReadyEvent":
        known = {f for f in cls.__dataclass_fields__}  # noqa: SLF001
        return cls(**{k: v for k, v in data.items() if k in known})

    def with_digest(self) -> "BridgeReadyEvent":
        payload = asdict(self)
        object.__setattr__(self, "event_digest", canonical_digest(payload))
        return self

    # -- validation ---------------------------------------------------------
    def validate(
        self,
        *,
        expected_nonce: str,
        expected_mission_id: str = "",
        expected_pid: int = 0,
    ) -> Tuple[bool, Tuple[str, ...], str]:
        """Return ``(ok, block_codes, reason)``.

        Authentication precedes shape validation: an unauthenticated event is
        rejected without its contents being trusted for any purpose.
        """
        codes: list = []

        # 1. authentication — constant time, launch-scoped nonce
        if not expected_nonce or not self.bridge_nonce:
            codes.append(BLOCK_READY_UNAUTHENTICATED)
            return False, tuple(codes), "READY event carries no bridge nonce"
        if not hmac.compare_digest(str(self.bridge_nonce), str(expected_nonce)):
            codes.append(BLOCK_READY_UNAUTHENTICATED)
            return False, tuple(codes), "READY event nonce mismatch"

        # 2. emitting process must be the runner the bridge spawned
        if expected_pid and int(self.runner_pid or 0) != int(expected_pid):
            codes.append(BLOCK_READY_UNAUTHENTICATED)
            return (
                False,
                tuple(codes),
                f"READY event pid {self.runner_pid} != spawned runner {expected_pid}",
            )

        # 3. required fields
        missing = [f for f in REQUIRED_READY_FIELDS if not getattr(self, f, "")]
        if missing:
            codes.append(BLOCK_READY_MALFORMED)
            return False, tuple(codes), "READY event missing fields: " + ", ".join(missing)

        # 4. digest integrity
        recomputed = canonical_digest(asdict(self))
        if self.event_digest != recomputed:
            codes.append(BLOCK_READY_MALFORMED)
            return False, tuple(codes), "READY event digest mismatch"

        # 5. semantic requirements
        if expected_mission_id and self.mission_id != expected_mission_id:
            codes.append(BLOCK_READY_MALFORMED)
            return (
                False,
                tuple(codes),
                f"READY mission {self.mission_id!r} != requested {expected_mission_id!r}",
            )
        if self.memory_use_gate != "PASS":
            codes.append(BLOCK_GATE_NOT_PASSED)
        if self.provider_owner != "CAPT_AGENT_RUNNER":
            codes.append(BLOCK_READY_MALFORMED)
        if self.execution_mode != "GOVERNED":
            codes.append(BLOCK_NOT_GOVERNED)
        if codes:
            return False, tuple(codes), "READY event did not satisfy governed preconditions"
        return True, (), ""

    # -- serialisation (nonce never leaves) ---------------------------------
    def redacted_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        if out.get("bridge_nonce"):
            out["bridge_nonce"] = _REDACTED
        return out


@dataclass
class BridgeResult:
    """Machine-readable bridge outcome. This is the skill's entire interface."""

    boot_state: str = BOOT_STATE_UNAVAILABLE
    provider_owner: str = OWNER_NONE_WHEN_BLOCKED
    mission_id: str = ""
    session_id: str = ""
    checkpoint_id: str = ""
    intent_id: str = ""
    contextpack_digest: str = ""
    memory_use_decision_id: str = ""
    memory_use_gate: str = ""
    ctp_transaction_id: str = ""
    khsb_correlation_id: str = ""
    execution_mode: str = ""
    workspace_path: str = ""
    capt_source_path: str = ""
    runner_command: Tuple[str, ...] = ()
    runner_pid: int = 0
    doctor_ok: bool = False
    block_codes: Tuple[str, ...] = ()
    block_reason: str = ""
    degraded_controls: Tuple[str, ...] = ()
    ready_event: Optional[BridgeReadyEvent] = None
    notes: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def provider_allowed(self) -> bool:
        """True only in the fully governed state. Everything else blocks."""
        return (
            self.boot_state == BOOT_STATE_FULL
            and self.provider_owner == OWNER_CAPT_AFTER_READY
            and self.memory_use_gate == "PASS"
            and self.execution_mode == "GOVERNED"
        )

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["runner_command"] = list(self.runner_command)
        out["block_codes"] = list(self.block_codes)
        out["degraded_controls"] = list(self.degraded_controls)
        out["notes"] = list(self.notes)
        out["provider_allowed"] = self.provider_allowed
        out["ready_event"] = self.ready_event.redacted_dict() if self.ready_event else None
        return out

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)


def blocked(
    reason: str,
    codes: Tuple[str, ...],
    *,
    boot_state: str = BOOT_STATE_UNAVAILABLE,
    **kw: Any,
) -> BridgeResult:
    """Construct a fail-closed result. The only way the bridge reports failure."""
    return BridgeResult(
        boot_state=boot_state,
        provider_owner=OWNER_NONE_WHEN_BLOCKED,
        block_reason=reason,
        block_codes=codes,
        **kw,
    )


class ProviderOwnership:
    """Runtime invariant EXACTLY_ONE_PROVIDER_OWNER.

    Enforces that at most one owner holds provider authority and that a return to
    Hermes-native execution after a CAPT transfer requires explicit owner
    authorization. There is no silent fallback edge.
    """

    def __init__(self, owner: str = OWNER_HERMES_BEFORE_BRIDGE) -> None:
        if owner not in PROVIDER_OWNERS:
            raise ProviderOwnershipViolation(f"unknown provider owner: {owner!r}")
        self._owner = owner
        self._history: list = [owner]

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def history(self) -> Tuple[str, ...]:
        return tuple(self._history)

    def transition(self, new_owner: str, *, owner_authorized: bool = False) -> None:
        if new_owner not in PROVIDER_OWNERS:
            raise ProviderOwnershipViolation(f"unknown provider owner: {new_owner!r}")
        if new_owner == self._owner:
            return
        if (self._owner, new_owner) not in _LEGAL_TRANSITIONS:
            raise ProviderOwnershipViolation(
                f"illegal provider-owner transition {self._owner} -> {new_owner}"
            )
        if new_owner == OWNER_HERMES_BEFORE_BRIDGE and not owner_authorized:
            raise ProviderOwnershipViolation(
                "returning provider authority to Hermes requires explicit owner "
                "authorization (no silent fallback)"
            )
        self._owner = new_owner
        self._history.append(new_owner)

    def assert_single_owner(self) -> None:
        if self._owner not in PROVIDER_OWNERS:
            raise ProviderOwnershipViolation("provider ownership is undefined")
