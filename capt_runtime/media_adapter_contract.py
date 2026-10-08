"""Governed media endpoint declarations. Metadata only; no network dispatch.

Providers may expose OpenAI-style, multipart, asynchronous job, or bespoke
endpoints. Never infer capability solely from model names or user prompts.
The provider driver must validate an exact authorized adapter + cost boundary
before any upload, polling, or download occurs.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from urllib.parse import urlsplit

_ALLOWED_OPERATIONS = frozenset({
    "image_input", "audio_input", "video_input", "file_input",
    "image_generate", "audio_generate", "video_generate", "audio_transcribe",
})
_ALLOWED_TRANSPORTS = frozenset({
    "chat_completions", "responses", "json", "multipart", "async_job",
})
_ALLOWED_RESPONSE_TYPES = frozenset({
    "json_base64", "json_url", "raw_binary", "multipart", "job_receipt",
})
_TEMPLATE_NAMES = frozenset({"job_id", "file_id", "generation_id"})


def _trusted_origin(url: str, *, allow_loopback: bool = False) -> str:
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("MEDIA_ENDPOINT_ORIGIN_CREDENTIALS_OR_QUERY_FORBIDDEN")
    if parsed.path not in ("", "/"):
        raise ValueError("MEDIA_ENDPOINT_ORIGIN_MUST_NOT_CONTAIN_PATH")
    if not parsed.hostname:
        raise ValueError("MEDIA_ENDPOINT_HOST_MISSING")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("MEDIA_ENDPOINT_PORT_INVALID") from exc
    if parsed.scheme != "https":
        if not (allow_loopback and parsed.scheme == "http" and
                parsed.hostname in ("127.0.0.1", "::1", "localhost")):
            raise ValueError("MEDIA_ENDPOINT_REQUIRES_HTTPS")
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if parsed.hostname.lower() in ("localhost",):
            if not allow_loopback:
                raise ValueError("MEDIA_ENDPOINT_LOCALHOST_NOT_ALLOWED")
    else:
        if not ip.is_global and not (allow_loopback and ip.is_loopback):
            raise ValueError("MEDIA_ENDPOINT_PRIVATE_IP_FORBIDDEN")
    return parsed.netloc.lower()


def _validate_path(value: str, *, allow_templates: bool) -> None:
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        raise ValueError("MEDIA_ENDPOINT_PATH_MUST_BE_RELATIVE_TO_ORIGIN")
    if any(c in value for c in ("\\", "?", "#", "%", "\x00")):
        raise ValueError("MEDIA_ENDPOINT_PATH_UNSAFE")
    pieces = value.split("/")
    if any(x in ("..", ".") or "%2e" in x.lower() or "%2f" in x.lower() for x in pieces):
        raise ValueError("MEDIA_ENDPOINT_PATH_TRAVERSAL")
    tokens = re.findall(r"\{([^{}]+)\}", value)
    if tokens and not allow_templates:
        raise ValueError("MEDIA_ENDPOINT_UNEXPECTED_TEMPLATE")
    if any(token not in _TEMPLATE_NAMES for token in tokens):
        raise ValueError("MEDIA_ENDPOINT_TEMPLATE_UNKNOWN")
    if value.count("{") != value.count("}") or len(value) > 512:
        raise ValueError("MEDIA_ENDPOINT_PATH_INVALID")


@dataclass(frozen=True)
class MediaAdapterContract:
    provider_id: str
    origin: str
    operation: str
    transport: str
    submit_path: str
    response_type: str
    media_types: tuple[str, ...]
    poll_path: str | None = None
    result_path: str | None = None
    download_origins: tuple[str, ...] = ()
    max_asset_bytes: int = 512 * 1024 * 1024
    allow_loopback: bool = False

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", self.provider_id):
            raise ValueError("MEDIA_ADAPTER_PROVIDER_ID_INVALID")
        if self.operation not in _ALLOWED_OPERATIONS:
            raise ValueError("MEDIA_ADAPTER_OPERATION_UNSUPPORTED")
        if self.transport not in _ALLOWED_TRANSPORTS:
            raise ValueError("MEDIA_ADAPTER_TRANSPORT_UNSUPPORTED")
        if self.response_type not in _ALLOWED_RESPONSE_TYPES:
            raise ValueError("MEDIA_ADAPTER_RESPONSE_UNSUPPORTED")
        _trusted_origin(self.origin, allow_loopback=self.allow_loopback)
        _validate_path(self.submit_path, allow_templates=False)
        if self.poll_path:
            _validate_path(self.poll_path, allow_templates=True)
        if self.result_path:
            _validate_path(self.result_path, allow_templates=True)
        if self.transport == "async_job" and (
            not self.poll_path or not self.result_path or self.response_type != "job_receipt"
        ):
            raise ValueError("MEDIA_ADAPTER_ASYNC_REQUIRES_POLL_AND_RESULT_PATHS")
        if self.transport != "async_job" and (self.poll_path or self.result_path):
            raise ValueError("MEDIA_ADAPTER_POLLING_ONLY_FOR_ASYNC")
        if not self.media_types or len(self.media_types) > 32 or any(
            not re.fullmatch(r"[a-z0-9*+.-]+/[a-z0-9*+.-]+", m)
            for m in self.media_types
        ):
            raise ValueError("MEDIA_ADAPTER_MIME_TYPES_INVALID")
        if not 1 <= self.max_asset_bytes <= 4 * 1024 * 1024 * 1024:
            raise ValueError("MEDIA_ADAPTER_SIZE_INVALID")
        for host in self.download_origins:
            _trusted_origin(host, allow_loopback=self.allow_loopback)

    def permits_download(self, url: str) -> bool:
        """Exact origin check; job response URLs are *untrusted* by default."""
        self.validate()
        candidate = urlsplit(url)
        if candidate.scheme != "https" and not self.allow_loopback:
            return False
        if candidate.username or candidate.password or candidate.fragment:
            return False
        try:
            accepted_origin = _trusted_origin(
                f"{candidate.scheme}://{candidate.netloc}",
                allow_loopback=self.allow_loopback
            )
        except ValueError:
            return False
        return accepted_origin in {
            _trusted_origin(o, allow_loopback=self.allow_loopback)
            for o in self.download_origins
        }
