"""Immutable, credential-free boundary for approved model execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import digest


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
    """All non-secret deterministic execution inputs, frozen before admission.

    Provider credentials deliberately are not represented here.  They are resolved
    only after durable admission, from the provider identifier held below.
    """

    command_id: str
    idempotency_key: str
    correlation_id: str
    issued_at: str
    approval_request_id: str
    prompt_assembly_digest: str
    dispatch_prompt_digest: str
    mission_id: str
    task_id: str
    driver_run_id: str
    resource: str
    objective: str
    provider_id: str | None
    provider_model: str | None
    executable: str | None
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

    @property
    def prepared_execution_digest(self) -> str:
        """Canonical digest binding all non-secret dispatch-relevant inputs."""
        return digest({
            "commandId": self.command_id,
            "idempotencyKey": self.idempotency_key,
            "correlationId": self.correlation_id,
            "issuedAt": self.issued_at,
            "approvalRequestId": self.approval_request_id,
            "promptAssemblyDigest": self.prompt_assembly_digest,
            "dispatchPromptDigest": self.dispatch_prompt_digest,
            "missionId": self.mission_id,
            "taskId": self.task_id,
            "driverRunId": self.driver_run_id,
            "resource": self.resource,
            "objective": self.objective,
            "providerId": self.provider_id,
            "providerModel": self.provider_model,
            "executable": self.executable,
            "operation": self.operation,
            "data": self.data,
        })
    @property
    def preparedExecutionDigest(self) -> str:
        """Contract-facing camelCase spelling of the prepared digest."""
        return self.prepared_execution_digest


def prepared_execution_digest(prepared: PreparedApprovedModelExecution) -> str:
    """Named canonical digest API for the prepared-execution admission binding."""
    return prepared.prepared_execution_digest
