"""Non-authoritative operator-control state for CAPT RuntimeService.

This document coordinates operator surfaces. It never substitutes for EventStore
approval, execution, evidence, verification, ClaimGuard, task, or mission state.
"""
from __future__ import annotations

import copy
import os
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from capt_runtime.contracts import canonical_json, digest

SCHEMA_VERSION = "1.0.0"
ALLOWED_PROMPT_INTELLIGENCE = frozenset(
    {"OFF", "AUTO", "OMNI", "META", "FORGE", "SIGMA"}
)


class OperatorControlStale(RuntimeError):
    def __init__(self, current_snapshot: dict[str, Any]) -> None:
        super().__init__("E_OPERATOR_CONTROL_STALE")
        self.current_snapshot = current_snapshot


ConfigValidator = Callable[[dict[str, str]], dict[str, str] | None]

class OperatorControlStore:
    def __init__(
        self,
        path: str | Path,
        defaults: dict[str, str],
        validate_configuration: ConfigValidator | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._validate_external = validate_configuration
        self._now = now or (
            lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        self._lock = threading.RLock()
        if self.path.exists():
            self._state = self._load()
        else:
            config = self._normalize_configuration(defaults)
            self._state = self._build_state(
                revision=0,
                configuration_revision=0,
                configuration=config,
                active_session_id=None,
                sessions={},
            )
            self._persist(self._state)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)
    def _normalize_configuration(self, raw: dict[str, str]) -> dict[str, str]:
        provider = str(raw.get("provider", "")).strip()
        model = str(raw.get("model", "")).strip()
        target_root = str(raw.get("targetRoot", "")).strip()
        prompt_intelligence = str(raw.get("promptIntelligence", "")).strip().upper()
        if not provider:
            raise ValueError("PROVIDER_MISSING")
        if not model:
            raise ValueError("MODEL_MISSING")
        if prompt_intelligence not in ALLOWED_PROMPT_INTELLIGENCE:
            raise ValueError("PROMPT_INTELLIGENCE_INVALID")
        normalized_target = ""
        if target_root:
            root = Path(target_root).expanduser().resolve(strict=False)
            if not root.exists() or not root.is_dir():
                raise ValueError("TARGET_ROOT_NOT_DIRECTORY")
            normalized_target = str(root)
        config = {
            "provider": provider,
            "model": model,
            "targetRoot": normalized_target,
            "promptIntelligence": prompt_intelligence,
        }
        if self._validate_external is not None:
            validated = self._validate_external(dict(config))
            if validated is not None:
                config = validated
        return config

    @staticmethod
    def _configuration_digest(config: dict[str, str]) -> str:
        return digest({key: config[key] for key in (
            "provider", "model", "targetRoot", "promptIntelligence"
        )})
    def _build_state(
        self,
        *,
        revision: int,
        configuration_revision: int,
        configuration: dict[str, str],
        active_session_id: str | None,
        sessions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        active = sessions.get(active_session_id, {}) if active_session_id else {}
        cursors = {
            key: active.get(key)
            for key in (
                "proposalId", "proposalRevision", "proposalSelection",
                "approvalRequestId", "missionId", "taskId", "driverRunId", "claimId",
            )
        }
        return {
            "schemaVersion": SCHEMA_VERSION,
            "revision": revision,
            "updatedAt": self._now(),
            "activeSessionId": active_session_id,
            "configurationRevision": configuration_revision,
            "configurationDigest": self._configuration_digest(configuration),
            **configuration,
            **cursors,
            "sessions": sessions,
        }

    def _load(self) -> dict[str, Any]:
        import json

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("schemaVersion") != SCHEMA_VERSION:
            raise ValueError("OPERATOR_CONTROL_SCHEMA_INVALID")
        config = self._normalize_configuration(raw)
        if raw.get("configurationDigest") != self._configuration_digest(config):
            raise ValueError("OPERATOR_CONTROL_DIGEST_INVALID")
        os.chmod(self.path, 0o600)
        return raw

    def _persist(self, state: dict[str, Any]) -> None:
        tmp = self.path.with_name(
            ".%s.%s.tmp" % (self.path.name, uuid.uuid4().hex)
        )
        data = canonical_json(state).encode("utf-8")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, "wb", closefd=True) as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise
            os.replace(tmp, self.path)
            os.chmod(self.path, 0o600)
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            if tmp.exists():
                tmp.unlink()

    def _require_revision(self, expected_revision: int) -> None:
        if expected_revision != int(self._state["revision"]):
            raise OperatorControlStale(self.snapshot())

    def _current_configuration(self) -> dict[str, str]:
        return {
            key: str(self._state[key])
            for key in ("provider", "model", "targetRoot", "promptIntelligence")
        }
    def set_configuration(
        self,
        *,
        expected_revision: int,
        provider: str | None = None,
        model: str | None = None,
        target_root: str | None = None,
        prompt_intelligence: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._require_revision(expected_revision)
            current = self._current_configuration()
            candidate = dict(current)
            updates = {
                "provider": provider,
                "model": model,
                "targetRoot": target_root,
                "promptIntelligence": prompt_intelligence,
            }
            for key, value in updates.items():
                if value is not None:
                    candidate[key] = value
            candidate = self._normalize_configuration(candidate)
            changed = candidate != current
            config_revision = int(self._state["configurationRevision"]) + (1 if changed else 0)
            sessions = copy.deepcopy(self._state.get("sessions", {}))
            active = self._state.get("activeSessionId")
            if active and active in sessions and changed:
                session = sessions[active]
                session.update(candidate)
                session["configurationRevision"] = config_revision
                session["configurationDigest"] = self._configuration_digest(candidate)
                for key in (
                    "proposalId", "proposalRevision", "proposalSelection",
                    "approvalRequestId", "missionId", "taskId", "driverRunId", "claimId",
                ):
                    session[key] = None
            next_state = self._build_state(
                revision=int(self._state["revision"]) + 1,
                configuration_revision=config_revision,
                configuration=candidate,
                active_session_id=active,
                sessions=sessions,
            )
            self._persist(next_state)
            self._state = next_state
            return self.snapshot()
    def new_chat(
        self,
        *,
        expected_revision: int,
        provider: str | None = None,
        model: str | None = None,
        target_root: str | None = None,
        prompt_intelligence: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._require_revision(expected_revision)
            current = self._current_configuration()
            candidate = dict(current)
            overrides = {
                "provider": provider,
                "model": model,
                "targetRoot": target_root,
                "promptIntelligence": prompt_intelligence,
            }
            for key, value in overrides.items():
                if value is not None:
                    candidate[key] = value
            candidate = self._normalize_configuration(candidate)
            changed = candidate != current
            config_revision = int(self._state["configurationRevision"]) + (1 if changed else 0)
            session_id = "opchat-" + uuid.uuid4().hex[:24]
            sessions = copy.deepcopy(self._state.get("sessions", {}))
            sessions[session_id] = {
                "sessionId": session_id,
                "createdAt": self._now(),
                "configurationRevision": config_revision,
                "configurationDigest": self._configuration_digest(candidate),
                **candidate,
                "proposalId": None,
                "proposalRevision": None,
                "proposalSelection": None,
                "approvalRequestId": None,
                "missionId": None,
                "taskId": None,
                "driverRunId": None,
                "claimId": None,
            }
            next_state = self._build_state(
                revision=int(self._state["revision"]) + 1,
                configuration_revision=config_revision,
                configuration=candidate,
                active_session_id=session_id,
                sessions=sessions,
            )
            self._persist(next_state)
            self._state = next_state
            return self.snapshot()

    def session_get(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            session = self._state.get("sessions", {}).get(session_id)
            return copy.deepcopy(session) if session is not None else None

    def require_current(
        self, *, expected_revision: int, configuration_digest: str | None = None
    ) -> dict[str, Any]:
        with self._lock:
            self._require_revision(expected_revision)
            if (
                configuration_digest is not None
                and configuration_digest != self._state["configurationDigest"]
            ):
                raise OperatorControlStale(self.snapshot())
            if not self._state.get("activeSessionId"):
                raise ValueError("OPERATOR_CONTROL_SESSION_REQUIRED")
            return self.snapshot()

    def _update_active_session(
        self, expected_revision: int, updates: dict[str, Any]
    ) -> dict[str, Any]:
        self._require_revision(expected_revision)
        active = self._state.get("activeSessionId")
        if not active:
            raise ValueError("OPERATOR_CONTROL_SESSION_REQUIRED")
        sessions = copy.deepcopy(self._state.get("sessions", {}))
        session = sessions.get(active)
        if session is None:
            raise ValueError("OPERATOR_CONTROL_SESSION_UNKNOWN")
        session.update(updates)
        next_state = self._build_state(
            revision=int(self._state["revision"]) + 1,
            configuration_revision=int(self._state["configurationRevision"]),
            configuration=self._current_configuration(),
            active_session_id=active,
            sessions=sessions,
        )
        self._persist(next_state)
        self._state = next_state
        return self.snapshot()
    def bind_proposal(
        self,
        *,
        expected_revision: int,
        configuration_digest: str,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            self.require_current(
                expected_revision=expected_revision,
                configuration_digest=configuration_digest,
            )
            if proposal.get("targetRoot") != self._state["targetRoot"]:
                raise ValueError("OPERATOR_CONTROL_PROPOSAL_ROOT_MISMATCH")
            if (proposal.get("provider") or "") != self._state["provider"]:
                raise ValueError("OPERATOR_CONTROL_PROPOSAL_PROVIDER_MISMATCH")
            if (proposal.get("model") or "") != self._state["model"]:
                raise ValueError("OPERATOR_CONTROL_PROPOSAL_MODEL_MISMATCH")
            if self._state["promptIntelligence"] == "OFF":
                if proposal.get("stageChain") or proposal.get("stageRecords"):
                    raise ValueError("OPERATOR_CONTROL_PROPOSAL_PI_MISMATCH")
            return self._update_active_session(expected_revision, {
                "proposalId": proposal.get("proposalId"),
                "proposalRevision": proposal.get("revision"),
                "proposalSelection": None,
                "approvalRequestId": None,
                "missionId": None,
                "taskId": None,
                "driverRunId": None,
                "claimId": None,
            })

    def bind_approval(
        self,
        *,
        expected_revision: int,
        configuration_digest: str,
        proposal_id: str,
        selection: str,
        approval: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            current = self.require_current(
                expected_revision=expected_revision,
                configuration_digest=configuration_digest,
            )
            if current.get("proposalId") != proposal_id:
                raise OperatorControlStale(current)
            return self._update_active_session(expected_revision, {
                "proposalSelection": selection,
                "approvalRequestId": approval.get("requestId"),
                "missionId": approval.get("missionId"),
                "taskId": approval.get("taskId"),
                "driverRunId": approval.get("driverRunId"),
            })