from __future__ import annotations

import sys
from pathlib import Path

import pytest

from capt_runtime.errors import AuthorityViolation
from capt_runtime.tools.adapters.code import CodeExecutionAdapter


def _request(root: Path, code: str, **arguments) -> dict:
    typed = [
        {"kind": "string", "name": "code", "value": code},
        {"kind": "path", "name": "cwd", "value": str(arguments.pop("cwd", root))},
    ]
    for name, value in arguments.items():
        typed.append({"kind": "integer", "name": name, "value": value})
    return {
        "toolRequestId": "code-tool-request",
        "toolId": "code.execution",
        "operation": "code.execute_python",
        "arguments": typed,
        "filesystemScope": str(root),
        "backendId": "local",
    }


def _value(result: dict, name: str):
    return next(item["value"] for item in result["output"] if item["name"] == name)


def test_python_code_executes_in_scoped_cwd(tmp_path: Path) -> None:
    result = CodeExecutionAdapter().execute(
        _request(tmp_path, "from pathlib import Path; print(Path.cwd().name)")
    )
    assert result["status"] == "succeeded"
    assert result["exitCode"] == 0
    assert tmp_path.name in _value(result, "stdout")
    assert _value(result, "scriptDigest").startswith("sha256:")
    assert not list(tmp_path.glob(".capt-python-*"))


def test_python_uses_current_interpreter_and_no_shell(tmp_path: Path) -> None:
    result = CodeExecutionAdapter().execute(
        _request(tmp_path, "import sys; print(sys.executable)")
    )
    assert Path(_value(result, "stdout").strip()).resolve() == Path(sys.executable).resolve()


def test_parent_secret_is_not_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAPT_TEST_SECRET_TOKEN", "should-not-leak")
    result = CodeExecutionAdapter().execute(
        _request(tmp_path, "import os; print(os.getenv('CAPT_TEST_SECRET_TOKEN'))")
    )
    assert _value(result, "stdout").strip() == "None"


def test_code_execution_rejects_cwd_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    with pytest.raises(AuthorityViolation):
        CodeExecutionAdapter().execute(
            _request(root, "print('bad')", cwd=outside)
        )


def test_timeout_is_indeterminate_and_temp_script_is_removed(tmp_path: Path) -> None:
    result = CodeExecutionAdapter().execute(
        _request(tmp_path, "import time; time.sleep(30)", timeout_ms=100)
    )
    assert result["status"] == "indeterminate"
    assert _value(result, "timedOut") is True
    assert _value(result, "cancelled") is False
    assert not list(tmp_path.glob(".capt-python-*"))


def test_output_limits_are_inherited_from_local_backend(tmp_path: Path) -> None:
    result = CodeExecutionAdapter().execute(
        _request(
            tmp_path,
            "import sys; sys.stdout.write('x'*200000); sys.stderr.write('y'*150000)",
            stdout_limit_bytes=4096,
            stderr_limit_bytes=2048,
        )
    )
    assert result["status"] == "succeeded"
    assert len(_value(result, "stdout").encode()) <= 4096
    assert len(_value(result, "stderr").encode()) <= 2048
    assert _value(result, "stdoutTotalBytes") >= 200000
    assert _value(result, "stderrTotalBytes") >= 150000
    assert _value(result, "stdoutTruncated") is True
    assert _value(result, "stderrTruncated") is True


def test_nonzero_exit_reports_real_exit_code(tmp_path: Path) -> None:
    result = CodeExecutionAdapter().execute(
        _request(tmp_path, "import sys; print('before'); sys.exit(7)")
    )
    assert result["status"] == "failed"
    assert result["exitCode"] == 7
    assert _value(result, "stdout").strip() == "before"


def test_unknown_or_duplicate_arguments_fail_closed(tmp_path: Path) -> None:
    adapter = CodeExecutionAdapter()
    request = _request(tmp_path, "print('x')")
    request["arguments"].append({"kind": "string", "name": "bogus", "value": "x"})
    with pytest.raises(ValueError, match="unknown argument"):
        adapter.execute(request)

    request = _request(tmp_path, "print('x')")
    request["arguments"].append({"kind": "string", "name": "code", "value": "print(2)"})
    with pytest.raises(ValueError, match="duplicate argument"):
        adapter.execute(request)


def test_python_can_persist_local_mutation_inside_admitted_cwd(tmp_path: Path) -> None:
    marker = tmp_path / "marker.txt"
    result = CodeExecutionAdapter().execute(
        _request(
            tmp_path,
            "from pathlib import Path; Path('marker.txt').write_text('CAPT'); print('written')",
        )
    )
    assert result["status"] == "succeeded"
    assert marker.read_text() == "CAPT"
    assert _value(result, "stdout").strip() == "written"
