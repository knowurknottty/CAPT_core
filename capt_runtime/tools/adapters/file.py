"""Scoped local file operations for CAPT ToolBroker.

This adapter implements filesystem mechanics only. It does not grant authority,
settle capability use, or expose a normal operator path around ToolBroker.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterable

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.scope import require_scoped_path

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
    supports_reconciliation = False

    @staticmethod
    def readiness() -> dict[str, object]:
        return {"status": "available", "reason": "local scoped filesystem adapter loaded"}

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
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
        args = _arguments(request, operation)
        if operation == "file.read":
            return self._read(Path(scope), args)
        if operation == "file.search":
            return self._search(Path(scope), args)
        if operation == "file.write":
            return self._write(Path(scope), args)
        return self._patch(Path(scope), args)

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
