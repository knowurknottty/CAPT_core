from __future__ import annotations

import json
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.adapters.file import FileToolAdapter


def _request(operation: str, root: Path, **arguments) -> dict:
    typed = []
    for name, value in arguments.items():
        if isinstance(value, bool):
            kind = "boolean"
        elif isinstance(value, int):
            kind = "integer"
        elif name in {"path", "search_root"}:
            kind = "path"
        else:
            kind = "string"
        typed.append({"kind": kind, "name": name, "value": value})
    return {
        "toolRequestId": "file-tool-request",
        "toolId": "file.operations",
        "operation": operation,
        "arguments": typed,
        "filesystemScope": str(root),
        "backendId": "local",
    }


def _value(result: dict, name: str):
    return next(item["value"] for item in result["output"] if item["name"] == name)


def test_read_is_bounded_and_paginated(tmp_path: Path) -> None:
    target = tmp_path / "large.txt"
    target.write_text("abcdefghij", encoding="utf-8")
    adapter = FileToolAdapter()

    first = adapter.execute(_request("file.read", tmp_path, path=target, offset=0, limit_bytes=4))
    second = adapter.execute(_request("file.read", tmp_path, path=target, offset=4, limit_bytes=4))

    assert first["status"] == "succeeded"
    assert _value(first, "content") == "abcd"
    assert _value(first, "bytesReturned") == 4
    assert _value(first, "totalBytes") == 10
    assert _value(first, "truncated") is True
    assert _value(first, "nextOffset") == 4
    assert _value(second, "content") == "efgh"
    assert _value(second, "nextOffset") == 8
    assert _value(first, "fileDigest").startswith("sha256:")


def test_read_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    (root / "escape.txt").symlink_to(outside / "secret.txt")

    with pytest.raises(AuthorityViolation):
        FileToolAdapter().execute(_request("file.read", root, path=root / "escape.txt"))


def test_write_is_atomic_and_digest_bound(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("before", encoding="utf-8")
    adapter = FileToolAdapter()

    result = adapter.execute(_request("file.write", tmp_path, path=target, content="after"))

    assert result["status"] == "succeeded"
    assert target.read_text(encoding="utf-8") == "after"
    assert _value(result, "beforeDigest").startswith("sha256:")
    assert _value(result, "afterDigest").startswith("sha256:")
    assert _value(result, "beforeDigest") != _value(result, "afterDigest")
    assert _value(result, "byteCount") == 5
    identity = json.loads(result["sideEffectIdentity"])
    assert identity["afterDigest"] == _value(result, "afterDigest")
    assert not list(tmp_path.glob(".capt-file-*"))


def test_write_new_file_reports_absent_before_identity(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"
    result = FileToolAdapter().execute(
        _request("file.write", tmp_path, path=target, content="created")
    )
    assert target.read_text() == "created"
    assert _value(result, "beforeDigest") == "absent"
    assert _value(result, "afterDigest").startswith("sha256:")


def test_write_through_escape_symlink_is_denied(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(AuthorityViolation):
        FileToolAdapter().execute(
            _request("file.write", root, path=root / "escape" / "x.txt", content="bad")
        )
    assert not (outside / "x.txt").exists()


def test_patch_requires_exact_replacement_count_and_commits_atomically(tmp_path: Path) -> None:
    target = tmp_path / "patch.txt"
    target.write_text("alpha beta alpha\n", encoding="utf-8")
    adapter = FileToolAdapter()

    with pytest.raises(ValueError, match="replacement count"):
        adapter.execute(
            _request(
                "file.patch",
                tmp_path,
                path=target,
                old="alpha",
                new="omega",
                expected_replacements=1,
            )
        )
    assert target.read_text() == "alpha beta alpha\n"

    result = adapter.execute(
        _request(
            "file.patch",
            tmp_path,
            path=target,
            old="alpha",
            new="omega",
            expected_replacements=2,
        )
    )
    assert target.read_text() == "omega beta omega\n"
    assert _value(result, "replacementCount") == 2
    assert _value(result, "beforeDigest") != _value(result, "afterDigest")
    assert not list(tmp_path.glob(".capt-file-*"))


def test_patch_rejects_empty_match_text(tmp_path: Path) -> None:
    target = tmp_path / "patch.txt"
    target.write_text("abc")
    with pytest.raises(ValueError, match="old must not be empty"):
        FileToolAdapter().execute(
            _request(
                "file.patch",
                tmp_path,
                path=target,
                old="",
                new="x",
                expected_replacements=0,
            )
        )


def test_search_is_recursive_bounded_and_does_not_follow_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    (root / "nested").mkdir(parents=True)
    outside.mkdir()
    (root / "a.txt").write_text("needle first\nother\n")
    (root / "nested" / "b.txt").write_text("second NEEDLE\nneedle third\n")
    (outside / "secret.txt").write_text("needle outside\n")
    (root / "escape").symlink_to(outside, target_is_directory=True)

    result = FileToolAdapter().execute(
        _request("file.search", root, search_root=root, query="needle", max_results=2)
    )
    matches = json.loads(_value(result, "matches"))

    assert result["status"] == "succeeded"
    assert len(matches) == 2
    assert all("secret.txt" not in match["path"] for match in matches)
    assert _value(result, "truncated") is True
    assert _value(result, "resultCount") == 2
    assert all(len(match["line"]) <= 4096 for match in matches)


def test_unknown_and_duplicate_arguments_fail_closed(tmp_path: Path) -> None:
    adapter = FileToolAdapter()
    request = _request("file.read", tmp_path, path=tmp_path / "x")
    request["arguments"].append({"kind": "string", "name": "bogus", "value": "x"})
    with pytest.raises(ValueError, match="unknown argument"):
        adapter.execute(request)

    request = _request("file.read", tmp_path, path=tmp_path / "x")
    request["arguments"].append({"kind": "path", "name": "path", "value": str(tmp_path / "x")})
    with pytest.raises(ValueError, match="duplicate argument"):
        adapter.execute(request)
