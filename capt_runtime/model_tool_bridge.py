"""Translate approved model function calls into canonical CAPT ToolRequests.

This bridge is deliberately mechanics-only: it cannot mint capability authority.
Every call is checked against the frozen model authority profile, translated to
a contract-valid ToolRequest, and executed through ToolBroker.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .contracts import digest
from .errors import AuthorityViolation
from .model_authority import revalidate_normalized_model_authority
from .tool_broker import ToolBroker, tool_request_fingerprint

MODEL_TOOL_MAX_CALLS = 32

_TOOL_MAP = {
    "capt_file_read": ("file.operations", "file.read", False),
    "capt_file_search": ("file.operations", "file.search", False),
    "capt_file_write": ("file.operations", "file.write", True),
    "capt_file_patch": ("file.operations", "file.patch", True),
    "capt_shell_exec": ("terminal.local", "terminal.exec", True),
}
_OPERATION_TO_NAME = {value[1]: name for name, value in _TOOL_MAP.items()}


def _stable(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": properties,
                "required": required,
            },
        },
    }


_TOOL_SCHEMAS = {
    "capt_file_read": _schema(
        "capt_file_read",
        "Read bytes from one file inside the approved filesystem scope.",
        {
            "path": {"type": "string"},
            "offset": {"type": "integer", "minimum": 0},
            "limit_bytes": {"type": "integer", "minimum": 1, "maximum": 65536},
        },
        ["path"],
    ),
    "capt_file_search": _schema(
        "capt_file_search",
        "Search UTF-8 text files inside the approved filesystem scope.",
        {
            "search_root": {"type": "string"},
            "query": {"type": "string", "minLength": 1},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
            "max_file_bytes": {"type": "integer", "minimum": 1, "maximum": 4194304},
            "case_sensitive": {"type": "boolean"},
        },
        ["query"],
    ),
    "capt_file_write": _schema(
        "capt_file_write",
        "Write one UTF-8 file inside the approved filesystem scope. Consequential.",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        ["path", "content"],
    ),
    "capt_file_patch": _schema(
        "capt_file_patch",
        "Replace an exact string occurrence count in one approved file. Consequential.",
        {
            "path": {"type": "string"},
            "old": {"type": "string", "minLength": 1},
            "new": {"type": "string"},
            "expected_replacements": {"type": "integer", "minimum": 0},
        },
        ["path", "old", "new", "expected_replacements"],
    ),
    "capt_shell_exec": _schema(
        "capt_shell_exec",
        "Execute explicit argv without a shell inside the approved filesystem scope. Consequential.",
        {
            "argv": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 1024},
            "cwd": {"type": "string"},
            "timeout_ms": {"type": "integer", "minimum": 1, "maximum": 3600000},
            "stdout_limit_bytes": {"type": "integer", "minimum": 0},
            "stderr_limit_bytes": {"type": "integer", "minimum": 0},
        },
        ["argv"],
    ),
}


def model_tool_schemas_for_operations(operations: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    schemas: list[dict[str, Any]] = []
    for operation in operations:
        name = _OPERATION_TO_NAME.get(str(operation))
        if name is None:
            raise AuthorityViolation("MODEL_TOOL_OPERATION_UNKNOWN:" + str(operation))
        schemas.append(_TOOL_SCHEMAS[name])
    return schemas


def model_tool_schema_digest(authority_profile: Mapping[str, Any]) -> str:
    operations = authority_profile.get("toolOperations")
    if not isinstance(operations, (list, tuple)):
        raise AuthorityViolation("MODEL_TOOL_OPERATIONS_MALFORMED")
    return digest(model_tool_schemas_for_operations(operations))


class ModelToolBridge:
    """One approved DriverRun's immutable ToolBroker adapter."""

    def __init__(
        self,
        *,
        broker: ToolBroker,
        authority_profile: Mapping[str, Any],
        grant_id: str,
        lease_id: str,
        operator_id: str,
        session_id: str,
        driver_run_id: str,
        now: Callable[[], str],
        target_root: str | None = None,
    ) -> None:
        validation_target = target_root or str(authority_profile.get("filesystemRoot", ""))
        self.profile = revalidate_normalized_model_authority(
            authority_profile, target_root=validation_target
        )
        self.broker = broker
        self.grant_id = grant_id
        self.lease_id = lease_id
        self.operator_id = operator_id
        self.session_id = session_id
        self.driver_run_id = driver_run_id
        self.now = now
        self.root = Path(self.profile["filesystemRoot"])
        self.allowed_operations = frozenset(self.profile["toolOperations"])
        self.max_calls = MODEL_TOOL_MAX_CALLS

    def openai_tools(self) -> list[dict[str, Any]]:
        return model_tool_schemas_for_operations(self.profile["toolOperations"])

    @property
    def schema_digest(self) -> str:
        return model_tool_schema_digest(self.profile)

    def execute_call(
        self,
        name: str,
        arguments: Mapping[str, Any] | str,
        *,
        call_id: str,
    ) -> dict[str, Any]:
        mapping = _TOOL_MAP.get(name)
        if mapping is None:
            raise AuthorityViolation("MODEL_TOOL_UNKNOWN")
        tool_id, operation, consequential = mapping
        if operation not in self.allowed_operations:
            raise AuthorityViolation("MODEL_TOOL_NOT_AUTHORIZED:" + operation)
        args = self._decode_arguments(arguments)
        request = self._request(
            tool_id=tool_id,
            operation=operation,
            consequential=consequential,
            args=args,
            call_id=call_id,
        )
        result = self.broker.execute(
            request,
            operator_id=self.operator_id,
            session_id=self.session_id,
        )
        tool_result = result["result"]
        values = {item["name"]: item.get("value") for item in tool_result.get("output", [])}
        return {
            "toolExecutionId": result["toolExecutionId"],
            "status": tool_result["status"],
            "exitCode": tool_result.get("exitCode"),
            "values": values,
            "replayed": bool(result.get("replayed")),
        }

    @staticmethod
    def _decode_arguments(value: Mapping[str, Any] | str) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError as exc:
                raise AuthorityViolation("MODEL_TOOL_ARGUMENTS_INVALID_JSON") from exc
            if not isinstance(decoded, dict):
                raise AuthorityViolation("MODEL_TOOL_ARGUMENTS_MUST_BE_OBJECT")
            return decoded
        raise AuthorityViolation("MODEL_TOOL_ARGUMENTS_MUST_BE_OBJECT")

    def _absolute_path(self, value: Any, *, default_root: bool = False) -> str:
        if value is None and default_root:
            return str(self.root)
        if not isinstance(value, str) or not value.strip():
            raise AuthorityViolation("MODEL_TOOL_PATH_REQUIRED")
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.root / path
        return str(path)

    @staticmethod
    def _arg(name: str, value: Any, kind: str) -> dict[str, Any]:
        return {"kind": kind, "name": name, "value": value}

    def _typed_arguments(self, operation: str, args: dict[str, Any]) -> list[dict[str, Any]]:
        if operation == "file.read":
            out = [self._arg("path", self._absolute_path(args.get("path")), "path")]
            if "offset" in args: out.append(self._arg("offset", args["offset"], "integer"))
            if "limit_bytes" in args: out.append(self._arg("limit_bytes", args["limit_bytes"], "integer"))
            return out
        if operation == "file.search":
            out = [
                self._arg("search_root", self._absolute_path(args.get("search_root"), default_root=True), "path"),
                self._arg("query", args.get("query"), "string"),
            ]
            if "max_results" in args: out.append(self._arg("max_results", args["max_results"], "integer"))
            if "max_file_bytes" in args: out.append(self._arg("max_file_bytes", args["max_file_bytes"], "integer"))
            if "case_sensitive" in args: out.append(self._arg("case_sensitive", args["case_sensitive"], "boolean"))
            return out
        if operation == "file.write":
            return [
                self._arg("path", self._absolute_path(args.get("path")), "path"),
                self._arg("content", args.get("content"), "string"),
            ]
        if operation == "file.patch":
            return [
                self._arg("path", self._absolute_path(args.get("path")), "path"),
                self._arg("old", args.get("old"), "string"),
                self._arg("new", args.get("new"), "string"),
                self._arg("expected_replacements", args.get("expected_replacements"), "integer"),
            ]
        if operation == "terminal.exec":
            argv = args.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                raise AuthorityViolation("MODEL_TOOL_ARGV_INVALID")
            out = [
                self._arg("argv", json.dumps(argv, separators=(",", ":")), "string"),
                self._arg("cwd", self._absolute_path(args.get("cwd"), default_root=True), "path"),
            ]
            for name in ("timeout_ms", "stdout_limit_bytes", "stderr_limit_bytes"):
                if name in args: out.append(self._arg(name, args[name], "integer"))
            return out
        raise AuthorityViolation("MODEL_TOOL_UNKNOWN_OPERATION")

    def _request(
        self,
        *,
        tool_id: str,
        operation: str,
        consequential: bool,
        args: dict[str, Any],
        call_id: str,
    ) -> dict[str, Any]:
        material = self.driver_run_id + ":" + str(call_id)
        idem = _stable("model-tool-", material)
        typed = self._typed_arguments(operation, args)
        target = str(self.root)
        for item in typed:
            if item["name"] in {"path", "search_root", "cwd"}:
                target = str(item["value"])
                break
        request = {
            "schemaVersion": "1.0.0",
            "toolRequestId": _stable("model-tool-request-", material),
            "toolId": tool_id,
            "operation": operation,
            "arguments": typed,
            "consequential": consequential,
            "grantId": self.grant_id,
            "leaseId": self.lease_id,
            "reservationId": None,
            "backendId": "local",
            "targetIdentity": target,
            "filesystemScope": str(self.root),
            "idempotencyKey": idem,
            "operationFingerprint": "sha256:" + "0" * 64,
            "replayPolicy": "never",
            "requestedAt": self.now(),
        }
        request["operationFingerprint"] = tool_request_fingerprint(request)
        return request
