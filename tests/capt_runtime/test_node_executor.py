from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from capt_runtime.node.executor import NodeExecutor
from capt_runtime.node.journal import NodeOperationJournal
from capt_runtime.node.types import (
    NodeOperationRequest,
    NodeOperationState,
    OperationCapability,
)

NOW = datetime(2026, 9, 8, 20, 30, tzinfo=timezone.utc)


def _request(root, operation, arguments, *, expires=None):
    cap = OperationCapability(
        capability_id="cap-1", bot_id="bot-1", mission_id="m-1", task_id="t-1",
        controller_id="controller-1", node_id="node-1",
        permitted_operations=frozenset({operation}), filesystem_roots=(str(root),),
        issued_at=NOW, expires_at=expires or NOW + timedelta(minutes=5),
    )
    return NodeOperationRequest(
        operation_id=f"op-{operation}", capability=cap, operation=operation,
        arguments=arguments, issued_at=NOW,
    )


def test_shell_exec_uses_explicit_argv_and_records_specific_evidence(tmp_path):
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    executor = NodeExecutor("node-1", journal, now=lambda: NOW)
    request = _request(tmp_path, "shell.exec", {"argv": ["printf", "hello"], "cwd": str(tmp_path)})
    result = executor.execute(request, controller_id="controller-1")
    assert result.state is NodeOperationState.CLOSED
    assert result.exit_code == 0
    assert any(e["kind"] == "process" and e["stdout"] == "hello" for e in result.evidence)

def test_filesystem_write_cannot_escape_capability_root(tmp_path):
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    executor = NodeExecutor("node-1", journal, now=lambda: NOW)
    request = _request(tmp_path, "filesystem.write", {"path": str(tmp_path.parent / "escape.txt"), "content": "no"})
    with pytest.raises(PermissionError, match="filesystem_scope_violation"):
        executor.execute(request, controller_id="controller-1")


def test_expired_capability_is_rejected_before_execution(tmp_path):
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    executor = NodeExecutor("node-1", journal, now=lambda: NOW)
    request = _request(
        tmp_path, "filesystem.write", {"path": str(tmp_path / "x.txt"), "content": "no"},
        expires=NOW,
    )
    with pytest.raises(PermissionError, match="capability_expired"):
        executor.execute(request, controller_id="controller-1")
    assert not (tmp_path / "x.txt").exists()


def test_filesystem_read_write_and_telemetry_are_typed(tmp_path):
    journal = NodeOperationJournal(tmp_path / "journal.sqlite")
    executor = NodeExecutor("node-1", journal, now=lambda: NOW)
    write = _request(tmp_path, "filesystem.write", {"path": str(tmp_path / "x.txt"), "content": "abc"})
    assert executor.execute(write, controller_id="controller-1").state is NodeOperationState.CLOSED
    read = _request(tmp_path, "filesystem.read", {"path": str(tmp_path / "x.txt")})
    result = executor.execute(read, controller_id="controller-1")
    assert any(e["kind"] == "file_read" and e["content"] == "abc" for e in result.evidence)


def test_shell_timeout_is_typed_and_request_bound(tmp_path):
    journal = NodeOperationJournal(tmp_path / "journal-timeout.sqlite")
    executor = NodeExecutor("node-1", journal, now=lambda: NOW)
    request = _request(
        tmp_path,
        "shell.exec",
        {
            "argv": ["python3", "-c", "import time; time.sleep(0.2)"],
            "cwd": str(tmp_path),
            "timeout_ms": 20,
        },
    )
    result = executor.execute(request, controller_id="controller-1")
    assert result.state is NodeOperationState.TIMED_OUT
    assert any(e["kind"] == "process" and e["timedOut"] is True for e in result.evidence)
