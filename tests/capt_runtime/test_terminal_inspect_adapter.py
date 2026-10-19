"""UPG-071 local inspection is a separately declared, bounded read operation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.adapters.terminal_inspect import TerminalInspectToolAdapter
from capt_runtime.tools.builtins import (
    TERMINAL_INSPECT_DESCRIPTOR,
    TERMINAL_LOCAL_DESCRIPTOR,
)
from capt_runtime.tools.readonly_argv import ReadOnlyRefused
from capt_runtime.tools.registry import ToolRegistry


def _request(root: Path, argv, *, tool="terminal.inspect", operation="terminal.inspect"):
    return {
        "toolId": tool,
        "operation": operation,
        "backendId": "local",
        "filesystemScope": str(root),
        "arguments": [
            {"kind": "string", "name": "argv", "value": json.dumps(argv)},
            {"kind": "path", "name": "cwd", "value": str(root)},
            {"kind": "integer", "name": "timeout_ms", "value": 2000},
        ],
    }


def test_separate_declared_operation_and_effect():
    reg = ToolRegistry()
    reg.register(TERMINAL_LOCAL_DESCRIPTOR, object())
    reg.register(TERMINAL_INSPECT_DESCRIPTOR, TerminalInspectToolAdapter())
    local = reg.require("terminal.local")["descriptor"]
    inspect = reg.require("terminal.inspect")["descriptor"]
    assert local["operations"] == ["terminal.exec"]
    assert inspect["operations"] == ["terminal.inspect"]
    assert inspect["requiredCapabilities"] == ["terminal.inspect"]
    assert inspect["operationEffects"] == [
        {"operation": "terminal.inspect", "effectClass": "pure_read_only"}
    ]


@pytest.mark.parametrize("argv", [
    ["uniq", "input.txt", "output.txt"],
    ["find", ".", "-exec", "/bin/sh", "-c", "echo bad", ";"],
    ["/bin/cat", "input.txt"],
    ["sh", "-c", "cat input.txt"],
    ["tail", "-f", "input.txt"],
])
def test_writes_shells_and_unbounded_commands_refuse_without_dispatch(tmp_path, argv):
    (tmp_path / "input.txt").write_text("contents")
    adapter = TerminalInspectToolAdapter()
    with pytest.raises(ReadOnlyRefused):
        adapter.execute(_request(tmp_path, argv))
    assert not (tmp_path / "output.txt").exists()


def test_wrong_tool_or_operation_fails_before_spawn(tmp_path):
    adapter = TerminalInspectToolAdapter()
    with pytest.raises(AuthorityViolation, match="exact tool"):
        adapter.execute(_request(tmp_path, ["cat", "x"], operation="terminal.exec"))


def test_scoped_read_dispatches_only_os_binary(tmp_path):
    (tmp_path / "notes.txt").write_text("strictly read-only\n", encoding="utf-8")
    adapter = TerminalInspectToolAdapter()
    output = adapter.execute(_request(tmp_path, ["cat", "notes.txt"]))
    assert output["status"] == "succeeded", output
    values = {item["name"]: item["value"] for item in output["output"]}
    assert values["stdout"] == "strictly read-only\n"
    assert values["admissionPolicy"] == "readonly-argv-v1"


def test_outside_scope_refused_before_dispatch(tmp_path):
    outside = tmp_path.parent / "outside-test-secret.txt"
    outside.write_text("never-read", encoding="utf-8")
    with pytest.raises(AuthorityViolation):
        TerminalInspectToolAdapter().execute(_request(tmp_path, ["cat", str(outside)]))


@pytest.mark.parametrize("argv", [
    ["git", "config", "--get", "--file=/tmp/outside.ini", "private.canary"],
    ["git", "config", "--get", "--file", "/tmp/outside.ini", "private.canary"],
    ["git", "config", "--global", "--list"],
    ["git", "config", "--system", "--list"],
    ["git", "status", "--short"],
    ["git", "log", "--oneline", "-1"],
])
def test_git_inspection_does_not_cross_unenforced_git_config_scope(tmp_path, argv):
    with pytest.raises(ReadOnlyRefused, match="git-requires-governed-exec"):
        TerminalInspectToolAdapter().execute(_request(tmp_path, argv))


@pytest.mark.parametrize("argv", [
    ["ls", "-LR", "."],
    ["ls", "--dereference", "--recursive", "."],
    ["find", "-L", ".", "-type", "f"],
    ["grep", "-R", "secret", "."],
    ["rg", "--follow", "secret", "."],
    ["du", "-L", "."],
])
def test_recursive_symlink_follow_flags_refuse(tmp_path, argv):
    outside = tmp_path.parent / "out-of-scope-directory"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("secret")
    (tmp_path / "link-outside").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ReadOnlyRefused):
        TerminalInspectToolAdapter().execute(_request(tmp_path, argv))
