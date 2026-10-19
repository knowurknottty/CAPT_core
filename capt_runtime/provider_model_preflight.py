"""Non-inference model availability probe for OpenRouter.

One read-only authenticated GET before costly inference, restricted to the exact
official OpenRouter origin. It cannot select a replacement model or change
CAPT-granted tool authority. No prompt or user content is transmitted.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from . import http_client

_ID = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+$")


class ProviderModelPreflightError(ValueError):
    def __init__(self, code: str, *, http_status: int | None = None):
        super().__init__(code)
        self.code = code
        self.http_status = http_status


def verify_openrouter_model(model: str, *, api_key: str, modality: str = "text") -> dict:
    """Confirm catalog presence without any inference POST or credential redirect.

    Caller already authorizes access to OpenRouter under the model dispatch
    authority. Authentication credentials are never logged or returned.
    """
    if not isinstance(model, str) or not _ID.fullmatch(model):
        raise ProviderModelPreflightError("PROVIDER_MODEL_ID_INVALID")
    if modality not in {"text", "image"}:
        raise ProviderModelPreflightError("PROVIDER_OUTPUT_MODALITY_INVALID")
    if not isinstance(api_key, str) or not api_key:
        raise ProviderModelPreflightError("PROVIDER_CREDENTIAL_UNAVAILABLE")
    if modality == "text":
        author, slug = model.split("/", 1)
        url = "https://openrouter.ai/api/v1/model/" + urllib.parse.quote(author, safe="") + "/" + urllib.parse.quote(slug, safe="")
    else:
        url = "https://openrouter.ai/api/v1/images/models"
    req = urllib.request.Request(url, method="GET", headers={
        "Accept": "application/json",
        "Authorization": "Bearer " + api_key,
    })
    try:
        with http_client.open_url(req, timeout=6.0) as response:
            data = json.loads(http_client.read_bounded(response, limit=2_000_000))
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        if status == 404:
            raise ProviderModelPreflightError("PROVIDER_MODEL_UNAVAILABLE", http_status=404) from exc
        if status in (401, 402, 403):
            raise ProviderModelPreflightError("PROVIDER_ACCOUNT_UNAVAILABLE", http_status=status) from exc
        raise ProviderModelPreflightError("PROVIDER_MODEL_PREFLIGHT_UNAVAILABLE", http_status=status) from exc
    except (TimeoutError, OSError, ValueError, UnicodeError, json.JSONDecodeError, http_client.ResponseTooLarge) as exc:
        raise ProviderModelPreflightError("PROVIDER_MODEL_PREFLIGHT_UNAVAILABLE") from exc
    if not isinstance(data, dict) or "data" not in data:
        raise ProviderModelPreflightError("PROVIDER_MODEL_PREFLIGHT_INVALID")
    if modality == "image":
        records=data["data"]
        if not isinstance(records, list):
            raise ProviderModelPreflightError("PROVIDER_MODEL_PREFLIGHT_INVALID")
        matched=next((item for item in records if isinstance(item,dict) and item.get("id")==model),None)
        if matched is None:
            raise ProviderModelPreflightError("PROVIDER_MODEL_UNAVAILABLE")
        output=(matched.get("architecture") or {}).get("output_modalities")
        if not isinstance(output,list) or "image" not in output:
            raise ProviderModelPreflightError("PROVIDER_MODEL_UNAVAILABLE")
        return {"model":model, "modality":"image", "available":True}
    record=data["data"]
    if not isinstance(record,dict) or not isinstance(record.get("id"),str):
        raise ProviderModelPreflightError("PROVIDER_MODEL_PREFLIGHT_INVALID")
    return {"model":model, "modality":"text", "available":True}
