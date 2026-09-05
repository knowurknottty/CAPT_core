"""Scoped local file operations for CAPT ToolBroker.

This adapter implements filesystem mechanics only. It does not grant authority,
settle capability use, or expose a normal operator path around ToolBroker.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.scope import require_scoped_path
from capt_runtime.world_receipt import (
    effect_intent_id,
    receipt_side_effect_identity,
    verify_world_receipt,
    world_receipt_id,
)

MAX_READ_BYTES = 65_536
MAX_MUTATION_BYTES = 16 * 1024 * 1024
MAX_SEARCH_FILE_BYTES = 4 * 1024 * 1024
DEFAULT_SEARCH_FILE_BYTES = 1024 * 1024
MAX_SEARCH_RESULTS = 500
MAX_SEARCH_FILES = 5_000
MAX_SEARCH_JSON_CHARS = 60_000
MAX_MATCH_LINE_CHARS = 4_096

_OPERATION_ARGUMENTS = {
    "file.read": {"path", "offset", "limit_bytes"},
    "file.search": {
        "search_root",
        "query",
        "max_results",
        "max_file_bytes",
        "case_sensitive",
    },
    "file.write": {"path", "content"},
    "file.patch": {"path", "old", "new", "expected_replacements"},
}
_REQUIRED_ARGUMENTS = {
    "file.read": {"path"},
    "file.search": {"search_root", "query"},
    "file.write": {"path", "content"},
    "file.patch": {"path", "old", "new", "expected_replacements"},
}


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _output(kind: str, name: str, value: Any) -> dict[str, Any]:
    return {"kind": kind, "name": name, "value": value}


def _success(
    output: Iterable[dict[str, Any]], *, side_effect_identity: str | None = None
) -> dict[str, Any]:
    return {
        "status": "succeeded",
        "exitCode": None,
        "output": list(output),
        "sideEffectIdentity": side_effect_identity,
        "error": None,
    }


def _arguments(request: dict[str, Any], operation: str) -> dict[str, Any]:
    allowed = _OPERATION_ARGUMENTS[operation]
    parsed: dict[str, Any] = {}
    for item in request.get("arguments", []):
        name = item.get("name")
        if name in parsed:
            raise ValueError(f"duplicate argument: {name}")
        if name not in allowed:
            raise ValueError(f"unknown argument for {operation}: {name}")
        parsed[name] = item.get("value")
    missing = _REQUIRED_ARGUMENTS[operation].difference(parsed)
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(sorted(missing))}")
    return parsed


def _integer(value: Any, name: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _ordinary_file(path: Path, operation: str) -> None:
    if not path.is_file():
        raise AuthorityViolation(f"{operation} target is not an ordinary file: {path}")


def _atomic_replace(path: Path, data: bytes, *, mode: int | None) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".capt-file-", dir=str(path.parent))
    temp = Path(temp_name)
    try:
        if mode is None:
            os.fchmod(fd, 0o600)
        else:
            os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            fd = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _effect_identity(
    operation: str, path: Path, before_digest: str, after_digest: str
) -> str:
    return json.dumps(
        {
            "operation": operation,
            "path": str(path),
            "beforeDigest": before_digest,
            "afterDigest": after_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


class FileToolAdapter:
    adapter_id = "adapter-file-operations"
    supports_reconciliation = True

    @staticmethod
    def readiness() -> dict[str, object]:
        return {"status": "available", "reason": "local scoped filesystem adapter loaded"}

    @staticmethod
    def _validated_request(request: dict[str, Any]) -> tuple[Path, str, dict[str, Any]]:
        if request.get("toolId") != "file.operations":
            raise AuthorityViolation("FileToolAdapter requires toolId=file.operations")
        if request.get("backendId") != "local":
            raise AuthorityViolation("FileToolAdapter supports only backendId=local")
        scope = request.get("filesystemScope")
        if not scope:
            raise AuthorityViolation("file operation requires filesystemScope")
        operation = request.get("operation")
        if operation not in _OPERATION_ARGUMENTS:
            raise AuthorityViolation(f"unsupported file operation: {operation}")
        return Path(scope), operation, _arguments(request, operation)

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        root, operation, args = self._validated_request(request)
        if operation == "file.read":
            return self._read(root, args)
        if operation == "file.search":
            return self._search(root, args)
        if operation == "file.write":
            return self._write(root, args)
        return self._patch(root, args)

    @staticmethod
    def _receipt_path(target: Path, intent_id: str) -> Path:
        suffix = intent_id.removeprefix("effect-intent-")
        return target.with_name(f".{target.name}.capt-receipt-{suffix}.json")

    @staticmethod
    def _reversal_path(target: Path, intent_id: str) -> Path:
        suffix = intent_id.removeprefix("effect-intent-")
        return target.with_name(f".{target.name}.capt-rollback-{suffix}")

    @staticmethod
    @contextmanager
    def _target_lock(root: Path, target: Path):
        """Serialize cooperating CAPT writers for one file target.

        This is intentionally advisory: it closes CAPT-vs-CAPT races but does
        not pretend arbitrary external filesystem writers participate.
        """
        lock_path = require_scoped_path(
            root, target.with_name(f".{target.name}.capt-lock"), for_write=True
        )
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(lock_path, flags, 0o600)
        except OSError as exc:
            raise AuthorityViolation(
                f"WORLD_RECEIPT_TARGET_LOCK_UNAVAILABLE: {lock_path}"
            ) from exc
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    @staticmethod
    def _result_value(result: dict[str, Any], name: str) -> Any:
        for item in result.get("output", []):
            if item.get("name") == name:
                return item.get("value")
        raise ValueError(f"missing adapter output {name}")

    def prepare_effect(self, request: dict[str, Any]) -> dict[str, Any]:
        root, operation, args = self._validated_request(request)
        if operation not in {"file.write", "file.patch"}:
            raise AuthorityViolation("WORLD_RECEIPT_FILE_MUTATION_REQUIRED")
        if operation == "file.write":
            target = require_scoped_path(root, args["path"], for_write=True)
            if target.exists() and not target.is_file():
                raise AuthorityViolation(f"write target is not an ordinary file: {target}")
            content = args["content"]
            if not isinstance(content, str):
                raise ValueError("content must be a string")
            data = content.encode("utf-8")
            if len(data) > MAX_MUTATION_BYTES:
                raise ValueError(f"content exceeds {MAX_MUTATION_BYTES} bytes")
            before = _digest_file(target) if target.exists() else "absent"
            expected_after = _digest_bytes(data)
        else:
            target = require_scoped_path(root, args["path"])
            _ordinary_file(target, "patch")
            require_scoped_path(root, args["path"], for_write=True)
            old, new = args["old"], args["new"]
            if not isinstance(old, str) or not isinstance(new, str) or old == "":
                raise ValueError("patch old/new must be strings and old must not be empty")
            expected = _integer(
                args["expected_replacements"], "expected_replacements",
                minimum=0, maximum=1_000_000,
            )
            data = target.read_bytes()
            if len(data) > MAX_MUTATION_BYTES:
                raise ValueError(f"patch target exceeds {MAX_MUTATION_BYTES} bytes")
            actual = data.count(old.encode("utf-8"))
            if actual != expected:
                raise ValueError(
                    f"replacement count mismatch: expected {expected}, observed {actual}"
                )
            patched = data.replace(old.encode("utf-8"), new.encode("utf-8"))
            if len(patched) > MAX_MUTATION_BYTES:
                raise ValueError(f"patched content exceeds {MAX_MUTATION_BYTES} bytes")
            before = _digest_bytes(data)
            expected_after = _digest_bytes(patched)

        intent_id = effect_intent_id(request["idempotencyKey"])
        receipt_path = require_scoped_path(
            root, self._receipt_path(target, intent_id), for_write=True
        )
        reversal_path = require_scoped_path(
            root, self._reversal_path(target, intent_id), for_write=True
        )
        return {
            "targetIdentity": str(target),
            "basisVersion": before,
            "atomicDomain": "file-replace:" + str(target),
            "coordinationMode": "staged",
            "rollbackStrategy": "escrow",
            "reconciliationStrategy": "target_receipt",
            "reversalHandle": str(reversal_path),
            "receiptSpec": {
                "receiptKind": "file_sidecar",
                "targetLocal": True,
                "locator": str(receipt_path),
                "expectedPostStateDigest": expected_after,
            },
        }

    def verify_reversal_handle(self, effect_intent: dict[str, Any]) -> bool:
        target = Path(effect_intent["targetIdentity"])
        reversal = effect_intent.get("reversalHandle")
        if not isinstance(reversal, str) or not reversal:
            raise AuthorityViolation("WORLD_RECEIPT_REVERSAL_HANDLE_REQUIRED")
        reversal_path = Path(reversal)
        expected = self._reversal_path(target, effect_intent["effectIntentId"])
        if reversal_path != expected:
            raise AuthorityViolation("WORLD_RECEIPT_REVERSAL_HANDLE_CHANGED")
        if reversal_path.is_symlink() or not reversal_path.is_file():
            raise AuthorityViolation("WORLD_RECEIPT_REVERSAL_HANDLE_NOT_ORDINARY_FILE")
        if effect_intent["basisVersion"] == "absent":
            if reversal_path.stat().st_size != 0:
                raise AuthorityViolation("WORLD_RECEIPT_ABSENT_REVERSAL_MARKER_INVALID")
        elif _digest_file(reversal_path) != effect_intent["basisVersion"]:
            raise AuthorityViolation("WORLD_RECEIPT_REVERSAL_PREIMAGE_MISMATCH")
        return True

    def _persist_world_receipt(self, receipt_path: Path, receipt: dict[str, Any]) -> None:
        payload = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()
        _atomic_replace(receipt_path, payload, mode=None)

    def execute_world_effect(
        self, request: dict[str, Any], effect_intent: dict[str, Any], observe_effect
    ) -> dict[str, Any]:
        root, operation, args = self._validated_request(request)
        if operation not in {"file.write", "file.patch"}:
            raise AuthorityViolation("WORLD_RECEIPT_FILE_MUTATION_REQUIRED")
        target = Path(effect_intent["targetIdentity"])
        scoped_target = require_scoped_path(root, target, for_write=True)
        if scoped_target != target:
            raise AuthorityViolation("WORLD_RECEIPT_TARGET_IDENTITY_CHANGED")

        with self._target_lock(root, target):
            current = _digest_file(target) if target.exists() else "absent"
            if current != effect_intent["basisVersion"]:
                raise AuthorityViolation("WORLD_RECEIPT_BASIS_VERSION_CHANGED")

            reversal_path = require_scoped_path(
                root, effect_intent.get("reversalHandle"), for_write=True
            )
            expected_reversal = self._reversal_path(
                target, effect_intent["effectIntentId"]
            )
            if reversal_path != expected_reversal:
                raise AuthorityViolation("WORLD_RECEIPT_REVERSAL_HANDLE_CHANGED")
            preimage = b"" if current == "absent" else target.read_bytes()
            if current != "absent" and _digest_bytes(preimage) != current:
                raise AuthorityViolation("WORLD_RECEIPT_PREIMAGE_CHANGED_DURING_STAGE")
            _atomic_replace(reversal_path, preimage, mode=None)
            self.verify_reversal_handle(effect_intent)

            result = (
                self._write(root, args)
                if operation == "file.write"
                else self._patch(root, args)
            )
            actual_before = self._result_value(result, "beforeDigest")
            if actual_before != effect_intent["basisVersion"]:
                raise AuthorityViolation("WORLD_RECEIPT_BASIS_CHANGED_DURING_COMMIT")
            after = self._result_value(result, "afterDigest")
            if after != effect_intent["receiptSpec"]["expectedPostStateDigest"]:
                raise AuthorityViolation("WORLD_RECEIPT_POST_STATE_MISMATCH")
            receipt_path = require_scoped_path(
                root, effect_intent["receiptSpec"]["locator"], for_write=True
            )
            expected_receipt = self._receipt_path(
                target, effect_intent["effectIntentId"]
            )
            if receipt_path != expected_receipt:
                raise AuthorityViolation("WORLD_RECEIPT_LOCATOR_CHANGED")
            receipt = {
                "schemaVersion": "1.0.0",
                "receiptId": world_receipt_id(effect_intent["intentDigest"], after),
                "effectIntentId": effect_intent["effectIntentId"],
                "intentDigest": effect_intent["intentDigest"],
                "targetIdentity": str(target),
                "receiptKind": "file_sidecar",
                "receiptLocator": str(receipt_path),
                "observedStateDigest": after,
                "verifiedAt": datetime.now(timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                ),
                "commitState": "committed",
                "reversalHandle": str(reversal_path),
            }
            verify_world_receipt(effect_intent, receipt)
            self._persist_world_receipt(receipt_path, receipt)
            self.verify_receipt(effect_intent, receipt)

        identity = receipt_side_effect_identity(receipt)
        observe_effect(identity)
        result = dict(result)
        result["sideEffectIdentity"] = identity
        result["worldReceipt"] = receipt
        return result

    def verify_receipt(self, effect_intent: dict[str, Any], receipt: dict[str, Any]) -> bool:
        verify_world_receipt(effect_intent, receipt)
        target = Path(effect_intent["targetIdentity"])
        receipt_path = Path(effect_intent["receiptSpec"]["locator"])
        if receipt_path != self._receipt_path(target, effect_intent["effectIntentId"]):
            raise AuthorityViolation("WORLD_RECEIPT_LOCATOR_CHANGED")
        if target.is_symlink() or not target.is_file():
            raise AuthorityViolation("WORLD_RECEIPT_TARGET_NOT_ORDINARY_FILE")
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise AuthorityViolation("WORLD_RECEIPT_PROOF_NOT_ORDINARY_FILE")
        on_disk = json.loads(receipt_path.read_text(encoding="utf-8"))
        if on_disk != receipt:
            raise AuthorityViolation("WORLD_RECEIPT_TARGET_PROOF_MISMATCH")
        if _digest_file(target) != receipt["observedStateDigest"]:
            raise AuthorityViolation("WORLD_RECEIPT_OBSERVED_STATE_CHANGED")
        self.verify_reversal_handle(effect_intent)
        return True

    def reconcile(self, execution_state: dict[str, Any]) -> dict[str, Any] | None:
        intent = execution_state.get("effectIntent")
        if not intent:
            return None
        receipt_path = Path(intent["receiptSpec"]["locator"])
        if not receipt_path.exists():
            return None
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise AuthorityViolation("WORLD_RECEIPT_PROOF_NOT_ORDINARY_FILE")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.verify_receipt(intent, receipt)
        return receipt

    def reverse_world_effect(
        self, request: dict[str, Any], effect_intent: dict[str, Any]
    ) -> dict[str, Any]:
        """Reverse a staged file effect only while its exact post-state still holds."""
        root, operation, _args = self._validated_request(request)
        if operation not in {"file.write", "file.patch"}:
            raise AuthorityViolation("WORLD_RECEIPT_FILE_MUTATION_REQUIRED")
        target = Path(effect_intent["targetIdentity"])
        target = require_scoped_path(root, target, for_write=True)
        expected_post = effect_intent["receiptSpec"]["expectedPostStateDigest"]
        current = _digest_file(target) if target.exists() else "absent"
        if current != expected_post:
            raise AuthorityViolation("WORLD_RECEIPT_REVERSAL_POST_STATE_CHANGED")
        self.verify_reversal_handle(effect_intent)
        reversal_path = Path(effect_intent["reversalHandle"])
        if effect_intent["basisVersion"] == "absent":
            target.unlink()
            dir_fd = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            restored = "absent"
        else:
            mode = stat.S_IMODE(target.stat().st_mode)
            _atomic_replace(target, reversal_path.read_bytes(), mode=mode)
            restored = _digest_file(target)
        if restored != effect_intent["basisVersion"]:
            raise AuthorityViolation("WORLD_RECEIPT_REVERSAL_VERIFY_FAILED")
        return {
            "status": "succeeded",
            "targetIdentity": str(target),
            "restoredBasisVersion": restored,
            "reversalHandle": str(reversal_path),
        }

    def _read(self, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        target = require_scoped_path(root, args["path"])
        _ordinary_file(target, "read")
        offset = _integer(args.get("offset", 0), "offset", minimum=0, maximum=2**63 - 1)
        limit = _integer(
            args.get("limit_bytes", MAX_READ_BYTES),
            "limit_bytes",
            minimum=1,
            maximum=MAX_READ_BYTES,
        )
        total = target.stat().st_size
        with target.open("rb") as handle:
            handle.seek(offset)
            data = handle.read(limit)
        next_offset = offset + len(data)
        truncated = next_offset < total
        return _success(
            [
                _output("string", "content", data.decode("utf-8", errors="replace")),
                _output("integer", "bytesReturned", len(data)),
                _output("integer", "totalBytes", total),
                _output("boolean", "truncated", truncated),
                _output("integer", "nextOffset", next_offset),
                _output("string", "fileDigest", _digest_file(target)),
            ]
        )

    def _write(self, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        target = require_scoped_path(root, args["path"], for_write=True)
        if target.exists() and not target.is_file():
            raise AuthorityViolation(f"write target is not an ordinary file: {target}")
        content = args["content"]
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        data = content.encode("utf-8")
        if len(data) > MAX_MUTATION_BYTES:
            raise ValueError(f"content exceeds {MAX_MUTATION_BYTES} bytes")
        before = _digest_file(target) if target.exists() else "absent"
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
        _atomic_replace(target, data, mode=mode)
        after = _digest_file(target)
        return _success(
            [
                _output("string", "beforeDigest", before),
                _output("string", "afterDigest", after),
                _output("integer", "byteCount", len(data)),
            ],
            side_effect_identity=_effect_identity("file.write", target, before, after),
        )

    def _patch(self, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        target = require_scoped_path(root, args["path"])
        _ordinary_file(target, "patch")
        writable = require_scoped_path(root, args["path"], for_write=True)
        old = args["old"]
        new = args["new"]
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError("old and new must be strings")
        if old == "":
            raise ValueError("old must not be empty")
        expected = _integer(
            args["expected_replacements"],
            "expected_replacements",
            minimum=0,
            maximum=1_000_000,
        )
        size = target.stat().st_size
        if size > MAX_MUTATION_BYTES:
            raise ValueError(f"patch target exceeds {MAX_MUTATION_BYTES} bytes")
        data = target.read_bytes()
        old_bytes = old.encode("utf-8")
        actual = data.count(old_bytes)
        if actual != expected:
            raise ValueError(
                f"replacement count mismatch: expected {expected}, observed {actual}"
            )
        patched = data.replace(old_bytes, new.encode("utf-8"))
        if len(patched) > MAX_MUTATION_BYTES:
            raise ValueError(f"patched content exceeds {MAX_MUTATION_BYTES} bytes")
        before = _digest_bytes(data)
        mode = stat.S_IMODE(target.stat().st_mode)
        _atomic_replace(writable, patched, mode=mode)
        after = _digest_file(writable)
        return _success(
            [
                _output("string", "beforeDigest", before),
                _output("string", "afterDigest", after),
                _output("integer", "byteCount", len(patched)),
                _output("integer", "replacementCount", actual),
            ],
            side_effect_identity=_effect_identity("file.patch", writable, before, after),
        )

    def _search(self, root: Path, args: dict[str, Any]) -> dict[str, Any]:
        search_root = require_scoped_path(root, args["search_root"])
        if not search_root.is_dir():
            raise AuthorityViolation(f"search_root is not a directory: {search_root}")
        query = args["query"]
        if not isinstance(query, str) or not query:
            raise ValueError("query must be a non-empty string")
        max_results = _integer(
            args.get("max_results", 100),
            "max_results",
            minimum=1,
            maximum=MAX_SEARCH_RESULTS,
        )
        max_file_bytes = _integer(
            args.get("max_file_bytes", DEFAULT_SEARCH_FILE_BYTES),
            "max_file_bytes",
            minimum=1,
            maximum=MAX_SEARCH_FILE_BYTES,
        )
        case_sensitive = _boolean(args.get("case_sensitive", False), "case_sensitive")
        needle = query if case_sensitive else query.casefold()
        scope_root = require_scoped_path(root, root)
        matches: list[dict[str, Any]] = []
        encoded_matches = "[]"
        files_scanned = 0
        truncated = False
        stop = False

        for current, dirs, files in os.walk(search_root, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(
                name for name in dirs if not (current_path / name).is_symlink()
            )
            for name in sorted(files):
                candidate = current_path / name
                if candidate.is_symlink():
                    continue
                if files_scanned >= MAX_SEARCH_FILES:
                    truncated = True
                    stop = True
                    break
                try:
                    candidate = require_scoped_path(root, candidate)
                except AuthorityViolation:
                    continue
                if not candidate.is_file():
                    continue
                files_scanned += 1
                try:
                    with candidate.open("rb") as handle:
                        data = handle.read(max_file_bytes + 1)
                except OSError:
                    continue
                if len(data) > max_file_bytes or b"\x00" in data:
                    continue
                text = data.decode("utf-8", errors="replace")
                for line_number, line in enumerate(text.splitlines(), start=1):
                    haystack = line if case_sensitive else line.casefold()
                    if needle not in haystack:
                        continue
                    if len(matches) >= max_results:
                        truncated = True
                        stop = True
                        break
                    relative = str(candidate.relative_to(scope_root))
                    match = {
                        "path": relative,
                        "lineNumber": line_number,
                        "line": line[:MAX_MATCH_LINE_CHARS],
                    }
                    projected = json.dumps(
                        matches + [match], sort_keys=True, separators=(",", ":")
                    )
                    if len(projected) > MAX_SEARCH_JSON_CHARS:
                        truncated = True
                        stop = True
                        break
                    matches.append(match)
                    encoded_matches = projected
                if stop:
                    break
            if stop:
                break

        return _success(
            [
                _output("string", "matches", encoded_matches),
                _output("integer", "resultCount", len(matches)),
                _output("integer", "filesScanned", files_scanned),
                _output("boolean", "truncated", truncated),
            ]
        )
