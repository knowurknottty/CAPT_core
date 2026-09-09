"""Transactional CAPT reservations for Cloudflare free-tier budgets."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from capt_runtime.errors import AuthorityViolation

from .cloudflare_ai_catalog import CloudflareAIModelCatalogSnapshot
from .cloudflare_free_router import (
    CloudflareFreeEstimate,
    CloudflareFreeTierRouter,
    CloudflareWorkClass,
)
from .cloudflare_free_tier import CloudflareUsageSnapshot


def _digest(
    work_class: str,
    estimate: CloudflareFreeEstimate,
    day: date,
    catalog_digest: str | None = None,
) -> str:
    payload = {
        "workClass": work_class,
        "estimate": asdict(estimate),
        "day": day.isoformat(),
        "catalogDigest": catalog_digest,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class CloudflareUsageLedger:
    def __init__(self, path: str | Path, *, router: CloudflareFreeTierRouter | None = None) -> None:
        self.router = router or CloudflareFreeTierRouter.default()
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS cloudflare_usage_reservations (
                    operation_id TEXT PRIMARY KEY,
                    day TEXT NOT NULL,
                    work_class TEXT NOT NULL,
                    estimate_json TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    release_reason TEXT
                )"""
            )
            self._db.commit()

    @staticmethod
    def _usage_from_rows(rows) -> CloudflareUsageSnapshot:
        totals = {
            "workers_requests": 0,
            "queue_operations": 0,
            "browser_seconds": 0,
            "workers_ai_neurons": 0,
            "d1_rows_read": 0,
            "d1_rows_written": 0,
        }
        for row in rows:
            if row["state"] == "released":
                continue
            estimate = json.loads(row["estimate_json"])
            totals["workers_requests"] += int(estimate["worker_requests"])
            totals["queue_operations"] += int(estimate["queue_operations"])
            totals["browser_seconds"] += int(estimate["browser_seconds"])
            totals["workers_ai_neurons"] += int(estimate["ai_neurons"])
            totals["d1_rows_read"] += int(estimate["d1_rows_read"])
            totals["d1_rows_written"] += int(estimate["d1_rows_written"])
        return CloudflareUsageSnapshot(**totals)

    def _snapshot_unlocked(self, day: date) -> CloudflareUsageSnapshot:
        rows = self._db.execute(
            "SELECT estimate_json, state FROM cloudflare_usage_reservations WHERE day=?",
            (day.isoformat(),),
        ).fetchall()
        return self._usage_from_rows(rows)

    def snapshot(self, *, day: date) -> CloudflareUsageSnapshot:
        with self._lock:
            return self._snapshot_unlocked(day)

    def reserve(
        self,
        operation_id: str,
        work_class: str,
        estimate: CloudflareFreeEstimate,
        *,
        day: date,
        ai_catalog: CloudflareAIModelCatalogSnapshot | None = None,
        at: datetime | None = None,
    ) -> dict[str, str]:
        if not operation_id:
            raise ValueError("cloudflare_operation_id_required")
        digest = _digest(
            work_class,
            estimate,
            day,
            ai_catalog.source_digest if ai_catalog is not None else None,
        )
        estimate_json = json.dumps(asdict(estimate), sort_keys=True, separators=(",", ":"))
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                existing = self._db.execute(
                    "SELECT * FROM cloudflare_usage_reservations WHERE operation_id=?",
                    (operation_id,),
                ).fetchone()
                if existing is not None:
                    if existing["request_digest"] != digest:
                        raise AuthorityViolation("CLOUDFLARE_USAGE_RESERVATION_DIGEST_MISMATCH")
                    self._db.commit()
                    return {
                        "operationId": operation_id,
                        "state": existing["state"],
                        "requestDigest": digest,
                    }
                usage = self._snapshot_unlocked(day)
                try:
                    work = CloudflareWorkClass(work_class)
                except ValueError as exc:
                    raise ValueError(f"cloudflare_work_class_invalid:{work_class}") from exc
                self.router.route(
                    work,
                    estimate,
                    usage=usage,
                    ai_catalog=ai_catalog,
                    at=at,
                )
                self._db.execute(
                    "INSERT INTO cloudflare_usage_reservations(operation_id,day,work_class,estimate_json,request_digest,state) VALUES(?,?,?,?,?,?)",
                    (operation_id, day.isoformat(), work_class, estimate_json, digest, "reserved"),
                )
                self._db.commit()
                return {"operationId": operation_id, "state": "reserved", "requestDigest": digest}
            except Exception:
                self._db.rollback()
                raise

    def release(self, operation_id: str, *, reason: str) -> None:
        if not reason:
            raise ValueError("cloudflare_release_reason_required")
        with self._lock:
            row = self._db.execute(
                "SELECT state FROM cloudflare_usage_reservations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(operation_id)
            if row["state"] == "committed":
                raise AuthorityViolation("CLOUDFLARE_COMMITTED_USAGE_CANNOT_BE_RELEASED")
            if row["state"] == "released":
                return
            self._db.execute(
                "UPDATE cloudflare_usage_reservations SET state='released', release_reason=? WHERE operation_id=?",
                (reason, operation_id),
            )
            self._db.commit()

    def commit(self, operation_id: str) -> None:
        with self._lock:
            row = self._db.execute(
                "SELECT state FROM cloudflare_usage_reservations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(operation_id)
            if row["state"] == "released":
                raise AuthorityViolation("CLOUDFLARE_RELEASED_USAGE_CANNOT_BE_COMMITTED")
            if row["state"] == "committed":
                return
            self._db.execute(
                "UPDATE cloudflare_usage_reservations SET state='committed' WHERE operation_id=?",
                (operation_id,),
            )
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()
