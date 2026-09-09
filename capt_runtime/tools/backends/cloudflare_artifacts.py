"""Persistent bounded binary artifact spool for Cloudflare Browser Run."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .cloudflare_native import CloudflareBrowserAction

MAX_CLOUDFLARE_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_CLOUDFLARE_ARTIFACT_CHUNK_BYTES = 64 * 1024
_REF_PREFIX = "cloudflare-artifact://"


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _token(operation_id: str, action: str, digest: str) -> str:
    raw = f"{operation_id}\x00{action}\x00{digest}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class CloudflareBinaryArtifactSpool:
    def __init__(self, root: str | Path, *, max_bytes: int = MAX_CLOUDFLARE_ARTIFACT_BYTES) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
            raise ValueError("cloudflare_artifact_max_bytes_invalid")
        self.root = Path(root)
        self.max_bytes = max_bytes
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass

    def _paths(self, token: str) -> tuple[Path, Path]:
        if len(token) != 64 or any(ch not in "0123456789abcdef" for ch in token):
            raise ValueError("cloudflare_artifact_ref_invalid")
        return self.root / f"{token}.bin", self.root / f"{token}.json"

    def capture(
        self,
        *,
        operation_id: str,
        action: CloudflareBrowserAction,
        media_type: str,
        data: bytes,
    ) -> dict[str, Any]:
        if not operation_id:
            raise ValueError("cloudflare_artifact_operation_id_required")
        if action not in {CloudflareBrowserAction.SCREENSHOT, CloudflareBrowserAction.PDF}:
            raise ValueError("cloudflare_artifact_action_invalid")
        if not isinstance(data, bytes) or not data:
            raise ValueError("cloudflare_artifact_data_invalid")
        if len(data) > self.max_bytes:
            raise RuntimeError("cloudflare_browser_binary_artifact_too_large")
        if not isinstance(media_type, str) or not media_type:
            raise ValueError("cloudflare_artifact_media_type_invalid")

        digest = _sha256(data)
        token = _token(operation_id, action.value, digest)
        data_path, meta_path = self._paths(token)
        data_path.write_bytes(data)
        meta = {
            "operationId": operation_id,
            "action": action.value,
            "mediaType": media_type,
            "bytes": len(data),
            "sha256": digest,
        }
        meta_path.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
        for path in (data_path, meta_path):
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        return {
            "ref": _REF_PREFIX + token,
            "sha256": digest,
            "bytes": len(data),
            "mediaType": media_type,
            "action": action.value,
        }

    def capture_workflow_step(
        self, *, operation_id: str, data: bytes, media_type: str = "application/octet-stream"
    ) -> dict[str, Any]:
        if not operation_id:
            raise ValueError("cloudflare_artifact_operation_id_required")
        if media_type != "application/octet-stream":
            raise ValueError("cloudflare_workflow_step_media_type_invalid")
        if not isinstance(data, bytes) or not data:
            raise ValueError("cloudflare_artifact_data_invalid")
        if len(data) > self.max_bytes:
            raise RuntimeError("cloudflare_workflow_step_artifact_too_large")
        action = "workflow_step_evidence"
        digest = _sha256(data)
        token = _token(operation_id, action, digest)
        data_path, meta_path = self._paths(token)
        data_path.write_bytes(data)
        meta = {
            "operationId": operation_id, "action": action, "mediaType": media_type,
            "bytes": len(data), "sha256": digest,
        }
        meta_path.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
        for path in (data_path, meta_path):
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        return {"ref": _REF_PREFIX + token, "sha256": digest, "bytes": len(data),
                "mediaType": media_type, "action": action}

    def read(
        self,
        *,
        operation_id: str,
        ref: str,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
            raise ValueError("cloudflare_artifact_ref_invalid")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("cloudflare_artifact_offset_invalid")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("cloudflare_artifact_limit_invalid")
        if limit < 1 or limit > MAX_CLOUDFLARE_ARTIFACT_CHUNK_BYTES:
            raise ValueError("cloudflare_artifact_limit_out_of_range")

        token = ref[len(_REF_PREFIX):]
        data_path, meta_path = self._paths(token)
        if not data_path.is_file() or not meta_path.is_file():
            raise KeyError("cloudflare_artifact_ref_not_found")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("operationId") != operation_id:
            raise PermissionError("cloudflare_artifact_operation_mismatch")
        total = data_path.stat().st_size
        if total != meta.get("bytes"):
            raise RuntimeError("cloudflare_artifact_size_integrity_mismatch")
        digest = meta.get("sha256")
        action = meta.get("action")
        if not isinstance(digest, str) or not isinstance(action, str):
            raise RuntimeError("cloudflare_artifact_metadata_integrity_mismatch")
        if token != _token(operation_id, action, digest):
            raise RuntimeError("cloudflare_artifact_metadata_integrity_mismatch")
        if _sha256(data_path.read_bytes()) != digest:
            raise RuntimeError("cloudflare_artifact_digest_integrity_mismatch")
        if offset > total:
            raise ValueError("cloudflare_artifact_offset_out_of_range")

        with data_path.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read(limit)
        next_offset = offset + len(chunk)
        return {
            "ref": ref,
            "operationId": operation_id,
            "action": meta.get("action"),
            "mediaType": meta.get("mediaType"),
            "offset": offset,
            "nextOffset": next_offset,
            "totalBytes": total,
            "sha256": meta.get("sha256"),
            "dataBase64": base64.b64encode(chunk).decode("ascii"),
            "eof": next_offset >= total,
        }
