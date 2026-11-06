from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from capt_runtime.tools.backends.local import LocalProcessBackend, LocalProcessRequest

from .evidence import NodeEvidenceSpool
from .journal import NodeOperationJournal
from .types import NodeOperationRequest, NodeOperationResult, NodeOperationState
from .unix import file_digest, scoped_path, system_telemetry


def _capture_fields(prefix: str, capture: dict[str, object]) -> dict[str, object]:
    fields: dict[str, object] = {
        f"{prefix}Storage": capture["storage"],
        f"{prefix}Sha256": capture["sha256"],
        f"{prefix}CapturedBytes": capture["capturedBytes"],
        f"{prefix}TotalBytes": capture["totalBytes"],
        f"{prefix}Truncated": capture["sourceTruncated"],
    }
    if capture["storage"] == "inline":
        fields[prefix] = capture["inline"]
    else:
        fields[f"{prefix}Ref"] = capture["ref"]
        fields[f"{prefix}Preview"] = capture["preview"]
    return fields


class NodeExecutor:
    def __init__(
        self,
        node_id: str,
        journal: NodeOperationJournal,
        *,
        now: Callable[[], datetime] | None = None,
        process_backend: LocalProcessBackend | None = None,
        evidence_spool: NodeEvidenceSpool | None = None,
    ) -> None:
        self.node_id = node_id
        self.journal = journal
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.process_backend = process_backend or LocalProcessBackend()
        if evidence_spool is None:
            if journal.path == ":memory:":
                root = Path(tempfile.mkdtemp(prefix="capt-node-evidence-"))
            else:
                journal_path = Path(journal.path)
                root = journal_path.parent / f"{journal_path.name}.evidence"
            evidence_spool = NodeEvidenceSpool(root)
        self.evidence_spool = evidence_spool

    def execute(self, request: NodeOperationRequest, *, controller_id: str) -> NodeOperationResult:
        request.capability.require_authorized(
            request.operation,
            node_id=self.node_id,
            controller_id=controller_id,
            at=self.now(),
        )
        self.journal.prepare(request)
        self.journal.record_state(request.operation_id, NodeOperationState.EXECUTING)
        try:
            result = self._dispatch(request)
        except Exception:
            self.journal.record_state(request.operation_id, NodeOperationState.FAILED)
            raise
        self.journal.record_result(request.operation_id, result)
        return result

    def _dispatch(self, request: NodeOperationRequest) -> NodeOperationResult:
        if request.operation == "shell.exec":
            argv = request.arguments.get("argv")
            cwd = request.arguments.get("cwd")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
                raise ValueError("shell_argv_invalid")
            if not isinstance(cwd, str):
                raise ValueError("shell_cwd_invalid")
            cwd_path = scoped_path(request.capability.filesystem_roots, cwd)
            root = next(
                Path(root).resolve()
                for root in request.capability.filesystem_roots
                if cwd_path.is_relative_to(Path(root).resolve())
            )
            timeout_ms = request.arguments.get("timeout_ms", 30_000)
            if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
                raise ValueError("shell_timeout_ms_invalid")
            if timeout_ms < 1 or timeout_ms > 3_600_000:
                raise ValueError("shell_timeout_ms_out_of_range")
            result = self.process_backend.execute(
                LocalProcessRequest(
                    argv=tuple(argv),
                    cwd=cwd_path,
                    filesystem_root=root,
                    timeout_seconds=timeout_ms / 1000.0,
                )
            )
            if result.timed_out:
                state = NodeOperationState.TIMED_OUT
            elif result.cancelled:
                state = NodeOperationState.CANCELLED
            else:
                state = NodeOperationState.CLOSED if result.exit_code == 0 else NodeOperationState.FAILED
            stdout = self.evidence_spool.capture_text(
                operation_id=request.operation_id,
                label="stdout",
                text=result.stdout,
                total_bytes=result.stdout_total_bytes,
                source_truncated=result.stdout_truncated,
            )
            stderr = self.evidence_spool.capture_text(
                operation_id=request.operation_id,
                label="stderr",
                text=result.stderr,
                total_bytes=result.stderr_total_bytes,
                source_truncated=result.stderr_truncated,
            )
            process_evidence = {
                "kind": "process",
                "pid": result.pid,
                "processGroupId": result.process_group_id,
                "startedAt": result.started_at,
                "completedAt": result.completed_at,
                "timedOut": result.timed_out,
                "cancelled": result.cancelled,
                **_capture_fields("stdout", stdout),
                **_capture_fields("stderr", stderr),
            }
            evidence = (process_evidence,)
            reason = (
                "process_timeout" if result.timed_out else
                "process_cancelled" if result.cancelled else
                "process_exit_nonzero" if result.exit_code != 0 else None
            )
            return NodeOperationResult(
                request.operation_id, state, evidence, result.exit_code, specific_reason=reason
            )

        if request.operation in {"filesystem.read", "filesystem.write"}:
            raw_path = request.arguments.get("path")
            if not isinstance(raw_path, str):
                raise ValueError("filesystem_path_invalid")
            path = scoped_path(request.capability.filesystem_roots, raw_path)
            if request.operation == "filesystem.read":
                content = path.read_text(encoding="utf-8")
                size = path.stat().st_size
                captured = self.evidence_spool.capture_text(
                    operation_id=request.operation_id,
                    label="content",
                    text=content,
                    total_bytes=size,
                    source_truncated=False,
                )
                file_evidence = {
                    "kind": "file_read",
                    "path": str(path),
                    "sha256": file_digest(path),
                    "bytes": size,
                    **_capture_fields("content", captured),
                }
                return NodeOperationResult(
                    request.operation_id, NodeOperationState.CLOSED, (file_evidence,)
                )
            content = request.arguments.get("content")
            if not isinstance(content, str):
                raise ValueError("filesystem_content_invalid")
            before = path.exists()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            evidence = ({
                "kind": "file_write", "path": str(path), "existedBefore": before,
                "sha256": file_digest(path), "bytes": path.stat().st_size,
            },)
            return NodeOperationResult(request.operation_id, NodeOperationState.CLOSED, evidence)

        if request.operation == "system.telemetry":
            return NodeOperationResult(
                request.operation_id,
                NodeOperationState.CLOSED,
                (system_telemetry(),),
            )

        if request.operation == "process.inspect":
            pid = request.arguments.get("pid")
            if not isinstance(pid, int) or pid <= 0:
                raise ValueError("process_pid_invalid")
            try:
                os.kill(pid, 0)
                exists = True
            except ProcessLookupError:
                exists = False
            evidence = ({"kind": "process_inspect", "pid": pid, "exists": exists},)
            return NodeOperationResult(request.operation_id, NodeOperationState.CLOSED, evidence)

        raise PermissionError("operation_not_implemented")
