"""Canonical Replay (Layer 3).

Per Phase 3E, Replay is a bounded canonical capability. It supports deterministic
event replay where possible, dry-run mode, target-state reconstruction, replay
provenance, replay version, partial replay, failure reporting, cancellation, and
protection against duplicate side effects.

Safety: replay does NOT automatically re-execute unsafe external actions. It
defaults to *state reconstruction / simulation* unless an execution capability is
explicitly authorized. This prevents duplicate side effects (I-07 bounded failure).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ReplayMode(str, Enum):
    DRY_RUN = "dry_run"          # simulate only; no side effects
    RECONSTRUCT = "reconstruct"  # rebuild target state in memory
    EXECUTE = "execute"          # re-run events (requires explicit authorization)


class ReplayStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReplayEvent:
    event_id: str
    kind: str
    payload: Dict[str, Any]
    timestamp: float
    provenance: Optional[str] = None
    replay_version: int = 1
    side_effect: bool = False  # True => unsafe external action; never auto-executed


@dataclass
class ReplayResult:
    replay_id: str
    status: str
    mode: str
    events_replayed: int
    events_total: int
    reconstructed_state: Dict[str, Any] = field(default_factory=dict)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    cancelled_at: Optional[float] = None
    provenance: Dict[str, Any] = field(default_factory=dict)


class ReplayEngine:
    """Bounded canonical replay.

    ``apply_fn`` is an optional callable invoked per event in EXECUTE mode. It
    MUST be side-effect-safe or explicitly authorized. In DRY_RUN / RECONSTRUCT
    modes no external action occurs; only state reconstruction is performed.
    """

    def __init__(self) -> None:
        self._cancelled: Dict[str, bool] = {}

    def replay(
        self,
        events: List[ReplayEvent],
        *,
        mode: ReplayMode = ReplayMode.RECONSTRUCT,
        target_state: Optional[Dict[str, Any]] = None,
        apply_fn: Optional[Callable[[ReplayEvent], Any]] = None,
        authorize_execute: bool = False,
        partial: bool = False,
    ) -> ReplayResult:
        if mode == ReplayMode.EXECUTE and not authorize_execute:
            raise ValueError("EXECUTE mode requires explicit authorize_execute=True")
        replay_id = uuid.uuid4().hex
        self._cancelled[replay_id] = False
        state = dict(target_state or {})
        result = ReplayResult(
            replay_id=replay_id,
            status=ReplayStatus.RUNNING.value,
            mode=mode.value,
            events_replayed=0,
            events_total=len(events),
            provenance={
                "replay_version": 1,
                "mode": mode.value,
                "authorized": mode == ReplayMode.EXECUTE,
                "started_at": time.time(),
            },
        )
        for i, ev in enumerate(events):
            if self._cancelled.get(replay_id):
                result.status = ReplayStatus.CANCELLED.value
                result.cancelled_at = time.time()
                result.provenance["ended_at"] = result.cancelled_at
                return result
            # Safety refusal MUST propagate (not caught as bounded failure):
            # replay never auto-executes unsafe external side-effect events.
            if mode == ReplayMode.EXECUTE and ev.side_effect:
                raise RuntimeError(
                    f"refusing to auto-execute side-effect event {ev.event_id}; "
                    f"use a dedicated executor with explicit authorization")
            try:
                if mode in (ReplayMode.DRY_RUN, ReplayMode.RECONSTRUCT):
                    # state reconstruction only; never invoke external side effects
                    state[f"event_{ev.event_id}"] = ev.payload
                elif mode == ReplayMode.EXECUTE:
                    if apply_fn is not None:
                        apply_fn(ev)
                    state[f"event_{ev.event_id}"] = ev.payload
                result.events_replayed += 1
            except Exception as e:  # bounded failure; record, continue or stop
                result.failures.append({"event_id": ev.event_id, "error": str(e)})
                if not partial:
                    result.status = ReplayStatus.FAILED.value
                    result.provenance["ended_at"] = time.time()
                    return result
        result.reconstructed_state = state
        result.status = ReplayStatus.COMPLETED.value
        result.provenance["ended_at"] = time.time()
        return result

    def cancel(self, replay_id: str) -> None:
        self._cancelled[replay_id] = True

    def dry_run(self, events: List[ReplayEvent],
                target_state: Optional[Dict[str, Any]] = None) -> ReplayResult:
        return self.replay(events, mode=ReplayMode.DRY_RUN, target_state=target_state)
