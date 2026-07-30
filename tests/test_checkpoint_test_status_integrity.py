"""CHECKPOINT.md must not record a failed pytest run as passing evidence.

Regression coverage for the recovered security candidate
`release-evidence:capt_solo/workspace.py:509`.

Original defect: `generate_checkpoint` scanned pytest output for the first line
containing "passed" or "failed" and stored it verbatim, without consulting the
process return code. A run that exited nonzero while printing a line such as
"999 passed" would be recorded as `- **tests_status**: 999 passed`, preserving
false verification evidence in the release authority document — directly
contradicting the function's own docstring promise that it "never fabricates
test results".

Fixed behaviour: a summary line is only recorded as-is when pytest exited 0.
A nonzero exit is labelled FAILED with the exit code.
"""

from __future__ import annotations

import subprocess

import pytest

from capt_solo import workspace


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_pytest_result(monkeypatch, result: _FakeCompleted):
    """Intercept only the pytest invocation; pass git calls through."""
    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "pytest" in list(cmd):
            return result
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(workspace.subprocess, "run", fake_run)


def test_failed_pytest_run_is_not_recorded_as_passing(monkeypatch):
    """A nonzero exit must never yield a bare passing summary line."""
    _patch_pytest_result(
        monkeypatch, _FakeCompleted(returncode=1, stdout="999 passed\n1 failed\n")
    )

    content = workspace.generate_checkpoint()

    assert "- **tests_status**: 999 passed" not in content, (
        "failed pytest run was recorded as passing evidence"
    )
    assert "FAILED" in content, "a nonzero pytest exit must be labelled FAILED"
    assert "exit 1" in content, "the exit code must be disclosed"


def test_nonzero_exit_without_summary_line_is_labelled_failed(monkeypatch):
    _patch_pytest_result(
        monkeypatch, _FakeCompleted(returncode=2, stdout="INTERNALERROR\n")
    )

    content = workspace.generate_checkpoint()

    assert "FAILED" in content
    assert "exit 2" in content


def test_successful_run_records_the_summary_line(monkeypatch):
    """The honest path is unchanged: exit 0 records the real summary."""
    _patch_pytest_result(
        monkeypatch, _FakeCompleted(returncode=0, stdout="687 passed in 16.38s\n")
    )

    content = workspace.generate_checkpoint()

    assert "687 passed" in content
    assert "FAILED" not in content.split("tests_status")[1][:80]


def test_docstring_promise_is_honoured():
    """The function documents that it never fabricates test results."""
    assert "Never fabricates test results" in (workspace.generate_checkpoint.__doc__ or "")
