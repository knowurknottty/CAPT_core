"""Durable local Cognitive Transaction Protocol journal.

The journal is append-only JSONL under the CAPT runtime home. It provides
recoverable begin/validate/note/commit/abort semantics and immutable receipts.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from capt_solo.core.config import ctp_journal_dir, ensure_dirs
from capt_solo.core.errors import IdempotencyError, IntegrityError, TransactionError


@dataclass(frozen=True)
class Receipt:
    tx_id: str
    status: str
    correlation_id: Optional[str]
    idempotency_key: Optional[str]
    created_at: float
    finalized_at: float
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CTPRuntime:
    """Small append-only local transaction journal."""

    def __init__(self, journal_path: Optional[Path] = None) -> None:
        ensure_dirs()
        self._path = Path(journal_path) if journal_path else ctp_journal_dir() / "journal.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self._path.is_symlink():
            raise IntegrityError("CTP journal path must not be a symlink")
        self._path.touch(exist_ok=True, mode=0o600)
        if os.name == "posix":
            os.chmod(self._path, 0o600)
        self._lock = threading.RLock()
        self._events: List[Dict[str, Any]] = []
        self._transactions: Dict[str, Dict[str, Any]] = {}
        self._receipts: Dict[str, Receipt] = {}
        self._finalized_keys: Dict[str, str] = {}
        self._closed = False
        self._load()

    def _load(self) -> None:
        with self._lock:
            try:
                lines = self._path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                raise IntegrityError(f"unable to read CTP journal: {exc}") from exc
            for number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except (TypeError, ValueError) as exc:
                    raise IntegrityError(f"invalid CTP journal record at line {number}") from exc
                if not isinstance(event, dict) or not isinstance(event.get("tx_id"), str):
                    raise IntegrityError(f"invalid CTP journal record at line {number}")
                self._apply(event)
                self._events.append(event)

    def _apply(self, event: Dict[str, Any]) -> None:
        tx_id = event["tx_id"]
        kind = event.get("type")
        if kind == "begin":
            self._transactions[tx_id] = {
                "tx_id": tx_id,
                "status": "pending",
                "correlation_id": event.get("correlation_id"),
                "idempotency_key": event.get("idempotency_key"),
                "meta": dict(event.get("meta") or {}),
                "created_at": float(event.get("timestamp", 0.0)),
            }
        elif kind in {"commit", "abort"}:
            tx = self._transactions.get(tx_id)
            if tx is None:
                raise IntegrityError(f"finalization references unknown transaction {tx_id}")
            status = "committed" if kind == "commit" else "aborted"
            tx["status"] = status
            receipt = Receipt(
                tx_id=tx_id,
                status=status,
                correlation_id=tx.get("correlation_id"),
                idempotency_key=tx.get("idempotency_key"),
                created_at=float(tx.get("created_at", 0.0)),
                finalized_at=float(event.get("timestamp", 0.0)),
                meta=dict(tx.get("meta") or {}),
            )
            self._receipts[tx_id] = receipt
            key = tx.get("idempotency_key")
            if key:
                self._finalized_keys[key] = tx_id

    def _append(self, event: Dict[str, Any]) -> None:
        if self._closed:
            raise TransactionError("CTP runtime is closed")
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            try:
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError as exc:
                raise TransactionError(f"unable to append CTP journal: {exc}") from exc
            self._apply(event)
            self._events.append(event)

    def begin(
        self,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self._lock:
            if idempotency_key and idempotency_key in self._finalized_keys:
                raise IdempotencyError(f"idempotency key already finalized: {idempotency_key}")
            tx_id = uuid.uuid4().hex
            self._append(
                {
                    "type": "begin",
                    "tx_id": tx_id,
                    "timestamp": time.time(),
                    "correlation_id": correlation_id,
                    "idempotency_key": idempotency_key,
                    "meta": dict(meta or {}),
                }
            )
            return tx_id

    def validate(self, tx_id: str, result: Any) -> bool:
        self._require_pending(tx_id)
        ok = bool(result.get("ok")) if isinstance(result, dict) and "ok" in result else bool(result)
        self._append(
            {"type": "validate", "tx_id": tx_id, "timestamp": time.time(), "ok": ok}
        )
        return ok

    def note(self, tx_id: str, note: str) -> None:
        self._require_pending(tx_id)
        self._append(
            {"type": "note", "tx_id": tx_id, "timestamp": time.time(), "note": str(note)}
        )

    def commit(self, tx_id: str) -> Receipt:
        self._require_pending(tx_id)
        self._append({"type": "commit", "tx_id": tx_id, "timestamp": time.time()})
        return self._receipts[tx_id]

    def abort(self, tx_id: str) -> Receipt:
        self._require_pending(tx_id)
        self._append({"type": "abort", "tx_id": tx_id, "timestamp": time.time()})
        return self._receipts[tx_id]

    def get_receipt(self, tx_id: str) -> Receipt:
        try:
            return self._receipts[tx_id]
        except KeyError as exc:
            raise TransactionError(f"transaction has no receipt: {tx_id}") from exc

    def recover(self) -> List[str]:
        return [tx_id for tx_id, tx in self._transactions.items() if tx.get("status") == "pending"]

    def audit_trail(self, tx_id: str) -> List[Dict[str, Any]]:
        if tx_id not in self._transactions:
            raise TransactionError(f"unknown transaction: {tx_id}")
        return [dict(event) for event in self._events if event.get("tx_id") == tx_id]

    def integrity_check(self) -> bool:
        try:
            probe = CTPRuntime(self._path)
            probe.close()
            return True
        except Exception:
            return False

    def _exists(self, tx_id: str) -> bool:
        return tx_id in self._transactions

    def _require_pending(self, tx_id: str) -> Dict[str, Any]:
        tx = self._transactions.get(tx_id)
        if tx is None:
            raise TransactionError(f"unknown transaction: {tx_id}")
        if tx.get("status") != "pending":
            raise TransactionError(f"transaction already finalized: {tx_id}")
        return tx

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> "CTPRuntime":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
