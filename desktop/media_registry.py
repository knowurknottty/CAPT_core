"""Load explicit operator-owned media routes; never infer modalities from names.

No configured routes = no media provider authority. A route is usable only
if its provider/model is present in the existing operator provider registry
and its declared capability includes that modality.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from capt_runtime.errors import AuthorityViolation
from capt_runtime.media_adapter_contract import MediaAdapterContract
from capt_runtime.media_execution import MediaRoute, MediaRouteRegistry
from desktop.prompt_compiler_provider import _load_providers
from capt_ui.operator.secrets import resolve as resolve_secret

_ALLOWED_CAPS = {
    "image_input": {"vision"},
    "image_generate": {"image", "image_generation"},
    "audio_generate": {"audio", "audio_generation", "tts"},
    "audio_transcribe": {"audio", "transcription"},
    "video_generate": {"video", "video_generation"},
}


def load_media_routes(ui: Path) -> tuple[MediaRouteRegistry, dict[str, str]]:
    ui = Path(ui)
    path = ui / "media-routes.json"
    if not path.is_file():
        return MediaRouteRegistry({}), {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schemaVersion") != "1.0.0":
        raise AuthorityViolation("MEDIA_ROUTE_REGISTRY_SCHEMA_INVALID")
    rows = data.get("routes", [])
    if not isinstance(rows, list) or len(rows) > 100:
        raise AuthorityViolation("MEDIA_ROUTE_REGISTRY_SIZE_INVALID")
    providers = {p.get("id"): p for p in _load_providers(ui)
                 if isinstance(p, dict) and p.get("enabled") is True}
    routes: dict[str, MediaRoute] = {}
    key_refs: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("enabled") is not True:
            continue
        provider_id = str(row.get("provider") or "")
        provider = providers.get(provider_id)
        model = str(row.get("model") or "")
        if not provider:
            raise AuthorityViolation("MEDIA_PROVIDER_NOT_REGISTERED")
        model_ids = provider.get("models") or []
        if not isinstance(model_ids, list) or model not in model_ids:
            raise AuthorityViolation("MEDIA_MODEL_NOT_REGISTERED")
        operation = str(row.get("operation") or "")
        capabilities = {str(x) for x in provider.get("capabilities") or []}
        if not (_ALLOWED_CAPS.get(operation, set()) & capabilities):
            raise AuthorityViolation("MEDIA_PROVIDER_OPERATION_NOT_DECLARED")
        base = urlsplit(str(provider.get("base_url") or ""))
        base_origin = base.scheme + "://" + base.netloc
        contract = MediaAdapterContract(
            provider_id=provider_id,
            origin=str(row.get("origin") or ""),
            operation=operation,
            transport=str(row.get("transport") or ""),
            submit_path=str(row.get("submitPath") or ""),
            response_type=str(row.get("responseType") or ""),
            media_types=tuple(row.get("mediaTypes") or []),
            poll_path=row.get("pollPath"),
            result_path=row.get("resultPath"),
            download_origins=tuple(row.get("downloadOrigins") or ()),
            max_asset_bytes=int(row.get("maxAssetBytes") or 64 * 1024 * 1024),
            allow_loopback=base.hostname in ("localhost", "127.0.0.1", "::1"),
        )
        if contract.origin != base_origin:
            raise AuthorityViolation("MEDIA_ROUTE_ORIGIN_MUST_MATCH_PROVIDER_REGISTRY")
        route = MediaRoute(
            adapter_id=str(row.get("adapterId") or ""), provider=provider_id,
            model=model, contract=contract,
            auth_style=str(row.get("authStyle") or "bearer"),
            maximum_price_usd=float(row.get("maximumPriceUSD")),
        )
        route.validate()
        if route.adapter_id in routes:
            raise AuthorityViolation("MEDIA_ROUTE_DUPLICATE")
        routes[route.adapter_id] = route
        key_refs[provider_id] = str(provider.get("key_ref") or "")
    return MediaRouteRegistry(routes), key_refs


def media_credential_provider(key_refs: dict[str, str]):
    def resolve(provider_id: str) -> str:
        return resolve_secret(provider_id, key_refs.get(provider_id, ""))
    return resolve


def media_route_catalog(registry: MediaRouteRegistry) -> list[dict]:
    return [
        {
            "adapterId": r.adapter_id, "provider": r.provider, "model": r.model,
            "operation": r.contract.operation,
            "mediaTypes": list(r.contract.media_types),
            "maximumPriceUSD": r.maximum_price_usd,
            "transport": r.contract.transport,
            "requiresHumanApproval": True,
            "canDispatch": True,
        }
        for r in registry.routes.values()
    ]
