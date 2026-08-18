"""Strict, deterministic contracts for Inversion Labs advisory engines."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Dict, Mapping, Tuple

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_OPERATION_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,63}$")
_EPISTEMIC = frozenset({"calculation", "heuristic", "simulation", "advisory"})
MAX_LAB_INPUT_BYTES = 65536


class LabContractError(ValueError):
    """Raised before execution when a Lab request/result violates its contract."""


class LabInputError(LabContractError):
    """Raised when an engine-specific input is invalid."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        )
    except ValueError as exc:
        raise LabContractError("Lab JSON numbers must be finite") from exc
    except (TypeError, OverflowError) as exc:
        raise LabContractError("Lab payload must be JSON serializable") from exc
    return text.encode("utf-8")


def sha256_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_request_digest(value: Mapping[str, Any]) -> str:
    return sha256_digest(canonical_json_bytes(dict(value)))


def _require_identifier(name: str, value: Any) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_RE.fullmatch(value):
        raise LabContractError("%s must be a CAPT-safe identifier" % name)
    return value


def _require_operation(value: Any) -> str:
    if not isinstance(value, str) or not _OPERATION_RE.fullmatch(value):
        raise LabContractError("operation must be a lowercase bounded identifier")
    return value


@dataclass(frozen=True)
class LabEngineRequest:
    engine_id: str
    operation: str
    input: Dict[str, Any]
    mission_id: str
    task_id: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "LabEngineRequest":
        allowed = {"engineId", "operation", "input", "missionId", "taskId"}
        unknown = set(raw) - allowed
        missing = allowed - set(raw)
        if unknown:
            raise LabContractError("unknown field(s): %s" % ", ".join(sorted(unknown)))
        if missing:
            raise LabContractError("missing field(s): %s" % ", ".join(sorted(missing)))
        value = raw["input"]
        if not isinstance(value, dict):
            raise LabContractError("input must be an object")
        if len(canonical_json_bytes(value)) > MAX_LAB_INPUT_BYTES:
            raise LabContractError("input exceeds %d bytes" % MAX_LAB_INPUT_BYTES)
        return cls(
            engine_id=_require_identifier("engineId", raw["engineId"]),
            operation=_require_operation(raw["operation"]),
            input=dict(value),
            mission_id=_require_identifier("missionId", raw["missionId"]),
            task_id=_require_identifier("taskId", raw["taskId"]),
        )

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "engineId": self.engine_id,
            "operation": self.operation,
            "input": dict(self.input),
            "missionId": self.mission_id,
            "taskId": self.task_id,
        }

    @property
    def request_digest(self) -> str:
        return canonical_request_digest(self.to_mapping())


@dataclass(frozen=True)
class LabEngineResult:
    engine_id: str
    engine_version: str
    operation: str
    epistemic_class: str
    observation: Dict[str, Any]
    limitations: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_identifier("engineId", self.engine_id)
        _require_operation(self.operation)
        if self.epistemic_class not in _EPISTEMIC:
            raise LabContractError("unknown epistemic class %r" % self.epistemic_class)
        canonical_json_bytes(self.observation)
        for item in self.limitations:
            if not isinstance(item, str) or not item or len(item) > 2048:
                raise LabContractError("limitations must be non-empty strings <= 2048 chars")

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "engineId": self.engine_id,
            "engineVersion": self.engine_version,
            "operation": self.operation,
            "epistemicClass": self.epistemic_class,
            "observation": dict(self.observation),
            "limitations": list(self.limitations),
        }
