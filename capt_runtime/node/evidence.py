"""Persistent bounded evidence spool for CAPT Node RPC results."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

INLINE_EVIDENCE_BYTES = 64 * 1024
EVIDENCE_PREVIEW_BYTES = 4 * 1024
MAX_EVIDENCE_CHUNK_BYTES = 64 * 1024
_REF_PREFIX = "node-evidence://"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _token(operation_id: str, label: str) -> str:
    raw = f"{operation_id}\x00{label}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class NodeEvidenceSpool:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass

    def _paths(self, token: str) -> tuple[Path, Path]:
        if len(token) != 64 or any(ch not in "0123456789abcdef" for ch in token):
            raise ValueError("evidence_ref_invalid")
        return self.root / f"{token}.bin", self.root / f"{token}.json"

    def capture_text(
        self,
        *,
        operation_id: str,
        label: str,
        text: str,
        total_bytes: int,
        source_truncated: bool,
    ) -> dict[str, Any]:
        data = text.encode("utf-8")
        digest = _sha256(data)
        common = {
            "sha256": digest,
            "capturedBytes": len(data),
            "totalBytes": total_bytes,
            "sourceTruncated": source_truncated,
        }
        if len(data) <= INLINE_EVIDENCE_BYTES:
            return {**common, "storage": "inline", "inline": text}

        token = _token(operation_id, label)
        data_path, meta_path = self._paths(token)
        data_path.write_bytes(data)
        meta = {
            "operationId": operation_id,
            "label": label,
            **common,
        }
        meta_path.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
        for path in (data_path, meta_path):
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        preview = data[:EVIDENCE_PREVIEW_BYTES].decode("utf-8", errors="replace")
        return {
            **common,
            "storage": "local_spool",
            "ref": _REF_PREFIX + token,
            "preview": preview,
        }

    def read(
        self,
        *,
        operation_id: str,
        ref: str,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
            raise ValueError("evidence_ref_invalid")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("evidence_offset_invalid")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("evidence_limit_invalid")
        if limit < 1 or limit > MAX_EVIDENCE_CHUNK_BYTES:
            raise ValueError("evidence_limit_out_of_range")
        token = ref[len(_REF_PREFIX):]
        data_path, meta_path = self._paths(token)
        if not data_path.is_file() or not meta_path.is_file():
            raise KeyError("evidence_ref_not_found")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("operationId") != operation_id:
            raise PermissionError("evidence_operation_mismatch")
        total = data_path.stat().st_size
        if offset > total:
            raise ValueError("evidence_offset_out_of_range")
        with data_path.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read(limit)
        next_offset = offset + len(chunk)
        return {
            "ref": ref,
            "operationId": operation_id,
            "label": meta.get("label"),
            "offset": offset,
            "nextOffset": next_offset,
            "totalBytes": total,
            "sha256": meta.get("sha256"),
            "dataBase64": base64.b64encode(chunk).decode("ascii"),
            "eof": next_offset >= total,
        }
