"""Governed Gemini Files API upload transport. No upload without consumed HumanApproval.

The upload session URL and provider file URI are opaque secrets held only in
encrypted EventStore receipts. Provider upload is distinct from model consumption.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import stat
from pathlib import Path
import re
from urllib.parse import urlsplit
import urllib.request
import urllib.error

from .errors import AuthorityViolation

_FILE_NAME = re.compile(r"^files/[A-Za-z0-9_-]{6,128}$")
_ALLOWED_MEDIA = {"application/pdf", "video/mp4", "audio/mpeg", "audio/mp4",
                  "audio/wav", "image/png", "image/jpeg", "image/webp"}
_MAX_METADATA_RESPONSE = 128 * 1024


def _validated_upload_url(value: str, origin: str) -> str:
    """Only a same-origin HTTPS (or explicit local test) upload session."""
    addr = urlsplit(value)
    allowed = urlsplit(origin)
    if (addr.scheme != allowed.scheme or addr.netloc.lower() != allowed.netloc.lower()
            or addr.username or addr.password or addr.fragment
            or not addr.path.startswith("/upload/")
            or len(value) > 2048):
        raise AuthorityViolation("MEDIA_UPLOAD_SESSION_ORIGIN_REFUSED")
    return value


def validate_file_receipt(raw: bytes, *, mime: str, origin: str) -> dict:
    if not raw or len(raw) > _MAX_METADATA_RESPONSE:
        raise AuthorityViolation("MEDIA_UPLOAD_RECEIPT_SIZE_INVALID")
    try:
        doc = json.loads(raw)
        file = doc.get("file") if isinstance(doc, dict) else None
    except (ValueError, UnicodeDecodeError):
        file = None
    if not isinstance(file, dict):
        raise AuthorityViolation("MEDIA_UPLOAD_FILE_RECEIPT_INVALID")
    name, uri, state = file.get("name"), file.get("uri"), file.get("state", "PROCESSING")
    if not isinstance(name, str) or not _FILE_NAME.fullmatch(name):
        raise AuthorityViolation("MEDIA_UPLOAD_PROVIDER_FILE_ID_INVALID")
    if not isinstance(uri, str):
        raise AuthorityViolation("MEDIA_UPLOAD_FILE_URI_INVALID")
    parsed = urlsplit(uri)
    wanted = urlsplit(origin)
    if (parsed.scheme != wanted.scheme or parsed.netloc.lower() != wanted.netloc.lower()
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/v1beta/" + name):
        raise AuthorityViolation("MEDIA_UPLOAD_FILE_URI_ORIGIN_REFUSED")
    reported_mime = file.get("mimeType", file.get("mime_type", mime))
    if reported_mime != mime or mime not in _ALLOWED_MEDIA:
        raise AuthorityViolation("MEDIA_UPLOAD_MIME_MISMATCH")
    if state not in ("PROCESSING", "ACTIVE", "FAILED"):
        raise AuthorityViolation("MEDIA_UPLOAD_FILE_STATE_INVALID")
    if state == "FAILED":
        raise AuthorityViolation("MEDIA_UPLOAD_PROVIDER_PROCESSING_FAILED")
    return {"fileName": name, "fileUri": uri, "fileMime": mime,
            "state": "file_active" if state == "ACTIVE" else "file_processing",
            "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=47)).isoformat()}


class GeminiResumableUploadTransport:
    """Production Python streaming transport. A fake may implement the same API."""

    def _open(self, request: urllib.request.Request):
        from .media_execution import NoRedirectHandler
        return urllib.request.build_opener(NoRedirectHandler()).open(request, timeout=120)

    def start(self, *, origin: str, path: str, credential: str,
              mime: str, size: int, original_name: str) -> str:
        if not credential:
            raise AuthorityViolation("MEDIA_UPLOAD_PROVIDER_CREDENTIAL_MISSING")
        if mime not in _ALLOWED_MEDIA:
            raise AuthorityViolation("MEDIA_UPLOAD_MIME_UNSUPPORTED")
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", original_name)[:100]
        body = json.dumps({"file": {"display_name": safe_name}}).encode("utf-8")
        headers = {
            "x-goog-api-key": credential, "Content-Type": "application/json",
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(size),
            "X-Goog-Upload-Header-Content-Type": mime,
        }
        request = urllib.request.Request(origin + path, body, headers=headers, method="POST")
        try:
            with self._open(request) as response:
                if response.status not in (200, 201, 202):
                    raise AuthorityViolation("MEDIA_UPLOAD_START_FAILED")
                url = response.headers.get("X-Goog-Upload-URL")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise AuthorityViolation("MEDIA_UPLOAD_START_TRANSPORT_FAILED") from None
        if not isinstance(url, str):
            raise AuthorityViolation("MEDIA_UPLOAD_SESSION_URL_MISSING")
        return _validated_upload_url(url, origin)

    def upload_and_finalize(self, *, session_url: str, origin: str, source: Path,
                            mime: str, size: int) -> bytes:
        _validated_upload_url(session_url, origin)
        headers = {
            "Content-Length": str(size),
            "Content-Type": mime,
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }
        # urllib can stream file-like request data; explicit length avoids
        # chunked transfer. The file is not read into Python memory.
        try:
            # Open the final source descriptor without following a last-hop
            # symlink. Keep that same inode open throughout streaming.
            fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                    raise AuthorityViolation("MEDIA_UPLOAD_SOURCE_CHANGED_BEFORE_SEND")
                request = urllib.request.Request(
                    session_url,
                    data=iter(lambda: stream.read(1_048_576), b""),
                    headers=headers, method="POST"
                )
                with self._open(request) as response:
                    if response.status not in (200, 201, 202):
                        raise AuthorityViolation("MEDIA_UPLOAD_FINALIZE_FAILED")
                    return response.read(_MAX_METADATA_RESPONSE + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            raise AuthorityViolation("MEDIA_UPLOAD_FINALIZE_TRANSPORT_FAILED") from None
        except OSError:
            raise AuthorityViolation("MEDIA_UPLOAD_SOURCE_UNAVAILABLE") from None

    def file_status(self, *, origin: str, file_name: str, credential: str) -> bytes:
        if not _FILE_NAME.fullmatch(file_name):
            raise AuthorityViolation("MEDIA_UPLOAD_PROVIDER_FILE_ID_INVALID")
        if not credential:
            raise AuthorityViolation("MEDIA_UPLOAD_PROVIDER_CREDENTIAL_MISSING")
        request = urllib.request.Request(
            origin + "/v1beta/" + file_name,
            headers={"x-goog-api-key": credential},
            method="GET"
        )
        try:
            with self._open(request) as response:
                if response.status != 200:
                    raise AuthorityViolation("MEDIA_UPLOAD_STATUS_FAILED")
                return response.read(_MAX_METADATA_RESPONSE + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            raise AuthorityViolation("MEDIA_UPLOAD_STATUS_TRANSPORT_FAILED") from None
