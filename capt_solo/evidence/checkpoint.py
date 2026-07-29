"""Mission Checkpointing and Restart Recovery.

Compact structured mission state (no verbose conversational history). On restart:
resolve identity -> load checkpoint -> compare to current repo state -> detect
divergence -> reuse valid evidence -> mark stale assumptions -> resume from first
incomplete safe action -> avoid replaying completed work.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from .workspace_isolation import ProjectWorkspace, BindState


class CheckpointStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    STALE = "stale"
    INTERRUPTED = "interrupted"


@dataclass
class MissionCheckpoint:
    mission_id: str
    project_id: str
    objective: str
    constraints: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    current_phase: str = "0"
    completed_work: List[str] = field(default_factory=list)
    pending_work: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    latest_verified_state: str = ""
    latest_evidence_state: str = ""
    unresolved_invalidations: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    decisions_made: List[str] = field(default_factory=list)
    next_safe_action: str = ""
    required_user_decisions: List[str] = field(default_factory=list)
    commit_references: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = CheckpointStatus.ACTIVE.value
    event_digest: str = ""

    def to_dict(self) -> Dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, d: Dict) -> "MissionCheckpoint":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class CheckpointStore:
    def __init__(self, root: str, *, create: bool = True) -> None:
        self._root = os.path.abspath(root)
        self._dir = os.path.join(self._root, ".capt", "checkpoints")
        if create:
            os.makedirs(self._dir, exist_ok=True)
        self._events_path = os.path.join(self._dir, "events.jsonl")

    @staticmethod
    def _digest(value: Dict) -> str:
        return "sha256:" + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _append_event(self, cp: MissionCheckpoint, event_type: str) -> Dict:
        if event_type not in {"created", "checkpoint", "completed", "rollback", "aborted", "resumed"}:
            raise ValueError("unsupported mission event: " + event_type)
        event = {"mission_id": cp.mission_id, "project_id": cp.project_id,
                 "event_type": event_type, "timestamp": cp.timestamp,
                 "status": cp.status, "phase": cp.current_phase,
                 "checkpoint_digest": cp.event_digest}
        event["event_digest"] = self._digest(event)
        with open(self._events_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def save(self, cp: MissionCheckpoint) -> str:
        os.makedirs(self._dir, exist_ok=True)
        path = os.path.join(self._dir, f"{cp.mission_id}.json")
        existed = os.path.exists(path)
        payload = cp.to_dict().copy(); payload.pop("event_digest", None)
        cp.event_digest = self._digest(payload)
        with open(path, "w") as f:
            json.dump(cp.to_dict(), f, indent=2)
        event_type = "created" if not existed else "checkpoint"
        if cp.status == CheckpointStatus.COMPLETED.value: event_type = "completed"
        if cp.status == CheckpointStatus.STALE.value: event_type = "rollback"
        if cp.status == CheckpointStatus.INTERRUPTED.value: event_type = "aborted"
        self._append_event(cp, event_type)
        return path

    def load(self, mission_id: str) -> Optional[MissionCheckpoint]:
        path = os.path.join(self._dir, f"{mission_id}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return MissionCheckpoint.from_dict(json.load(f))

    def list_ids(self) -> List[str]:
        if not os.path.isdir(self._dir): return []
        return sorted(f[:-5] for f in os.listdir(self._dir) if f.endswith(".json"))

    def events(self, mission_id: str = "") -> List[Dict]:
        if not os.path.exists(self._events_path): return []
        result = []
        with open(self._events_path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    event = json.loads(line)
                    if not mission_id or event.get("mission_id") == mission_id:
                        result.append(event)
        return result

    def record_event(self, mission_id: str, event_type: str) -> Dict:
        cp = self.load(mission_id)
        if cp is None: raise ValueError("checkpoint not found: " + mission_id)
        return self._append_event(cp, event_type)


def detect_divergence(cp: MissionCheckpoint, *,
                      current_head: str, current_branch: str,
                      current_files: List[str]) -> Dict[str, str]:
    """Compare checkpoint state to current repository state."""
    div: Dict[str, str] = {}
    if cp.latest_verified_state and current_head and cp.latest_verified_state != current_head:
        div["head"] = f"checkpoint head {cp.latest_verified_state[:8]} != current {current_head[:8]}"
    # file-level: any checkpoint file missing or extra
    cp_files = set(cp.files_changed)
    cur = set(current_files)
    missing = cp_files - cur
    extra = cur - cp_files
    if missing:
        div["missing_files"] = f"{len(missing)} checkpoint file(s) absent"
    if extra:
        div["extra_files"] = f"{len(extra)} untracked file(s) present"
    return div


def resume_plan(cp: MissionCheckpoint, divergence: Dict[str, str]) -> Dict:
    """Produce a resume decision: reuse valid evidence, mark stale, resume safely."""
    stale = bool(divergence)
    return {
        "status": "resume" if not stale else "resume_with_divergence",
        "reuse_evidence": not stale,
        "mark_stale_assumptions": list(divergence.keys()),
        "next_action": cp.next_safe_action if not cp.status == CheckpointStatus.COMPLETED.value
        else "DO_NOT_RESTART_COMPLETED_MISSION",
        "avoid_replay": cp.completed_work,
    }
