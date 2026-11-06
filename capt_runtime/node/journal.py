from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .integrity import GenericStateViolation, OperationDigestMismatch
from .types import (
    NodeOperationRequest,
    NodeOperationResult,
    NodeOperationState,
    canonical_request_digest,
)

_TERMINAL = {
    NodeOperationState.CLOSED.value,
    NodeOperationState.REJECTED.value,
    NodeOperationState.FAILED.value,
    NodeOperationState.CANCELLED.value,
    NodeOperationState.REVOKED.value,
    NodeOperationState.TIMED_OUT.value,
    NodeOperationState.BLOCKED_HUMAN.value,
    NodeOperationState.QUARANTINED.value,
}


class NodeOperationJournal:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS node_operations (
                    operation_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    detail TEXT,
                    controller_id TEXT,
                    result_json TEXT
                )"""
            )
            columns = {row["name"] for row in self._db.execute("PRAGMA table_info(node_operations)")}
            if "controller_id" not in columns:
                self._db.execute("ALTER TABLE node_operations ADD COLUMN controller_id TEXT")
            if "result_json" not in columns:
                self._db.execute("ALTER TABLE node_operations ADD COLUMN result_json TEXT")
            self._db.commit()

    def _row_unlocked(self, operation_id: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT operation_id, request_digest, state, detail, controller_id, result_json "
            "FROM node_operations WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
        if row is None:
            return None
        result = {
            "operationId": row["operation_id"],
            "requestDigest": row["request_digest"],
            "state": row["state"],
            "detail": row["detail"],
        }
        if row["result_json"]:
            stored = json.loads(row["result_json"])
            if not isinstance(stored, dict):
                raise ValueError("node_result_journal_invalid")
            result.update(stored)
            result["operationId"] = row["operation_id"]
            result["requestDigest"] = row["request_digest"]
            result["state"] = row["state"]
            result["detail"] = row["detail"]
        return result

    def _row(self, operation_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._row_unlocked(operation_id)

    def prepare(self, request: NodeOperationRequest) -> dict[str, Any]:
        digest = canonical_request_digest(request)
        with self._lock:
            existing = self._row_unlocked(request.operation_id)
            if existing is not None:
                if existing["requestDigest"] != digest:
                    self._db.execute(
                        "UPDATE node_operations SET state=?, detail=? WHERE operation_id=?",
                        (
                            NodeOperationState.QUARANTINED.value,
                            "operation_digest_mismatch",
                            request.operation_id,
                        ),
                    )
                    self._db.commit()
                    raise OperationDigestMismatch(
                        "operation_digest_mismatch", operation_id=request.operation_id
                    )
                return existing
            self._db.execute(
                "INSERT INTO node_operations("
                "operation_id, request_digest, state, detail, controller_id, result_json"
                ") VALUES(?,?,?,NULL,?,NULL)",
                (
                    request.operation_id,
                    digest,
                    NodeOperationState.PREPARED.value,
                    request.capability.controller_id,
                ),
            )
            self._db.commit()
            return self._row_unlocked(request.operation_id) or {}

    def record_state(
        self,
        operation_id: str,
        state: NodeOperationState | str,
        detail: str | None = None,
    ) -> dict[str, Any]:
        try:
            normalized = state if isinstance(state, NodeOperationState) else NodeOperationState(state)
        except ValueError as exc:
            raise GenericStateViolation(
                f"untyped_node_state:{state}", operation_id=operation_id
            ) from exc
        with self._lock:
            if self._row_unlocked(operation_id) is None:
                raise KeyError(operation_id)
            self._db.execute(
                "UPDATE node_operations SET state=?, detail=? WHERE operation_id=?",
                (normalized.value, detail, operation_id),
            )
            self._db.commit()
            return self._row_unlocked(operation_id) or {}

    def record_result(
        self, operation_id: str, result: NodeOperationResult
    ) -> dict[str, Any]:
        payload = {
            "evidence": [dict(item) for item in result.evidence],
            "exitCode": result.exit_code,
            "specificReason": result.specific_reason,
        }
        with self._lock:
            if self._row_unlocked(operation_id) is None:
                raise KeyError(operation_id)
            self._db.execute(
                "UPDATE node_operations SET state=?, detail=?, result_json=? "
                "WHERE operation_id=?",
                (
                    result.state.value,
                    result.detail,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    operation_id,
                ),
            )
            self._db.commit()
            return self._row_unlocked(operation_id) or {}

    def controller_id(self, operation_id: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT controller_id FROM node_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(operation_id)
            value = row["controller_id"]
            return str(value) if value is not None else None

    def lookup(self, operation_id: str) -> dict[str, Any] | None:
        return self._row(operation_id)

    def reconcile_candidates(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT operation_id FROM node_operations ORDER BY operation_id"
            ).fetchall()
            return [
                row
                for item in rows
                if (row := self._row_unlocked(item["operation_id"])) is not None
                and row["state"] not in _TERMINAL
            ]

    def close(self) -> None:
        with self._lock:
            self._db.close()
