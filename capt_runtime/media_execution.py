"""Governed media execution foundation.

An exact local asset, provider/model, endpoint contract, resource ceiling and
one-use HumanApproval are bound before a model/provider request is dispatched.
The transport is intentionally injectable for deterministic offline testing.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import commands
from .errors import AuthorityViolation
from .media_adapter_contract import MediaAdapterContract


MAX_INPUT_FILES = 8
MAX_INLINE_BYTES = 12 * 1024 * 1024
MAX_PROMPT_LENGTH = 32_768
_ALLOWED_OUTPUTS = ("image/png", "image/jpeg", "image/webp", "audio/mpeg", "audio/wav", "video/mp4")
_SUPPORTED_OPERATIONS = frozenset({
    "image_input", "document_input", "video_input", "image_generate", "audio_generate",
    "audio_transcribe", "video_generate",
})
_JOB_RE = re.compile(r"^dr-media-[A-Za-z0-9-]{8,96}$")
_FILENAME_RE = re.compile(r"^[0-9a-f-]{36}-[A-Za-z0-9_]{1,60}(?:\.[A-Za-z0-9]{1,16})?$")


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _hash(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(obj)).hexdigest()


def _sha256_file(path: Path, ceiling: int) -> tuple[str, int]:
    hashed = hashlib.sha256()
    length = 0
    with path.open("rb") as file:
        while chunk := file.read(1_048_576):
            length += len(chunk)
            if length > ceiling:
                raise AuthorityViolation("MEDIA_INPUT_OVER_SIZE_LIMIT")
            hashed.update(chunk)
    return "sha256:" + hashed.hexdigest(), length


def _regular_file(path: Path, base: Path) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise AuthorityViolation("MEDIA_INTAKE_INVALID_PATH")
    try:
        resolved_base = base.resolve(strict=True)
        resolved = path.resolve(strict=True)
        mode = path.lstat().st_mode
    except OSError as exc:
        raise AuthorityViolation("MEDIA_INTAKE_NOT_FOUND") from exc
    if not stat.S_ISREG(mode) or resolved != path or not resolved.is_relative_to(resolved_base):
        raise AuthorityViolation("MEDIA_INTAKE_OUTSIDE_QUARANTINE")


def _verified_files(
    entries: Any, *, state_root: Path, operation: str, max_input_bytes: int
) -> list[dict[str, Any]]:
    if not isinstance(entries, list) or len(entries) > MAX_INPUT_FILES:
        raise AuthorityViolation("MEDIA_INTAKE_COUNT_INVALID")
    if operation in ("image_input", "document_input", "video_input", "audio_transcribe") and not entries:
        raise AuthorityViolation("MEDIA_INPUT_REQUIRED")
    if operation not in ("image_input", "document_input", "video_input", "audio_transcribe") and entries:
        raise AuthorityViolation("MEDIA_INPUT_NOT_IMPLEMENTED_FOR_OPERATION")
    root = state_root / "native-media-intake" / "v1"
    result = []
    total = 0
    for item in entries:
        if not isinstance(item, dict):
            raise AuthorityViolation("MEDIA_INPUT_METADATA_INVALID")
        path = Path(str(item.get("stagedPath", "")))
        _regular_file(path, root)
        if not _FILENAME_RE.fullmatch(path.name):
            raise AuthorityViolation("MEDIA_INTAKE_NONCANONICAL_FILENAME")
        digest, size = _sha256_file(path, max_input_bytes)
        if digest != item.get("sha256") or size != item.get("sizeBytes"):
            raise AuthorityViolation("MEDIA_INTAKE_DIGEST_OR_SIZE_MISMATCH")
        mime = str(item.get("mediaType") or "")
        if operation == "document_input" and mime != "application/pdf":
            raise AuthorityViolation("MEDIA_MODEL_DOCUMENT_TYPE_UNSUPPORTED")
        if operation == "video_input" and mime != "video/mp4":
            raise AuthorityViolation("MEDIA_MODEL_VIDEO_TYPE_UNSUPPORTED")
        if operation == "image_input" and mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            raise AuthorityViolation("MEDIA_MODEL_IMAGE_TYPE_UNSUPPORTED")
        if operation == "audio_transcribe" and mime not in (
            "audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a", "audio/ogg", "audio/webm"
        ):
            raise AuthorityViolation("MEDIA_MODEL_AUDIO_TYPE_UNSUPPORTED")
        total += size
        if total > max_input_bytes:
            raise AuthorityViolation("MEDIA_TOTAL_INPUT_OVER_LIMIT")
        with path.open("rb") as stream:
            magic = stream.read(24)
        signatures = {
            "application/pdf": magic.startswith(b"%PDF-"),
            "video/mp4": len(magic) >= 12 and magic[4:8] == b"ftyp",
            "image/png": magic.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/jpeg": magic.startswith(b"\xff\xd8\xff"),
            "image/webp": magic.startswith(b"RIFF") and magic[8:12] == b"WEBP",
            "image/gif": magic.startswith((b"GIF87a", b"GIF89a")),
            "audio/mpeg": magic.startswith(b"ID3") or (len(magic) > 1 and magic[0] == 0xff and magic[1] & 0xe0 == 0xe0),
            "audio/wav": magic.startswith(b"RIFF") and magic[8:12] == b"WAVE",
            "audio/mp4": magic[4:8] == b"ftyp",
            "audio/x-m4a": magic[4:8] == b"ftyp",
            "audio/ogg": magic.startswith(b"OggS"),
            "audio/webm": magic.startswith(b"\x1a\x45\xdf\xa3"),
        }
        if not signatures.get(mime, False):
            raise AuthorityViolation("MEDIA_INPUT_SIGNATURE_MISMATCH")
        result.append({"stagedPath": str(path), "sha256": digest, "sizeBytes": size,
                       "mediaType": mime, "originalName": str(item.get("originalName") or path.name)[:200]})
    return result


@dataclass(frozen=True)
class MediaRoute:
    adapter_id: str
    provider: str
    model: str
    contract: MediaAdapterContract
    auth_style: str = "bearer"
    maximum_price_usd: float = 0.0

    def validate(self) -> None:
        self.contract.validate()
        if self.provider != self.contract.provider_id:
            raise AuthorityViolation("MEDIA_PROVIDER_CONTRACT_MISMATCH")
        if not self.model or len(self.model) > 200:
            raise AuthorityViolation("MEDIA_MODEL_INVALID")
        if not 0 <= self.maximum_price_usd <= 100:
            raise AuthorityViolation("MEDIA_ROUTE_PRICE_CEILING_INVALID")
        required_wire = {
            "image_input": ("chat_completions", "json_text"),
            "document_input": ("gemini_interactions", "json_text"),
            "video_input": ("gemini_interactions", "json_text"),
            "image_generate": ("json", "json_base64"),
            "audio_generate": ("json", "raw_binary"),
            "audio_transcribe": ("multipart", "json_text"),
            "video_generate": ("async_job", "job_receipt"),
        }
        expected = required_wire.get(self.contract.operation)
        mime_family = {'image_input': 'image/', 'document_input': 'application/',
                       'video_input': 'video/', 'image_generate': 'image/', 'audio_generate': 'audio/', 'audio_transcribe': 'audio/', 'video_generate': 'video/'}.get(self.contract.operation)
        if mime_family and not all(m.startswith(mime_family) for m in self.contract.media_types):
            raise AuthorityViolation('MEDIA_ROUTE_MIME_FAMILY_MISMATCH')
        if expected is not None and (
            self.contract.transport, self.contract.response_type
        ) != expected:
            if not (self.contract.operation == "image_generate" and
                    self.contract.transport == "json" and
                    self.contract.response_type == "json_url"):
                raise AuthorityViolation("MEDIA_ROUTE_WIRE_FORMAT_NOT_IMPLEMENTED")
        if self.contract.operation == "image_generate" and (
            self.contract.response_type == "json_url" and
            not self.contract.download_origins
        ):
            raise AuthorityViolation("MEDIA_IMAGE_URL_REQUIRES_DOWNLOAD_ALLOWLIST")
        if self.auth_style not in ("bearer", "x-goog-api-key", "none"):
            raise AuthorityViolation("MEDIA_AUTH_STYLE_INVALID")


class MediaRouteRegistry:
    """Exact operator-configured routes; model names never confer capability."""
    def __init__(self, routes: dict[str, MediaRoute]):
        self.routes = dict(routes)
        for key, route in self.routes.items():
            if key != route.adapter_id:
                raise ValueError("MEDIA_ROUTE_KEY_MISMATCH")
            route.validate()

    def resolve(self, adapter_id: str, provider: str, model: str, operation: str) -> MediaRoute:
        route = self.routes.get(adapter_id)
        if route is None or route.provider != provider or route.model != model:
            raise AuthorityViolation("MEDIA_ROUTE_NOT_EXPLICITLY_CONFIGURED")
        if route.contract.operation != operation:
            raise AuthorityViolation("MEDIA_CAPABILITY_NOT_ADVERTISED")
        return route


def _freeze_request(
    intent: dict[str, Any], *, registry: MediaRouteRegistry, state_root: Path
) -> dict[str, Any]:
    operation = str(intent.get("operation") or "")
    if operation not in _SUPPORTED_OPERATIONS:
        raise AuthorityViolation("MEDIA_OPERATION_NOT_IMPLEMENTED")
    provider = str(intent.get("provider") or "")
    model = str(intent.get("model") or "")
    route = registry.resolve(str(intent.get("adapterId") or ""), provider, model, operation)
    network = str(intent.get("providerNetworkPolicy") or "")
    if network != "remote_allowed" and not (route.contract.allow_loopback and network == "local_only"):
        raise AuthorityViolation("MEDIA_NETWORK_AUTHORITY_NOT_GRANTED")
    value = intent.get("maxCostUSD")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise AuthorityViolation("MEDIA_BUDGET_REQUIRED")
    if route.maximum_price_usd > value:
        raise AuthorityViolation("MEDIA_ESTIMATED_COST_EXCEEDS_APPROVED_LIMIT")
    prompt = str(intent.get("prompt") or "").strip()
    if not prompt or len(prompt) > MAX_PROMPT_LENGTH:
        raise AuthorityViolation("MEDIA_PROMPT_INVALID")
    files = _verified_files(intent.get("files", []), state_root=state_root,
                            operation=operation, max_input_bytes=MAX_INLINE_BYTES)
    if any(item["mediaType"] not in route.contract.media_types for item in files):
        raise AuthorityViolation("MEDIA_MODEL_INPUT_MIME_NOT_ADVERTISED")
    binding = {
        "operation": operation, "adapterId": route.adapter_id,
        "provider": provider, "model": model, "prompt": prompt,
        "files": files, "maxCostUSD": float(value),
        "routePriceCeilingUSD": route.maximum_price_usd,
        "providerNetworkPolicy": network, "transport": route.contract.transport,
        "mediaTypes": list(route.contract.media_types),
        "endpointOrigin": route.contract.origin,
        "endpointPath": route.contract.submit_path,
        "routeContractDigest": _hash({"contract": asdict(route.contract),
                                     "authStyle": route.auth_style,
                                     "maxPrice": route.maximum_price_usd}),
        "maxOutputBytes": min(route.contract.max_asset_bytes,
            512 * 1024 * 1024 if operation == "video_generate" else 64 * 1024 * 1024),
        "outputRoot": str((state_root / "media-output" / "v2").resolve()),
    }
    return binding


def _issued_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expires() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")


def prepare_media_approval(
    service: Any, intent: dict[str, Any], metadata: dict[str, Any],
    *, registry: MediaRouteRegistry
) -> dict[str, Any]:
    if metadata.get("actor", {}).get("kind") != "human":
        raise AuthorityViolation("MEDIA_PREPARE_HUMAN_ONLY")
    state_root = Path(service.store.path).parent.resolve()
    binding = _freeze_request(intent, registry=registry, state_root=state_root)
    digest = _hash(binding)
    suffix = hashlib.sha256(metadata["idempotencyKey"].encode()).hexdigest()[:20]
    mission = "m-media-" + suffix
    task = mission + "-task-1"
    driver = "dr-media-" + suffix
    request_id = "approval-media-" + suffix
    request = {
        "schemaVersion": "1.0.0", "requestId": request_id,
        "missionId": mission, "taskId": task, "requestedCapability": "cap.model.media",
        "resource": binding["outputRoot"], "operation": "ModelMediaExecution",
        "scope": {"kind": "media", "approvalBinding": {
            **binding, "missionId": mission, "taskId": task,
            "driverRunId": driver, "targetRoot": binding["outputRoot"],
            "manifestDigest": digest,
        }},
        "riskClassification": "consequential",
        "policyReason": (
            "Operator approval binds exact media bytes and digest, provider/model, "
            "endpoint, network authority and cost ceiling before external dispatch."
        ),
        "requestedBy": {"actorId": "exec-media", "kind": "execution_plane"},
        "expiresAt": _expires(), "createdAt": metadata["issuedAt"],
        "correlationId": metadata["correlationId"],
        "promptAssemblyDigest": digest, "remainingUses": 1,
    }
    # The authenticated human expresses intent; the bounded execution plane
    # requests HumanApproval under the existing separation-of-authorities.
    inner = commands.command(
        command_id="cmd-media-approval-" + suffix,
        idempotency_key="idem-media-approval-" + suffix,
        operation_fingerprint=commands.fingerprint(
            "request_human_approval", {"requestId": request_id, "manifestDigest": digest}),
        correlation_id=metadata["correlationId"], actor_id="exec-media",
        actor_kind="execution_plane", issued_at=metadata["issuedAt"],
        replay_policy="never",
    )
    service.request_human_approval(request, inner)
    return {"requestId": request_id, "driverRunId": driver,
            "missionId": mission, "taskId": task,
            "manifestDigest": digest, "state": "requested",
            "operation": binding["operation"], "provider": binding["provider"],
            "model": binding["model"], "fileCount": len(binding["files"]),
            "maxCostUSD": binding["maxCostUSD"]}


def _route_matches_binding(route: MediaRoute, binding: dict[str, Any]) -> None:
    expected = _hash({"contract": asdict(route.contract),
                      "authStyle": route.auth_style,
                      "maxPrice": route.maximum_price_usd})
    if binding.get("routeContractDigest") != expected:
        raise AuthorityViolation("MEDIA_ROUTE_CHANGED_SINCE_APPROVAL")


def _get_binding(service: Any, request_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    from .aggregates.human_approval import HumanApprovalAggregate
    state = service.store.require_state(HumanApprovalAggregate.stream_id(request_id))
    if state.get("operation") != "ModelMediaExecution":
        raise AuthorityViolation("MEDIA_APPROVAL_DOMAIN_MISMATCH")
    binding = (state.get("scope") or {}).get("approvalBinding") or {}
    if not binding or state.get("promptAssemblyDigest") != binding.get("manifestDigest"):
        raise AuthorityViolation("MEDIA_APPROVAL_BINDING_TAMPERED")
    return state, binding


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AuthorityViolation("MEDIA_REDIRECT_FORBIDDEN")


class MediaHTTPTransport:
    """Bounded binary HTTP. No redirects, no arbitrary model-returned URLs."""
    def send(self, method: str, url: str, body: bytes | None,
             headers: dict[str, str], limit: int) -> tuple[bytes, str]:
        if limit < 1:
            raise AuthorityViolation("MEDIA_HTTP_RESPONSE_LIMIT_INVALID")
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        opener = urllib.request.build_opener(NoRedirectHandler())
        try:
            with opener.open(request, timeout=90) as response:
                if response.status not in (200, 201, 202):
                    raise AuthorityViolation("MEDIA_PROVIDER_HTTP_REJECTED")
                chunks = []
                remaining = limit + 1
                while remaining > 0:
                    chunk = response.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                if remaining <= 0:
                    raise AuthorityViolation("MEDIA_PROVIDER_RESPONSE_OVERSIZE")
                return b"".join(chunks), response.headers.get("Content-Type", "")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            # Never propagate external provider bodies, URLs or credentials
            raise AuthorityViolation(
                "MEDIA_PROVIDER_HTTP_" + str(getattr(exc, "code", "UNAVAILABLE"))
            ) from None


def _authorization(route: MediaRoute, credential: str) -> dict[str, str]:
    if route.auth_style == "none":
        if urlsplit(route.contract.origin).scheme != "http" or not route.contract.allow_loopback:
            raise AuthorityViolation("MEDIA_UNAUTHENTICATED_REMOTE_REFUSED")
        return {}
    if not credential:
        raise AuthorityViolation("MEDIA_PROVIDER_CREDENTIAL_MISSING")
    return ({"x-goog-api-key": credential} if route.auth_style == "x-goog-api-key"
            else {"Authorization": "Bearer " + credential})


def _result_bytes(operation: str, response: bytes, response_type: str) -> tuple[bytes | None, str | None, str | None]:
    """Output media bytes, MIME type, or operation identifier. No shell/filesystem side effects."""
    if operation == "audio_generate":
        if not response or len(response) > 64 * 1024 * 1024:
            raise AuthorityViolation("MEDIA_AUDIO_OUTPUT_INVALID")
        is_mp3 = response.startswith(b"ID3") or (len(response) > 1 and response[0] == 255 and response[1] & 224 == 224)
        if not is_mp3:
            raise AuthorityViolation("MEDIA_AUDIO_OUTPUT_SIGNATURE_INVALID")
        return response, "audio/mpeg", None
    try:
        obj = json.loads(response)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AuthorityViolation("MEDIA_PROVIDER_JSON_INVALID") from exc
    if not isinstance(obj, dict):
        raise AuthorityViolation("MEDIA_PROVIDER_JSON_INVALID")
    if operation == "video_generate":
        operation_id = obj.get("name")
        if not isinstance(operation_id, str) or not re.fullmatch(
            r"operations/[A-Za-z0-9_./-]{4,200}", operation_id
        ) or ".." in operation_id or "%2" in operation_id.lower():
            raise AuthorityViolation("MEDIA_VIDEO_OPERATION_ID_INVALID")
        return None, None, operation_id
    if operation == "image_generate":
        items = obj.get("data")
        encoded = items[0].get("b64_json") if isinstance(items, list) and items and isinstance(items[0], dict) else None
        if not isinstance(encoded, str):
            raise AuthorityViolation("MEDIA_IMAGE_DATA_MISSING")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise AuthorityViolation("MEDIA_IMAGE_BASE64_INVALID") from exc
        if len(data) > 64 * 1024 * 1024 or not data:
            raise AuthorityViolation("MEDIA_IMAGE_OUTPUT_OVERSIZE")
        if data.startswith(bytes.fromhex("89504e470d0a1a0a")):
            mime = "image/png"
        elif data.startswith(bytes.fromhex("ffd8ff")):
            mime = "image/jpeg"
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            raise AuthorityViolation("MEDIA_IMAGE_OUTPUT_SIGNATURE_INVALID")
        return data, mime, None
    if operation in ("document_input", "video_input"):
        # Gemini Interactions REST output: never treat a queued interaction
        # as completed media understanding. One paid dispatch has already
        # crossed the external boundary and may require manual reconciliation.
        status = obj.get("status")
        if status not in (None, "completed"):
            raise AuthorityViolation("MEDIA_GEMINI_INTERACTION_NOT_COMPLETED")
        result = obj.get("output_text")
        if not isinstance(result, str) or not result.strip():
            outputs = obj.get("outputs")
            if isinstance(outputs, list):
                result = "".join(
                    x["text"] for x in outputs[:32]
                    if isinstance(x, dict) and x.get("type") == "text"
                    and isinstance(x.get("text"), str)
                )
        if not isinstance(result, str) or not result.strip():
            # REST interaction has step outputs; only examine model text
            # blocks (never echoed user inputs or tool call payloads).
            steps = obj.get("steps")
            chunks = []
            if isinstance(steps, list):
                for step in steps[-16:]:
                    if not isinstance(step, dict) or step.get("type") != "model":
                        continue
                    for part in (step.get("content") or [])[:32]:
                        if isinstance(part, dict) and part.get("type") == "text":
                            value = part.get("text")
                            if isinstance(value, str):
                                chunks.append(value)
            result = "".join(chunks)
        if not result or not result.strip():
            raise AuthorityViolation("MEDIA_GEMINI_TEXT_MISSING")
        if len(result.encode("utf-8")) > 2 * 1024 * 1024:
            raise AuthorityViolation("MEDIA_GEMINI_TEXT_OVER_LIMIT")
        return result.encode("utf-8"), "text/plain", None
    if operation == "image_input":
        choices = obj.get("choices")
        text = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        if not isinstance(text, str) or not text.strip():
            raise AuthorityViolation("MEDIA_VISION_TEXT_MISSING")
        return text.encode(), "text/plain", None
    if operation == "audio_transcribe":
        text = obj.get("text")
        if not isinstance(text, str):
            raise AuthorityViolation("MEDIA_TRANSCRIPTION_TEXT_MISSING")
        return text.encode(), "text/plain", None
    raise AuthorityViolation("MEDIA_OPERATION_UNIMPLEMENTED")


def _approved_image_url(raw: bytes, route: MediaRoute) -> str:
    """Accept an image URL only from an explicit configured asset origin."""
    try:
        document = json.loads(raw)
        files = document.get("data") if isinstance(document, dict) else None
        address = files[0].get("url") if (
            isinstance(files, list) and files and isinstance(files[0], dict)
        ) else None
    except (ValueError, UnicodeDecodeError, AttributeError, TypeError) as exc:
        raise AuthorityViolation("MEDIA_IMAGE_URL_RESPONSE_INVALID") from exc
    if not isinstance(address, str) or not route.contract.permits_download(address):
        raise AuthorityViolation("MEDIA_IMAGE_URL_ORIGIN_REFUSED")
    return address


def _download_approved_image(
    raw: bytes, route: MediaRoute, transport: MediaHTTPTransport,
    credential: str, ceiling: int
) -> tuple[bytes, str]:
    """No redirects, no arbitrary URL, no cross-origin bearer token."""
    address = _approved_image_url(raw, route)
    candidate = urlsplit(address)
    asset_origin = candidate.scheme + "://" + candidate.netloc
    headers = (
        _authorization(route, credential) if asset_origin == route.contract.origin
        else {}
    )
    bytes_, content_type = transport.send(
        "GET", address, None, headers, min(ceiling, 64 * 1024 * 1024)
    )
    declared = content_type.split(";", 1)[0].strip().lower()
    if bytes_.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "image/png"
    elif bytes_.startswith(b"\xff\xd8\xff"):
        kind = "image/jpeg"
    elif bytes_.startswith(b"RIFF") and bytes_[8:12] == b"WEBP":
        kind = "image/webp"
    else:
        raise AuthorityViolation("MEDIA_IMAGE_DOWNLOAD_MAGIC_INVALID")
    if declared not in (kind, "application/octet-stream"):
        raise AuthorityViolation("MEDIA_IMAGE_DOWNLOAD_MIME_INVALID")
    if kind not in route.contract.media_types:
        raise AuthorityViolation("MEDIA_PROVIDER_OUTPUT_MIME_NOT_ADVERTISED")
    return bytes_, kind


def _build_request(
    binding: dict[str, Any], route: MediaRoute
) -> tuple[bytes, str]:
    operation = binding["operation"]
    prompt = binding["prompt"]
    model = binding["model"]
    if operation in ("document_input", "video_input"):
        # Google Gemini Interactions API uses typed inline media blocks.
        # This route is intentionally limited to 12 MiB of governed bytes.
        # Larger media MUST use a separately approved file-upload workflow.
        content = [{"type": "text", "text": prompt}]
        for item in binding["files"]:
            data = Path(item["stagedPath"]).read_bytes()
            if len(data) != item["sizeBytes"] or (
                "sha256:" + hashlib.sha256(data).hexdigest()
            ) != item["sha256"]:
                raise AuthorityViolation("MEDIA_INPUT_CHANGED_AFTER_ADMISSION")
            content.append({
                "type": "document" if operation == "document_input" else "video",
                "data": base64.b64encode(data).decode("ascii"),
                "mime_type": item["mediaType"],
            })
        return _canonical({"model": model, "input": content}), "application/json"
    if operation == "image_input":
        content = [{"type": "text", "text": prompt}]
        for item in binding["files"]:
            data = Path(item["stagedPath"]).read_bytes()
            if len(data) != item["sizeBytes"] or ("sha256:" + hashlib.sha256(data).hexdigest()) != item["sha256"]:
                raise AuthorityViolation("MEDIA_INPUT_CHANGED_AFTER_ADMISSION")
            content.append({"type": "image_url", "image_url": {
                "url": "data:" + item["mediaType"] + ";base64," +
                    base64.b64encode(data).decode("ascii")
            }})
        return _canonical({"model": model, "messages": [
            {"role": "user", "content": content}]}), "application/json"
    if operation == "image_generate":
        return _canonical({
            "model": model, "prompt": prompt,
            "response_format": "url" if route.contract.response_type == "json_url"
                               else "b64_json",
            "n": 1
        }), "application/json"
    if operation == "audio_generate":
        return _canonical({"model": model, "input": prompt,
                           "voice": "alloy", "response_format": "mp3"}), "application/json"
    if operation == "video_generate":
        # Gemini Veo REST uses predictLongRunning, returns operations/name.
        # Only a frozen matching adapter route permits this request.
        return _canonical({"instances": [{"prompt": prompt}]}), "application/json"
    if operation == "audio_transcribe":
        # Exact bytes are streamed locally into multipart (12 MiB limit).
        # A random boundary is not authority and is never persisted.
        boundary = "capt_" + os.urandom(12).hex()
        file = binding["files"][0]
        blob = Path(file["stagedPath"]).read_bytes()
        if len(blob) != file["sizeBytes"] or ("sha256:" + hashlib.sha256(blob).hexdigest()) != file["sha256"]:
            raise AuthorityViolation("MEDIA_INPUT_CHANGED_AFTER_ADMISSION")
        body = (
            ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n" +
             model + "\r\n--" + boundary + "\r\n" +
             'Content-Disposition: form-data; name="file"; filename="input"\r\n' +
             "Content-Type: " + file["mediaType"] + "\r\n\r\n").encode()
            + blob + ("\r\n--" + boundary + "--\r\n").encode()
        )
        return body, "multipart/form-data; boundary=" + boundary
    raise AuthorityViolation("MEDIA_OPERATION_UNIMPLEMENTED")


def _artifact(
    *, state_root: Path, driver_run_id: str, blob: bytes, mime: str,
    max_bytes: int = 64 * 1024 * 1024
) -> dict[str, Any]:
    if mime not in _ALLOWED_OUTPUTS and mime != "text/plain":
        raise AuthorityViolation("MEDIA_ARTIFACT_MIME_UNSUPPORTED")
    ext = {
        "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        "audio/mpeg": ".mp3", "audio/wav": ".wav",
        "video/mp4": ".mp4", "text/plain": ".txt"
    }[mime]
    if not blob or len(blob) > max_bytes:
        raise AuthorityViolation("MEDIA_ARTIFACT_SIZE_INVALID")
    root = _media_output_directory(state_root, driver_run_id)
    target = root / ("result" + ext)
    with target.open("xb") as file:
        os.chmod(target, 0o600)
        file.write(blob)
        file.flush()
        os.fsync(file.fileno())
    return {"artifactPath": str(target), "artifactDigest": "sha256:" + hashlib.sha256(blob).hexdigest(),
            "mediaType": mime, "sizeBytes": len(blob), "trust": "untrusted",
            "verificationState": "pending_human_verification"}


def media_job_status(store: Any, driver_run_id: str) -> dict[str, Any]:
    if not _JOB_RE.fullmatch(driver_run_id):
        raise AuthorityViolation("MEDIA_RUN_ID_INVALID")
    receipt = store.idempotent_result("media-job:" + driver_run_id)
    if receipt is None:
        # A crash after atomic approval consumption can precede job claim.
        committed = store.load_state("driverrun-" + driver_run_id)
        return {"driverRunId": driver_run_id,
                "state": "indeterminate" if committed else "not_found",
                "safeToResubmit": False}
    return {"driverRunId": driver_run_id,
            "state": str(receipt.get("state") or "indeterminate"),
            "operationId": receipt.get("operationId"),
            "artifactCandidate": receipt.get("artifactCandidate"),
            "resultText": receipt.get("resultText"),
            "safeToResubmit": False,
            "failureCode": receipt.get("failureCode")}


def _job_update(store: Any, key: str, fingerprint: str, value: dict[str, Any]) -> None:
    store.complete_claimed_command(key, fingerprint, value)


def submit_approved_media(
    service: Any, request_id: str, metadata: dict[str, Any],
    *, registry: MediaRouteRegistry,
    transport: MediaHTTPTransport,
    credential_resolver,
) -> dict[str, Any]:
    """Single dispatch. HumanApproval consumed+DriverRun persisted BEFORE HTTP."""
    approved, binding = _get_binding(service, request_id)
    driver = binding.get("driverRunId")
    if not isinstance(driver, str) or not _JOB_RE.fullmatch(driver):
        raise AuthorityViolation("MEDIA_RUN_ID_INVALID")
    job_key = "media-job:" + driver
    if approved.get("state") == "consumed":
        return media_job_status(service.store, driver)
    if approved.get("state") != "approved":
        raise AuthorityViolation("MEDIA_HUMAN_APPROVAL_REQUIRED")
    route = registry.resolve(binding["adapterId"], binding["provider"],
                             binding["model"], binding["operation"])
    _route_matches_binding(route, binding)
    if route.maximum_price_usd > binding["maxCostUSD"]:
        raise AuthorityViolation("MEDIA_ROUTE_COST_CHANGED")
    if route.contract.origin != binding["endpointOrigin"] or (
        route.contract.submit_path != binding["endpointPath"]
    ):
        raise AuthorityViolation("MEDIA_ROUTE_CHANGED_SINCE_APPROVAL")
    if not binding.get("files") and binding["operation"] in ("image_input", "document_input", "video_input", "audio_transcribe"):
        raise AuthorityViolation("MEDIA_SOURCE_MISSING")
    # TOCTOU: recheck every source file/digest before consuming one-use approval.
    _verified_files(binding["files"], state_root=Path(service.store.path).parent,
                    operation=binding["operation"], max_input_bytes=MAX_INLINE_BYTES)
    body, content_type = _build_request(binding, route)
    token = "" if route.auth_style == "none" else credential_resolver(route.provider)
    auth = _authorization(route, token)
    prepared_digest = _hash({"binding": binding, "requestBytesSHA256":
                             hashlib.sha256(body).hexdigest()})
    inner = commands.command(
        command_id=metadata["commandId"] + "-dispatch",
        idempotency_key="idem-media-dispatch-" + driver,
        operation_fingerprint=commands.fingerprint(
            "media_admit", {"manifestDigest": binding["manifestDigest"], "driverRunId": driver}),
        correlation_id=metadata["correlationId"], actor_id="exec-media",
        actor_kind="execution_plane", issued_at=metadata["issuedAt"],
        replay_policy="never",
    )
    admit = service.admit_approved_model_execution(
        request_id, binding["manifestDigest"], "ModelMediaExecution",
        mission_id=binding["missionId"], task_id=binding["taskId"],
        driver_run_id=driver, resource=binding["targetRoot"],
        use_id="media:" + driver, now=_issued_at(), metadata=inner,
        driver_id="provider", prepared_execution_digest=prepared_digest,
    )
    if admit.get("status") == "idempotent":
        return media_job_status(service.store, driver)
    fingerprint = _hash({"driver": driver, "manifestDigest": binding["manifestDigest"]})
    service.store.claim_command(job_key, fingerprint, metadata["commandId"])
    from . import commands as _commands
    boundary_meta = _commands.command(
        command_id=metadata["commandId"] + "-boundary",
        idempotency_key="media-dispatch-boundary:" + driver,
        operation_fingerprint=_hash({"driver": driver, "boundary": "request_started"}),
        correlation_id=metadata["correlationId"], actor_id="exec-media",
        actor_kind="execution_plane", issued_at=_issued_at(), replay_policy="never",
    )
    service.record_driver_dispatch_boundary(driver, "request_started", boundary_meta)
    try:
        headers = {**auth, "Content-Type": content_type}
        raw, mime = transport.send("POST",
            route.contract.origin + route.contract.submit_path,
            body, headers, 64 * 1024 * 1024)
        if (binding["operation"] == "image_generate" and
                route.contract.response_type == "json_url"):
            content, media_type = _download_approved_image(
                raw, route, transport, token, binding["maxOutputBytes"]
            )
            operation_id = None
        else:
            content, media_type, operation_id = _result_bytes(
                binding["operation"], raw, route.contract.response_type
            )
        if media_type not in (None, "text/plain") and media_type not in route.contract.media_types:
            raise AuthorityViolation("MEDIA_PROVIDER_OUTPUT_MIME_NOT_ADVERTISED")
        if operation_id:
            state = {"state": "submitted", "operationId": operation_id,
                     "adapterId": route.adapter_id, "manifestDigest": binding["manifestDigest"]}
        else:
            candidate = _artifact(
                state_root=Path(service.store.path).parent,
                driver_run_id=driver, blob=content, mime=media_type
            )
            state = {"state": "completed", "artifactCandidate": candidate,
                     "resultText": content.decode("utf-8") if media_type == "text/plain" else None,
                     "manifestDigest": binding["manifestDigest"]}
        _job_update(service.store, job_key, fingerprint, state)
        return media_job_status(service.store, driver)
    except Exception as exc:
        # A request may already have crossed the paid boundary. Never auto-retry.
        _job_update(service.store, job_key, fingerprint,
                    {"state": "indeterminate", "manifestDigest": binding["manifestDigest"],
                     "failureCode": type(exc).__name__})
        raise


def _job_binding(
    service: Any, request_id: str, registry: MediaRouteRegistry,
) -> tuple[dict[str, Any], MediaRoute, str, dict[str, Any]]:
    approval, binding = _get_binding(service, request_id)
    driver = str(binding.get("driverRunId") or "")
    if not _JOB_RE.fullmatch(driver):
        raise AuthorityViolation("MEDIA_RUN_ID_INVALID")
    if approval.get("state") != "consumed" or approval.get("consumedBy") != "media:" + driver:
        raise AuthorityViolation("MEDIA_JOB_NOT_APPROVED_AND_CONSUMED")
    route = registry.resolve(binding["adapterId"], binding["provider"],
                             binding["model"], binding["operation"])
    _route_matches_binding(route, binding)
    if route.contract.origin != binding["endpointOrigin"] or route.contract.submit_path != binding["endpointPath"]:
        raise AuthorityViolation("MEDIA_JOB_ENDPOINT_CHANGED")
    if route.maximum_price_usd > binding["maxCostUSD"]:
        raise AuthorityViolation("MEDIA_JOB_PRICE_CEILING_CHANGED")
    receipt = service.store.idempotent_result("media-job:" + driver)
    if not isinstance(receipt, dict):
        raise AuthorityViolation("MEDIA_JOB_RECEIPT_MISSING")
    if receipt.get("manifestDigest") != binding["manifestDigest"]:
        raise AuthorityViolation("MEDIA_JOB_RECEIPT_TAMPERED")
    return binding, route, driver, receipt


def _poll_path(contract: MediaAdapterContract, operation_id: str) -> str:
    if not contract.poll_path:
        raise AuthorityViolation("MEDIA_POLL_UNSUPPORTED")
    if not re.fullmatch(r"operations/[A-Za-z0-9_./-]{4,200}", operation_id) or ".." in operation_id:
        raise AuthorityViolation("MEDIA_JOB_OPERATION_INVALID")
    path = contract.poll_path.replace("{job_id}", operation_id)
    if "{job_id}" in path or "{" in path or "}" in path:
        raise AuthorityViolation("MEDIA_JOB_ENDPOINT_TEMPLATE_UNRESOLVED")
    # Strings derived from an external job receipt still cannot select
    # a new domain, dot-traversal segment, or arbitrary file-system path.
    if not path.startswith("/") or path.startswith("//") or any(
        segment in (".", "..") for segment in path.split("/")
    ):
        raise AuthorityViolation("MEDIA_JOB_POLL_PATH_UNSAFE")
    return path


def _extract_video_url(document: dict[str, Any]) -> str:
    response = document.get("response") or {}
    if not isinstance(response, dict):
        raise AuthorityViolation("MEDIA_VIDEO_RESULT_INVALID")
    container = response.get("generateVideoResponse") or response
    if not isinstance(container, dict):
        raise AuthorityViolation("MEDIA_VIDEO_RESULT_INVALID")
    samples = container.get("generatedSamples") or container.get("generatedVideos") or []
    if not isinstance(samples, list) or not samples or not isinstance(samples[0], dict):
        raise AuthorityViolation("MEDIA_VIDEO_ASSET_MISSING")
    video = samples[0].get("video") or {}
    url = video.get("uri") if isinstance(video, dict) else None
    if not isinstance(url, str) or not url:
        raise AuthorityViolation("MEDIA_VIDEO_ASSET_URL_MISSING")
    return url


def poll_media_job(
    service: Any, request_id: str, *, registry: MediaRouteRegistry,
    transport: MediaHTTPTransport, credential_resolver
) -> dict[str, Any]:
    """GET only. An operation ID exists; never calls generation submit path."""
    binding, route, driver, receipt = _job_binding(service, request_id, registry)
    if binding["operation"] != "video_generate" or route.contract.transport != "async_job":
        raise AuthorityViolation("MEDIA_POLL_NOT_VIDEO_JOB")
    if receipt["state"] in ("completed", "ready_to_download", "indeterminate", "failed"):
        return media_job_status(service.store, driver)
    if receipt["state"] not in ("submitted", "processing"):
        raise AuthorityViolation("MEDIA_POLL_STATE_INVALID")
    operation_id = str(receipt.get("operationId") or "")
    poll_url = route.contract.origin + _poll_path(route.contract, operation_id)
    auth = _authorization(route, "" if route.auth_style == "none" else credential_resolver(route.provider))
    try:
        raw, _ = transport.send("GET", poll_url, None, auth, 512 * 1024)
        document = json.loads(raw)
        if not isinstance(document, dict) or not isinstance(document.get("done"), bool):
            raise AuthorityViolation("MEDIA_VIDEO_POLL_RESPONSE_INVALID")
        updated = dict(receipt)
        if not document["done"]:
            updated["state"] = "processing"
        elif document.get("error"):
            updated["state"] = "failed"
            updated["failureCode"] = "MEDIA_PROVIDER_JOB_FAILED"
        else:
            url = _extract_video_url(document)
            if not route.contract.permits_download(url):
                raise AuthorityViolation("MEDIA_VIDEO_DOWNLOAD_HOST_REFUSED")
            updated["state"] = "ready_to_download"
            # Sealed by EventStore's existing encrypted idempotency column.
            # Never return a signed URL to Chat or diagnostics.
            updated["downloadUrl"] = url
        _job_update(service.store, "media-job:" + driver,
                    _hash({"driver": driver, "manifestDigest": binding["manifestDigest"]}),
                    updated)
        return media_job_status(service.store, driver)
    except Exception:
        # GET may be retried manually. Preserve last state and operation ID;
        # never re-submit the generation request.
        raise


def fetch_media_artifact(
    service: Any, request_id: str, *, registry: MediaRouteRegistry,
    transport: MediaHTTPTransport, credential_resolver
) -> dict[str, Any]:
    """Download an already-completed approved video. Never starts generation."""
    binding, route, driver, receipt = _job_binding(service, request_id, registry)
    if binding["operation"] != "video_generate":
        raise AuthorityViolation("MEDIA_FETCH_NOT_VIDEO")
    if receipt["state"] == "completed":
        return media_job_status(service.store, driver)
    if receipt["state"] != "ready_to_download":
        raise AuthorityViolation("MEDIA_VIDEO_NOT_READY")
    url = str(receipt.get("downloadUrl") or "")
    if not route.contract.permits_download(url):
        raise AuthorityViolation("MEDIA_VIDEO_DOWNLOAD_HOST_REFUSED")
    key = "media-download:" + driver
    fingerprint = _hash({"driver": driver, "assetOrigin": urlsplit(url).netloc,
                         "manifestDigest": binding["manifestDigest"]})
    claim = service.store.claim_command(key, fingerprint, "cmd-media-download-" + driver)
    if claim.get("replayed"):
        # It may have passed the irreversible GET boundary before a crash.
        # Never automatically re-download, even though GET is nominally safe.
        return media_job_status(service.store, driver)
    try:
        # Never forward a provider bearer key to a distinct asset/CDN host.
        asset_auth = (_authorization(
            route, "" if route.auth_style == "none" else credential_resolver(route.provider)
        ) if urlsplit(url).scheme + "://" + urlsplit(url).netloc == route.contract.origin else {})
        ceiling = min(route.contract.max_asset_bytes, binding["maxOutputBytes"])
        if isinstance(transport, MediaHTTPTransport):
            candidate = _download_video_streaming(
                url, asset_auth, ceiling,
                state_root=Path(service.store.path).parent,
                driver_run_id=driver
            )
        else:
            data, content_type = transport.send(
                "GET", url, None, asset_auth, min(ceiling, 64 * 1024 * 1024)
            )
            kind = content_type.split(";", 1)[0].strip().lower()
            if kind not in ("video/mp4", "application/octet-stream"):
                raise AuthorityViolation("MEDIA_VIDEO_CONTENT_TYPE_MISMATCH")
            if len(data) < 12 or data[4:8] != b"ftyp":
                raise AuthorityViolation("MEDIA_VIDEO_MAGIC_INVALID")
            candidate = _artifact(
                state_root=Path(service.store.path).parent,
                driver_run_id=driver, blob=data, mime="video/mp4",
                max_bytes=ceiling
            )
        updated = {k: v for k, v in receipt.items() if k != "downloadUrl"}
        updated.update({"state": "completed", "artifactCandidate": candidate})
        _job_update(service.store, "media-job:" + driver,
                    _hash({"driver": driver, "manifestDigest": binding["manifestDigest"]}),
                    updated)
        service.store.complete_claimed_command(
            key, fingerprint, {"state": "completed",
                               "artifactDigest": candidate["artifactDigest"]}
        )
        return media_job_status(service.store, driver)
    except Exception as exc:
        service.store.complete_claimed_command(
            key, fingerprint, {"state": "indeterminate", "failureCode": type(exc).__name__}
        )
        raise


def _media_output_directory(state_root: Path, driver_run_id: str) -> Path:
    """One confined private media output directory, rejecting symlink swaps."""
    root = state_root / "media-output" / "v2" / driver_run_id
    if not _JOB_RE.fullmatch(driver_run_id):
        raise AuthorityViolation("MEDIA_RUN_ID_INVALID")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    base = (state_root / "media-output" / "v2").resolve()
    if (base != state_root.resolve() / "media-output" / "v2" or
        root.is_symlink() or root.resolve() != base / driver_run_id or not root.is_dir()):
        raise AuthorityViolation("MEDIA_OUTPUT_ROOT_UNSAFE")
    os.chmod(root, 0o700)
    return root


def _download_video_streaming(
    url: str, headers: dict[str, str], max_bytes: int,
    *, state_root: Path, driver_run_id: str
) -> dict[str, Any]:
    """Production video download streams to a private file, not RAM."""
    root = _media_output_directory(state_root, driver_run_id)
    target = root / "result.mp4"
    part = root / "download.partial"
    request = urllib.request.Request(url, headers=headers, method="GET")
    hasher = hashlib.sha256()
    counted = 0
    first = b""
    try:
        opener = urllib.request.build_opener(NoRedirectHandler())
        with opener.open(request, timeout=90) as response:
            if response.status != 200:
                raise AuthorityViolation("MEDIA_VIDEO_DOWNLOAD_HTTP_REJECTED")
            kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if kind not in ("video/mp4", "application/octet-stream"):
                raise AuthorityViolation("MEDIA_VIDEO_CONTENT_TYPE_MISMATCH")
            with part.open("xb") as file:
                os.chmod(part, 0o600)
                while True:
                    chunk = response.read(1_048_576)
                    if not chunk:
                        break
                    counted += len(chunk)
                    if counted > max_bytes:
                        raise AuthorityViolation("MEDIA_VIDEO_DOWNLOAD_OVERSIZE")
                    if len(first) < 12:
                        first += chunk[:12-len(first)]
                    hasher.update(chunk)
                    file.write(chunk)
                file.flush()
                os.fsync(file.fileno())
        if counted < 12 or first[4:8] != b"ftyp":
            raise AuthorityViolation("MEDIA_VIDEO_MAGIC_INVALID")
        # Never overwrite an earlier candidate; a retry after uncertain GET
        # is blocked by the separate durable media-download claim.
        if target.exists() or target.is_symlink():
            raise AuthorityViolation("MEDIA_VIDEO_ARTIFACT_ALREADY_EXISTS")
        os.link(part, target)
        return {
            "artifactPath": str(target), "artifactDigest": "sha256:" + hasher.hexdigest(),
            "mediaType": "video/mp4", "sizeBytes": counted,
            "trust": "untrusted", "verificationState": "pending_human_verification"
        }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise AuthorityViolation(
            "MEDIA_DOWNLOAD_HTTP_" + str(getattr(exc, "code", "UNAVAILABLE"))
        ) from None
    finally:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
