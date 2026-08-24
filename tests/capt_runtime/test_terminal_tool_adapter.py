from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.adapters.terminal import TerminalToolAdapter


def _request(root: Path, argv: list[str], **arguments) -> dict:
    typed = [
        {"kind": "string", "name": "argv", "value": json.dumps(argv)},
        {"kind": "path", "name": "cwd", "value": str(arguments.pop("cwd", root))},
    ]
    for name, value in arguments.items():
        typed.append({"kind": "integer", "name": name, "value": value})
    return {
        "toolRequestId": "terminal-tool-request",
        "toolId": "terminal.local",
        "operation": "terminal.exec",
        "arguments": typed,
        "filesystemScope": str(root),
        "backendId": "local",
    }


def _value(result: dict, name: str):
    return next(item["value"] for item in result["output"] if item["name"] == name)


def test_terminal_executes_explicit_argv_in_scoped_cwd(tmp_path: Path) -> None:
    result = TerminalToolAdapter().execute(
        _request(tmp_path, [sys.executable, "-c", "from pathlib import Path; print(Path.cwd().name)"])
    )
    assert result["status"] == "succeeded"
    assert result["exitCode"] == 0
    assert tmp_path.name in _value(result, "stdout")
    assert _value(result, "pid") > 0
    assert _value(result, "processGroupId") > 0


def test_terminal_never_interpolates_shell_syntax(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-exist"
    literal = f"$(touch {marker})"
    result = TerminalToolAdapter().execute(
        _request(tmp_path, ["/bin/echo", literal])
    )
    assert result["status"] == "succeeded"
    assert literal in _value(result, "stdout")
    assert not marker.exists()


def test_terminal_can_persist_local_mutation_inside_admitted_cwd(tmp_path: Path) -> None:
    marker = tmp_path / "marker.txt"
    result = TerminalToolAdapter().execute(
        _request(
            tmp_path,
            [sys.executable, "-c", "from pathlib import Path; Path('marker.txt').write_text('CAPT')"],
        )
    )
    assert result["status"] == "succeeded"
    assert marker.read_text() == "CAPT"


def test_terminal_parent_secret_is_not_inherited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAPT_TERMINAL_SECRET", "must-not-leak")
    result = TerminalToolAdapter().execute(
        _request(
            tmp_path,
            [sys.executable, "-c", "import os; print(os.getenv('CAPT_TERMINAL_SECRET'))"],
        )
    )
    assert _value(result, "stdout").strip() == "None"


def test_terminal_rejects_cwd_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    with pytest.raises(AuthorityViolation):
        TerminalToolAdapter().execute(
            _request(root, [sys.executable, "-c", "print('bad')"], cwd=outside)
        )


def test_terminal_timeout_is_indeterminate(tmp_path: Path) -> None:
    result = TerminalToolAdapter().execute(
        _request(
            tmp_path,
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout_ms=100,
        )
    )
    assert result["status"] == "indeterminate"
    assert _value(result, "timedOut") is True
    assert _value(result, "cancelled") is False


def test_terminal_output_is_bounded(tmp_path: Path) -> None:
    result = TerminalToolAdapter().execute(
        _request(
            tmp_path,
            [sys.executable, "-c", "import sys; sys.stdout.write('x'*100000); sys.stderr.write('y'*80000)"],
            stdout_limit_bytes=4096,
            stderr_limit_bytes=2048,
        )
    )
    assert result["status"] == "succeeded"
    assert len(_value(result, "stdout").encode()) <= 4096
    assert len(_value(result, "stderr").encode()) <= 2048
    assert _value(result, "stdoutTotalBytes") >= 100000
    assert _value(result, "stderrTotalBytes") >= 80000
    assert _value(result, "stdoutTruncated") is True
    assert _value(result, "stderrTruncated") is True


@pytest.mark.parametrize(
    "argv_value, match",
    [
        ("not-json", "valid JSON"),
        (json.dumps([]), "must not be empty"),
        (json.dumps(["echo", 7]), "strings"),
        (json.dumps("echo ok"), "JSON array"),
    ],
)
def test_terminal_rejects_invalid_argv(tmp_path: Path, argv_value: str, match: str) -> None:
    request = _request(tmp_path, ["echo", "ok"])
    request["arguments"][0]["value"] = argv_value
    with pytest.raises(ValueError, match=match):
        TerminalToolAdapter().execute(request)


def test_terminal_unknown_and_duplicate_arguments_fail_closed(tmp_path: Path) -> None:
    adapter = TerminalToolAdapter()
    request = _request(tmp_path, ["/bin/echo", "ok"])
    request["arguments"].append({"kind": "string", "name": "bogus", "value": "x"})
    with pytest.raises(ValueError, match="unknown argument"):
        adapter.execute(request)

    request = _request(tmp_path, ["/bin/echo", "ok"])
    request["arguments"].append({"kind": "string", "name": "argv", "value": "[]"})
    with pytest.raises(ValueError, match="duplicate argument"):
        adapter.execute(request)
