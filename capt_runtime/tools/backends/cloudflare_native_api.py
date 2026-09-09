"""Existing-resource-only Cloudflare API bridge for CAPT free-native surfaces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode, urlparse

from capt_runtime.errors import AuthorityViolation

from .cloudflare_ai_catalog import (
    CloudflareAIModelCatalogSnapshot,
    parse_cloudflare_ai_model_catalog,
)
from .cloudflare_native import CloudflareBrowserAction, CloudflareDispatchNotStarted

_API_ROOT = "https://api.cloudflare.com/client/v4"
_ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class CloudflareProviderRejected(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CloudflareNativeAPIProfile:
    account_id: str
    api_token_env: str
    worker_base_url: str
    worker_auth_env: str
    queue_ids: Mapping[str, str] = None  # type: ignore[assignment]
    d1_database_ids: Mapping[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if not self.account_id or len(self.account_id) > 32:
            raise AuthorityViolation("CLOUDFLARE_NATIVE_ACCOUNT_ID_INVALID")
        for value in (self.api_token_env, self.worker_auth_env):
            if not _ENV_RE.fullmatch(value):
                raise AuthorityViolation("CLOUDFLARE_NATIVE_SECRET_ENV_INVALID")
        parsed = urlparse(self.worker_base_url)
        if not parsed.hostname or parsed.scheme not in {"http", "https"}:
            raise AuthorityViolation("CLOUDFLARE_NATIVE_WORKER_URL_INVALID")
        if parsed.scheme != "https" and parsed.hostname not in _LOCAL_HOSTS:
            raise AuthorityViolation("CLOUDFLARE_NATIVE_WORKER_REQUIRES_HTTPS")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise AuthorityViolation("CLOUDFLARE_NATIVE_WORKER_URL_INVALID")
        object.__setattr__(self, "queue_ids", dict(self.queue_ids or {}))
        object.__setattr__(self, "d1_database_ids", dict(self.d1_database_ids or {}))


class CloudflareNativeAPIBridge:
    def __init__(
        self,
        profile: CloudflareNativeAPIProfile,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.profile = profile
        self.opener = opener
        self.now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _secret(env_name: str) -> str:
        value = os.environ.get(env_name)
        if not value:
            raise CloudflareDispatchNotStarted(f"CLOUDFLARE_SECRET_UNAVAILABLE:{env_name}")
        return value

    def _post(self, url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=30.0) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise CloudflareProviderRejected(
                f"cloudflare_http_rejected:{exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("cloudflare_transport_outcome_unclassified") from exc
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("cloudflare_response_json_unclassified") from exc
        if not isinstance(value, dict):
            raise RuntimeError("cloudflare_response_root_unclassified")
        return value

    def _get(self, url: str, token: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with self.opener(request, timeout=30.0) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise CloudflareProviderRejected(
                f"cloudflare_http_rejected:{exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("cloudflare_transport_outcome_unclassified") from exc
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("cloudflare_response_json_unclassified") from exc
        if not isinstance(value, dict):
            raise RuntimeError("cloudflare_response_root_unclassified")
        return value

    @staticmethod
    def _require_success(value: dict[str, Any]) -> Any:
        if value.get("success") is True:
            return value.get("result")
        errors = value.get("errors")
        code = "unclassified"
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            raw_code = errors[0].get("code")
            if raw_code is not None:
                code = str(raw_code)
        raise CloudflareProviderRejected(f"cloudflare_api_rejected:{code}")

    def ai_model_catalog(self) -> CloudflareAIModelCatalogSnapshot:
        token = self._secret(self.profile.api_token_env)
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urlencode({"page": page, "per_page": 100, "include_deprecated": "false"})
            url = f"{_API_ROOT}/accounts/{self.profile.account_id}/ai/models/search?{query}"
            value = self._get(url, token)
            result = self._require_success(value)
            info = value.get("result_info")
            if not isinstance(result, list) or not isinstance(info, dict):
                raise RuntimeError("cloudflare_ai_catalog_pagination_unclassified")
            current_page = info.get("page")
            total_pages = info.get("total_pages")
            if (
                isinstance(current_page, bool)
                or not isinstance(current_page, int)
                or isinstance(total_pages, bool)
                or not isinstance(total_pages, int)
                or current_page != page
                or total_pages < page
                or total_pages < 1
                or total_pages > 100
            ):
                raise RuntimeError("cloudflare_ai_catalog_pagination_unclassified")
            if not all(isinstance(item, dict) for item in result):
                raise RuntimeError("cloudflare_ai_catalog_result_unclassified")
            rows.extend(result)
            if page >= total_pages:
                break
            page += 1
        fetched_at = self.now()
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise RuntimeError("cloudflare_ai_catalog_clock_unaware")
        return parse_cloudflare_ai_model_catalog(rows, fetched_at=fetched_at)

    def worker_request(
        self,
        *,
        operation_id: str,
        route: str,
        payload: dict[str, Any],
        cpu_ms: int,
    ) -> dict[str, Any]:
        if not route.startswith("/") or ".." in route.split("/"):
            raise CloudflareDispatchNotStarted("CLOUDFLARE_WORKER_ROUTE_INVALID")
        url = self.profile.worker_base_url.rstrip("/") + route
        value = self._post(
            url,
            self._secret(self.profile.worker_auth_env),
            {"operationId": operation_id, "payload": payload, "cpuBudgetMs": cpu_ms},
        )
        return {"status": 200, "body": value}

    def queue_send(
        self,
        *,
        operation_id: str,
        queue: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        queue_id = self.profile.queue_ids.get(queue)
        if not queue_id:
            raise CloudflareDispatchNotStarted("CLOUDFLARE_QUEUE_RESOURCE_NOT_CONFIGURED")
        url = f"{_API_ROOT}/accounts/{self.profile.account_id}/queues/{queue_id}/messages"
        value = self._post(
            url,
            self._secret(self.profile.api_token_env),
            {
                "body": {"operationId": operation_id, "payload": body},
                "content_type": "json",
            },
        )
        self._require_success(value)
        return {"messageId": f"capt:{operation_id}"}

    def _d1_query(
        self,
        *,
        database: str,
        statement: str,
        params: list[Any],
    ) -> dict[str, Any]:
        database_id = self.profile.d1_database_ids.get(database)
        if not database_id:
            raise CloudflareDispatchNotStarted("CLOUDFLARE_D1_RESOURCE_NOT_CONFIGURED")
        url = (
            f"{_API_ROOT}/accounts/{self.profile.account_id}/d1/database/"
            f"{database_id}/query"
        )
        value = self._post(
            url,
            self._secret(self.profile.api_token_env),
            {"sql": statement, "params": params},
        )
        result = self._require_success(value)
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
            raise RuntimeError("cloudflare_d1_result_shape_unclassified")
        query = result[0]
        if query.get("success") is not True:
            raise CloudflareProviderRejected("cloudflare_d1_query_rejected")
        return query

    def d1_read(
        self,
        *,
        operation_id: str,
        database: str,
        statement: str,
        params: list[Any],
    ) -> dict[str, Any]:
        query = self._d1_query(database=database, statement=statement, params=params)
        meta = query.get("meta") or {}
        rows = query.get("results") or []
        rows_read = meta.get("rows_read")
        if not isinstance(rows_read, int) or rows_read < 0 or not isinstance(rows, list):
            raise RuntimeError("cloudflare_d1_read_evidence_unclassified")
        return {"rows": rows, "rowsRead": rows_read}

    def d1_write(
        self,
        *,
        operation_id: str,
        database: str,
        statement: str,
        params: list[Any],
    ) -> dict[str, Any]:
        query = self._d1_query(database=database, statement=statement, params=params)
        meta = query.get("meta") or {}
        rows_written = meta.get("rows_written")
        if not isinstance(rows_written, int) or rows_written < 0:
            raise RuntimeError("cloudflare_d1_write_evidence_unclassified")
        return {
            "rowsWritten": rows_written,
            "changeId": f"capt:{operation_id}",
        }

    def browser_run(
        self,
        *,
        operation_id: str,
        action: CloudflareBrowserAction,
        arguments: dict[str, Any],
        estimated_seconds: int,
    ) -> dict[str, Any]:
        if not isinstance(action, CloudflareBrowserAction):
            raise AuthorityViolation("CLOUDFLARE_BROWSER_ACTION_INVALID")
        if action in {CloudflareBrowserAction.PDF, CloudflareBrowserAction.SCREENSHOT}:
            raise CloudflareDispatchNotStarted(
                "CLOUDFLARE_BROWSER_BINARY_ARTIFACT_CAPTURE_NOT_IMPLEMENTED"
            )
        url = (
            f"{_API_ROOT}/accounts/{self.profile.account_id}/browser-rendering/"
            f"{action.value}"
        )
        value = self._post(
            url,
            self._secret(self.profile.api_token_env),
            arguments,
        )
        result = self._require_success(value)
        if isinstance(result, str):
            artifact_bytes = result.encode("utf-8")
        else:
            artifact_bytes = json.dumps(
                result, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        return {
            "browserSeconds": estimated_seconds,
            "artifactRef": "sha256:" + hashlib.sha256(artifact_bytes).hexdigest(),
            "usageBasis": "reserved_ceiling",
        }

    def workers_ai(
        self,
        *,
        operation_id: str,
        model: str,
        input_payload: dict[str, Any],
        estimated_neurons: int,
    ) -> dict[str, Any]:
        model_path = quote(model, safe="@/")
        url = f"{_API_ROOT}/accounts/{self.profile.account_id}/ai/run/{model_path}"
        value = self._post(
            url,
            self._secret(self.profile.api_token_env),
            input_payload,
        )
        result = self._require_success(value)
        return {
            "neurons": estimated_neurons,
            "output": result,
            "usageBasis": "reserved_ceiling",
        }
