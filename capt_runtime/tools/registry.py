"""Tool descriptor registry and truthful readiness projection.

The registry owns metadata and implementation references only. It never grants
capabilities and never dispatches a tool as a side effect of registration.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from capt_runtime.contracts import digest, require


class ToolRegistryError(RuntimeError):
    pass


class DuplicateToolId(ToolRegistryError):
    pass


class UnknownToolId(ToolRegistryError):
    pass


class InvalidToolDescriptor(ToolRegistryError):
    pass


ReadinessProbe = Callable[[], Dict[str, Any]]


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_operation_effects(descriptor: Dict[str, Any]) -> None:
    operations = list(descriptor["operations"])
    effects = list(descriptor["operationEffects"])
    effect_ops = [entry["operation"] for entry in effects]
    if len(effect_ops) != len(set(effect_ops)):
        raise InvalidToolDescriptor("operationEffects contains duplicate operations")
    if set(effect_ops) != set(operations):
        raise InvalidToolDescriptor(
            "operationEffects must cover descriptor operations exactly: "
            f"operations={sorted(operations)!r} effects={sorted(effect_ops)!r}"
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._registrations: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        descriptor: Dict[str, Any],
        adapter: Any,
        readiness_probe: Optional[ReadinessProbe] = None,
    ) -> Dict[str, Any]:
        require("ToolDescriptor", descriptor)
        _validate_operation_effects(descriptor)
        tool_id = descriptor["toolId"]
        if tool_id in self._registrations:
            raise DuplicateToolId(f"tool id already registered: {tool_id}")
        stored = deepcopy(descriptor)
        registration = {
            "descriptor": stored,
            "descriptorDigest": digest(stored),
            "adapter": adapter,
            "readinessProbe": readiness_probe,
        }
        self._registrations[tool_id] = registration
        return self.require(tool_id)

    def require(self, tool_id: str) -> Dict[str, Any]:
        try:
            registration = self._registrations[tool_id]
        except KeyError as exc:
            raise UnknownToolId(f"tool is not registered: {tool_id}") from exc
        return {
            "descriptor": deepcopy(registration["descriptor"]),
            "descriptorDigest": registration["descriptorDigest"],
            "adapter": registration["adapter"],
        }

    def adapter(self, tool_id: str) -> Any:
        return self.require(tool_id)["adapter"]

    def descriptor_digest(self, tool_id: str) -> str:
        return self.require(tool_id)["descriptorDigest"]

    def effect_class(self, tool_id: str, operation: str) -> str:
        descriptor = self.require(tool_id)["descriptor"]
        for entry in descriptor["operationEffects"]:
            if entry["operation"] == operation:
                return entry["effectClass"]
        raise InvalidToolDescriptor(f"operation is not declared for {tool_id}: {operation}")

    def readiness(self, tool_id: str) -> Dict[str, Any]:
        registration = self._registrations.get(tool_id)
        if registration is None:
            raise UnknownToolId(f"tool is not registered: {tool_id}")
        probe = registration["readinessProbe"]
        if probe is None:
            return require("ToolReadiness", {
                "schemaVersion": "1.0.0", "toolId": tool_id,
                "status": "unverified", "reason": "no readiness probe registered",
                "checkedAt": _now_rfc3339(),
            })
        try:
            projected = dict(probe())
            require("ToolReadiness", projected)
            if projected["toolId"] != tool_id:
                raise InvalidToolDescriptor(
                    f"readiness probe toolId mismatch: expected {tool_id}, got {projected['toolId']}"
                )
            return projected
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"[:2048]
            return require("ToolReadiness", {
                "schemaVersion": "1.0.0", "toolId": tool_id,
                "status": "unavailable", "reason": reason,
                "checkedAt": _now_rfc3339(),
            })

    def list_descriptors(self) -> list[Dict[str, Any]]:
        return [
            deepcopy(self._registrations[tool_id]["descriptor"])
            for tool_id in sorted(self._registrations)
        ]
