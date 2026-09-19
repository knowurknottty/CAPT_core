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

from capt_runtime.cloudflare_resource_adoption import CloudflareResourceBindingRegistry
from capt_runtime.errors import AuthorityViolation, IntegrityViolation

from .cloudflare_ai_catalog import (
    CloudflareAIModelCatalogSnapshot,
    parse_cloudflare_ai_model_catalog,
)
from .cloudflare_artifacts import CloudflareBinaryArtifactSpool
from .cloudflare_native import CloudflareBrowserAction, CloudflareDispatchNotStarted
from .cloudflare_resource_inventory import (
    CloudflareResourceInventorySnapshot,
    CloudflareResourceKind,
    parse_cloudflare_resource_inventory,
)
from .cloudflare_workflows import (
    MAX_WORKFLOW_EVENT_BYTES,
    MAX_WORKFLOW_START_PARAMS_BYTES,
    canonical_json,
    require_event_type,
    require_provider_status,
    require_workflow_instance_id,
    require_workflow_name,
    workflow_instance_id,
)

_API_ROOT = "https://api.cloudflare.com/client/v4"
_ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_ALIAS_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
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
    worker_alias: str = "capt-control"
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
        if not _ALIAS_RE.fullmatch(self.worker_alias):
            raise AuthorityViolation("CLOUDFLARE_NATIVE_WORKER_ALIAS_INVALID")
        if self.queue_ids or self.d1_database_ids:
            raise AuthorityViolation("CLOUDFLARE_NATIVE_RAW_RESOURCE_IDS_FORBIDDEN")
        object.__setattr__(self, "worker_base_url", self.worker_base_url.rstrip("/"))
        object.__setattr__(self, "queue_ids", {})
        object.__setattr__(self, "d1_database_ids", {})


class CloudflareNativeAPIBridge:
    def __init__(
        self,
        profile: CloudflareNativeAPIProfile,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        now: Callable[[], datetime] | None = None,
        binding_registry: CloudflareResourceBindingRegistry | None = None,
        artifact_spool: CloudflareBinaryArtifactSpool | None = None,
    ) -> None:
        self.profile = profile
        self.opener = opener
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.binding_registry = binding_registry
        self.artifact_spool = artifact_spool

    def _require_binding(self, kind: CloudflareResourceKind, target_alias: str) -> dict[str, Any]:
        if self.binding_registry is None:
            raise CloudflareDispatchNotStarted("CLOUDFLARE_RESOURCE_BINDING_REGISTRY_REQUIRED")
        try:
            return self.binding_registry.resolve(self.profile.account_id, kind, target_alias)
        except (AuthorityViolation, IntegrityViolation) as exc:
            raise CloudflareDispatchNotStarted(str(exc)) from exc

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

    def _post_binary(
        self, url: str, token: str, payload: dict[str, Any]
    ) -> tuple[bytes, str]:
        if self.artifact_spool is None:
            raise CloudflareDispatchNotStarted(
                "CLOUDFLARE_BROWSER_BINARY_ARTIFACT_SPOOL_REQUIRED"
            )
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
                raw = response.read(self.artifact_spool.max_bytes + 1)
                headers = getattr(response, "headers", None)
                content_type = headers.get("Content-Type") if hasattr(headers, "get") else None
        except urllib.error.HTTPError as exc:
            raise CloudflareProviderRejected(
                f"cloudflare_http_rejected:{exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("cloudflare_transport_outcome_unclassified") from exc
        if len(raw) > self.artifact_spool.max_bytes:
            raise RuntimeError("cloudflare_browser_binary_artifact_too_large")
        if not isinstance(content_type, str) or not content_type:
            raise RuntimeError("cloudflare_browser_binary_content_type_missing")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type == "application/json":
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("cloudflare_browser_binary_json_unclassified") from exc
            if isinstance(value, dict) and value.get("success") is False:
                self._require_success(value)
            raise RuntimeError("cloudflare_browser_binary_response_unclassified")
        return raw, media_type

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

    def resource_inventory(self) -> CloudflareResourceInventorySnapshot:
        token = self._secret(self.profile.api_token_env)
        d1_rows: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urlencode({"page": page, "per_page": 100})
            url = f"{_API_ROOT}/accounts/{self.profile.account_id}/d1/database?{query}"
            value = self._get(url, token)
            result = self._require_success(value)
            info = value.get("result_info")
            if not isinstance(result, list) or not isinstance(info, dict):
                raise RuntimeError("cloudflare_d1_inventory_pagination_unclassified")
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
                raise RuntimeError("cloudflare_d1_inventory_pagination_unclassified")
            if not all(isinstance(item, dict) for item in result):
                raise RuntimeError("cloudflare_d1_inventory_result_unclassified")
            d1_rows.extend(result)
            if page >= total_pages:
                break
            page += 1
        queue_value = self._get(
            f"{_API_ROOT}/accounts/{self.profile.account_id}/queues", token
        )
        queue_rows = self._require_success(queue_value)
        if not isinstance(queue_rows, list) or not all(
            isinstance(item, dict) for item in queue_rows
        ):
            raise RuntimeError("cloudflare_queue_inventory_result_unclassified")
        worker_value = self._get(
            f"{_API_ROOT}/accounts/{self.profile.account_id}/workers/scripts", token
        )
        worker_rows = self._require_success(worker_value)
        if not isinstance(worker_rows, list) or not all(
            isinstance(item, dict) for item in worker_rows
        ):
            raise RuntimeError("cloudflare_worker_inventory_result_unclassified")
        workflow_rows: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urlencode({"page": page, "per_page": 100})
            value = self._get(
                f"{_API_ROOT}/accounts/{self.profile.account_id}/workflows?{query}",
                token,
            )
            result = self._require_success(value)
            info = value.get("result_info")
            if not isinstance(result, list) or not isinstance(info, dict):
                raise RuntimeError("cloudflare_workflow_inventory_pagination_unclassified")
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
                raise RuntimeError("cloudflare_workflow_inventory_pagination_unclassified")
            if not all(isinstance(item, dict) for item in result):
                raise RuntimeError("cloudflare_workflow_inventory_result_unclassified")
            workflow_rows.extend(result)
            if page >= total_pages:
                break
            page += 1
        fetched_at = self.now()
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise RuntimeError("cloudflare_resource_inventory_clock_unaware")
        return parse_cloudflare_resource_inventory(
            account_id=self.profile.account_id,
            d1_rows=d1_rows,
            queue_rows=queue_rows,
            worker_rows=worker_rows,
            fetched_at=fetched_at,
            workflow_rows=workflow_rows,
        )

    def _workflow_binding(self, workflow: str) -> tuple[dict[str, Any], str, str]:
        binding = self._require_binding(CloudflareResourceKind.WORKFLOW, workflow)
        if binding.get("targetEndpoint") is not None:
            raise CloudflareDispatchNotStarted("CLOUDFLARE_WORKFLOW_BINDING_ENDPOINT_FORBIDDEN")
        resource_id = binding.get("resourceId")
        resource_name = binding.get("resourceName")
        if not isinstance(resource_id, str) or not resource_id:
            raise CloudflareDispatchNotStarted("CLOUDFLARE_WORKFLOW_BINDING_ID_INVALID")
        try:
            resource_name = require_workflow_name(resource_name)
        except ValueError as exc:
            raise CloudflareDispatchNotStarted(str(exc)) from exc
        return binding, resource_id, resource_name

    def workflow_expected_instance_id(self, *, operation_id: str, workflow: str) -> str:
        if not operation_id:
            raise ValueError("cloudflare_workflow_operation_id_required")
        _, resource_id, _ = self._workflow_binding(workflow)
        return workflow_instance_id(self.profile.account_id, resource_id, operation_id)

    def workflow_instance_start(
        self, *, operation_id: str, workflow: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if not operation_id:
            raise ValueError("cloudflare_workflow_operation_id_required")
        _, resource_id, resource_name = self._workflow_binding(workflow)
        encoded_params = canonical_json(
            params, max_bytes=MAX_WORKFLOW_START_PARAMS_BYTES, code="cloudflare_workflow_start_params"
        )
        instance_id = self.workflow_expected_instance_id(operation_id=operation_id, workflow=workflow)
        value = self._post(
            f"{_API_ROOT}/accounts/{self.profile.account_id}/workflows/{quote(resource_name, safe='')}/instances",
            self._secret(self.profile.api_token_env),
            {"instance_id": instance_id, "params": encoded_params},
        )
        result = self._require_success(value)
        if not isinstance(result, dict):
            raise RuntimeError("cloudflare_workflow_start_result_unclassified")
        if result.get("id") != instance_id:
            raise RuntimeError("cloudflare_workflow_instance_id_mismatch")
        if result.get("workflow_id") != resource_id:
            raise RuntimeError("cloudflare_workflow_resource_id_mismatch")
        status = require_provider_status(result.get("status"))
        return {"instanceId": instance_id, "status": status, "workflowId": resource_id, "versionId": result.get("version_id")}

    def workflow_instance_status(self, *, workflow: str, instance_id: str) -> dict[str, Any]:
        require_workflow_instance_id(instance_id)
        _, resource_id, resource_name = self._workflow_binding(workflow)
        value = self._get(
            f"{_API_ROOT}/accounts/{self.profile.account_id}/workflows/{quote(resource_name, safe='')}/instances/{quote(instance_id, safe='')}",
            self._secret(self.profile.api_token_env),
        )
        result = self._require_success(value)
        if not isinstance(result, dict):
            raise RuntimeError("cloudflare_workflow_status_result_unclassified")
        status = require_provider_status(result.get("status"))
        return {"instanceId": instance_id, "workflowId": resource_id, "status": status, "evidence": result}

    def workflow_instance_event(
        self, *, operation_id: str, workflow: str, instance_id: str, event_type: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        if not operation_id:
            raise ValueError("cloudflare_workflow_operation_id_required")
        require_workflow_instance_id(instance_id)
        event_type = require_event_type(event_type)
        _, _, resource_name = self._workflow_binding(workflow)
        envelope = {"operationId": operation_id, "payload": body}
        canonical_json(envelope, max_bytes=MAX_WORKFLOW_EVENT_BYTES, code="cloudflare_workflow_event_body")
        value = self._post(
            f"{_API_ROOT}/accounts/{self.profile.account_id}/workflows/{quote(resource_name, safe='')}/instances/{quote(instance_id, safe='')}/events/{quote(event_type, safe='')}",
            self._secret(self.profile.api_token_env),
            envelope,
        )
        result = self._require_success(value)
        if not isinstance(result, dict):
            raise RuntimeError("cloudflare_workflow_event_result_unclassified")
        if result.get("instanceId") != instance_id:
            raise RuntimeError("cloudflare_workflow_event_instance_id_mismatch")
        timestamp = result.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp:
            raise RuntimeError("cloudflare_workflow_event_timestamp_unclassified")
        return {"instanceId": instance_id, "timestamp": timestamp, "eventType": event_type}

    def workflow_instance_step_evidence(
        self, *, operation_id: str, workflow: str, instance_id: str,
        step_name: str, step_type: str, attempt: int | None = None,
    ) -> dict[str, Any]:
        if self.artifact_spool is None:
            raise CloudflareDispatchNotStarted("CLOUDFLARE_WORKFLOW_STEP_ARTIFACT_SPOOL_REQUIRED")
        if not operation_id:
            raise ValueError("cloudflare_workflow_operation_id_required")
        require_workflow_instance_id(instance_id)
        if not isinstance(step_name, str) or not step_name or len(step_name) > 512:
            raise ValueError("cloudflare_workflow_step_name_invalid")
        if step_type not in {"step", "waitForEvent"}:
            raise ValueError("cloudflare_workflow_step_type_invalid")
        if attempt is not None and (isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1):
            raise ValueError("cloudflare_workflow_step_attempt_invalid")
        _, _, resource_name = self._workflow_binding(workflow)
        query_data: dict[str, Any] = {"name": step_name, "type": step_type}
        if attempt is not None:
            query_data["attempt"] = attempt
        url = (
            f"{_API_ROOT}/accounts/{self.profile.account_id}/workflows/{quote(resource_name, safe='')}/"
            f"instances/{quote(instance_id, safe='')}/step?{urlencode(query_data)}"
        )
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self._secret(self.profile.api_token_env)}"}, method="GET"
        )
        try:
            with self.opener(request, timeout=30.0) as response:
                raw = response.read(self.artifact_spool.max_bytes + 1)
                headers = getattr(response, "headers", None)
                content_type = headers.get("Content-Type") if hasattr(headers, "get") else None
        except urllib.error.HTTPError as exc:
            raise CloudflareProviderRejected(f"cloudflare_http_rejected:{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("cloudflare_transport_outcome_unclassified") from exc
        if len(raw) > self.artifact_spool.max_bytes:
            raise RuntimeError("cloudflare_workflow_step_artifact_too_large")
        if not isinstance(content_type, str) or not content_type:
            raise RuntimeError("cloudflare_workflow_step_content_type_missing")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type == "application/octet-stream":
            manifest = self.artifact_spool.capture_workflow_step(
                operation_id=operation_id, data=raw, media_type=media_type
            )
            return {
                "kind": "binary", "artifactRef": manifest["ref"],
                "artifactSha256": manifest["sha256"], "artifactBytes": manifest["bytes"],
                "mediaType": manifest["mediaType"], "artifactAction": manifest["action"],
            }
        if media_type != "application/json":
            raise RuntimeError("cloudflare_workflow_step_content_type_unclassified")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("cloudflare_workflow_step_json_unclassified") from exc
        if not isinstance(value, dict):
            raise RuntimeError("cloudflare_workflow_step_result_unclassified")
        result = self._require_success(value)
        if not isinstance(result, dict):
            raise RuntimeError("cloudflare_workflow_step_result_unclassified")
        status = require_provider_status(result.get("status"))
        return {
            "kind": "json", "status": status, "error": result.get("error"),
            "output": result.get("output"), "eventType": result.get("event_type"),
        }

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
        binding = self._require_binding(CloudflareResourceKind.WORKER_SCRIPT, self.profile.worker_alias)
        if binding.get("targetEndpoint") != self.profile.worker_base_url:
            raise CloudflareDispatchNotStarted("CLOUDFLARE_WORKER_ENDPOINT_BINDING_MISMATCH")
        url = self.profile.worker_base_url + route
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
        binding = self._require_binding(CloudflareResourceKind.QUEUE, queue)
        queue_id = str(binding["resourceId"])
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
        binding = self._require_binding(CloudflareResourceKind.D1_DATABASE, database)
        database_id = str(binding["resourceId"])
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
        url = (
            f"{_API_ROOT}/accounts/{self.profile.account_id}/browser-rendering/"
            f"{action.value}"
        )
        if action in {CloudflareBrowserAction.PDF, CloudflareBrowserAction.SCREENSHOT}:
            if self.artifact_spool is None:
                raise CloudflareDispatchNotStarted(
                    "CLOUDFLARE_BROWSER_BINARY_ARTIFACT_SPOOL_REQUIRED"
                )
            token = self._secret(self.profile.api_token_env)
            if action is CloudflareBrowserAction.SCREENSHOT:
                url += "?encoding=binary"
            artifact_bytes, media_type = self._post_binary(url, token, arguments)
            allowed_media = (
                {"image/png", "image/jpeg", "image/webp"}
                if action is CloudflareBrowserAction.SCREENSHOT
                else {"application/pdf"}
            )
            if media_type not in allowed_media:
                raise RuntimeError("cloudflare_browser_binary_media_type_mismatch")
            manifest = self.artifact_spool.capture(
                operation_id=operation_id,
                action=action,
                media_type=media_type,
                data=artifact_bytes,
            )
            return {
                "browserSeconds": estimated_seconds,
                "artifactRef": manifest["ref"],
                "artifactSha256": manifest["sha256"],
                "artifactBytes": manifest["bytes"],
                "mediaType": manifest["mediaType"],
                "artifactAction": manifest["action"],
                "usageBasis": "reserved_ceiling",
            }
        token = self._secret(self.profile.api_token_env)
        value = self._post(url, token, arguments)
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
