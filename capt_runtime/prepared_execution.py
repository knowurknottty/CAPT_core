"""Immutable prepared boundary for approved model execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class FrozenDict(dict):
    """A JSON-serializable mapping that rejects post-preparation mutation."""

    def _immutable(self, *_args, **_kwargs):
        raise TypeError("prepared execution is immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _immutable


def freeze(value: Any) -> Any:
    """Recursively freeze command-derived values before admission."""
    if isinstance(value, Mapping):
        return FrozenDict({str(key): freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class PreparedApprovedModelExecution:
    """All deterministic model-execution inputs, frozen before approval use."""

    command: Mapping[str, Any]
    approval_request_id: str
    prompt_assembly_digest: str
    dispatch_prompt_digest: str
    mission_id: str
    task_id: str
    driver_run_id: str
    resource: str
    data: Mapping[str, Any]
    operation: str = "ModelOperatorInspection"

    @property
    def approval_identity(self) -> Mapping[str, str]:
        return FrozenDict({
            "promptAssemblyDigest": self.prompt_assembly_digest,
            "missionId": self.mission_id,
            "taskId": self.task_id,
            "driverRunId": self.driver_run_id,
            "resource": self.resource,
        })
