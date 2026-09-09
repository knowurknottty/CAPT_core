"""Typed free-tier-native Cloudflare execution surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .cloudflare_ai_catalog import CloudflareAIModelCatalogSnapshot
from .cloudflare_free_planner import CloudflareFreeExecutionPlanner
from .cloudflare_free_router import CloudflareFreeEstimate, CloudflareWorkClass


class CloudflareBrowserAction(str, Enum):
    CONTENT = "content"
    SCRAPE = "scrape"
    SCREENSHOT = "screenshot"
    PDF = "pdf"


class CloudflareDispatchNotStarted(RuntimeError):
    """Provider effect is proven not to have started; reservation may be released."""


class CloudflareNativeIndeterminate(RuntimeError):
    """Provider effect outcome cannot be classified safely; reservation stays locked."""


@dataclass(frozen=True)
class CloudflareWorkersResult:
    operation_id: str
    status_code: int
    body: Any
    effect: str = "workers_request_completed"


@dataclass(frozen=True)
class CloudflareQueueResult:
    operation_id: str
    message_id: str
    effect: str = "queue_message_enqueued"


class CloudflareWorkersCoordinator:
    def __init__(self, planner: CloudflareFreeExecutionPlanner, bridge: Any) -> None:
        self.planner = planner
        self.bridge = bridge

    def coordinate(
        self,
        *,
        operation_id: str,
        route: str,
        payload: dict[str, Any],
        cpu_ms: int,
        day: date,
    ) -> CloudflareWorkersResult:
        self.planner.reserve(
            operation_id=operation_id,
            work_class=CloudflareWorkClass.COORDINATION,
            estimate=CloudflareFreeEstimate(worker_requests=1, worker_cpu_ms=cpu_ms),
            day=day,
        )
        try:
            response = self.bridge.worker_request(
                operation_id=operation_id,
                route=route,
                payload=payload,
                cpu_ms=cpu_ms,
            )
        except CloudflareDispatchNotStarted:
            self.planner.ledger.release(operation_id, reason="workers_dispatch_not_started")
            raise
        except Exception as exc:
            raise CloudflareNativeIndeterminate(
                "workers_dispatch_outcome_unclassified"
            ) from exc
        self.planner.ledger.commit(operation_id)
        status = response.get("status")
        if isinstance(status, bool) or not isinstance(status, int):
            raise CloudflareNativeIndeterminate("workers_response_status_unclassified")
        return CloudflareWorkersResult(
            operation_id=operation_id,
            status_code=status,
            body=response.get("body"),
        )


class CloudflareQueueDelegator:
    def __init__(self, planner: CloudflareFreeExecutionPlanner, bridge: Any) -> None:
        self.planner = planner
        self.bridge = bridge

    def delegate(
        self,
        *,
        operation_id: str,
        queue: str,
        body: dict[str, Any],
        day: date,
    ) -> CloudflareQueueResult:
        self.planner.reserve(
            operation_id=operation_id,
            work_class=CloudflareWorkClass.DELEGATION,
            estimate=CloudflareFreeEstimate(queue_operations=1),
            day=day,
        )
        try:
            response = self.bridge.queue_send(
                operation_id=operation_id,
                queue=queue,
                body=body,
            )
        except CloudflareDispatchNotStarted:
            self.planner.ledger.release(operation_id, reason="queue_dispatch_not_started")
            raise
        except Exception as exc:
            raise CloudflareNativeIndeterminate(
                "queue_dispatch_outcome_unclassified"
            ) from exc
        message_id = response.get("messageId")
        if not isinstance(message_id, str) or not message_id:
            raise CloudflareNativeIndeterminate("queue_message_identity_unclassified")
        self.planner.ledger.commit(operation_id)
        return CloudflareQueueResult(
            operation_id=operation_id,
            message_id=message_id,
        )


@dataclass(frozen=True)
class CloudflareD1ReadResult:
    operation_id: str
    rows: tuple[dict[str, Any], ...]
    rows_read: int
    effect: str = "d1_read_completed"


@dataclass(frozen=True)
class CloudflareD1WriteResult:
    operation_id: str
    change_id: str
    rows_written: int
    effect: str = "d1_write_completed"


@dataclass(frozen=True)
class CloudflareBrowserResult:
    operation_id: str
    artifact_ref: str
    browser_seconds: int
    usage_basis: str
    effect: str = "browser_run_completed"


@dataclass(frozen=True)
class CloudflareWorkersAIResult:
    operation_id: str
    model: str
    output: Any
    neurons: int
    usage_basis: str
    catalog_digest: str
    catalog_fetched_at: str
    effect: str = "workers_ai_inference_completed"


class CloudflareD1StateStore:
    def __init__(self, planner: CloudflareFreeExecutionPlanner, bridge: Any) -> None:
        self.planner = planner
        self.bridge = bridge

    def read(
        self,
        *,
        operation_id: str,
        database: str,
        statement: str,
        params: list[Any],
        estimated_rows_read: int,
        day: date,
    ) -> CloudflareD1ReadResult:
        self.planner.reserve(
            operation_id=operation_id,
            work_class=CloudflareWorkClass.SHARED_STATE,
            estimate=CloudflareFreeEstimate(d1_rows_read=estimated_rows_read),
            day=day,
        )
        try:
            response = self.bridge.d1_read(
                operation_id=operation_id,
                database=database,
                statement=statement,
                params=params,
            )
        except CloudflareDispatchNotStarted:
            self.planner.ledger.release(operation_id, reason="d1_read_not_started")
            raise
        except Exception as exc:
            raise CloudflareNativeIndeterminate("d1_read_outcome_unclassified") from exc
        rows_read = response.get("rowsRead")
        rows = response.get("rows")
        if not isinstance(rows_read, int) or rows_read < 0 or not isinstance(rows, list):
            raise CloudflareNativeIndeterminate("d1_read_evidence_unclassified")
        if rows_read > estimated_rows_read:
            raise CloudflareNativeIndeterminate("d1_read_actual_usage_exceeded_reservation")
        self.planner.ledger.commit(operation_id)
        return CloudflareD1ReadResult(operation_id, tuple(rows), rows_read)

    def write(
        self,
        *,
        operation_id: str,
        database: str,
        statement: str,
        params: list[Any],
        estimated_rows_written: int,
        day: date,
    ) -> CloudflareD1WriteResult:
        self.planner.reserve(
            operation_id=operation_id,
            work_class=CloudflareWorkClass.SHARED_STATE,
            estimate=CloudflareFreeEstimate(d1_rows_written=estimated_rows_written),
            day=day,
        )
        try:
            response = self.bridge.d1_write(
                operation_id=operation_id,
                database=database,
                statement=statement,
                params=params,
            )
        except CloudflareDispatchNotStarted:
            self.planner.ledger.release(operation_id, reason="d1_write_not_started")
            raise
        except Exception as exc:
            raise CloudflareNativeIndeterminate("d1_write_outcome_unclassified") from exc
        rows_written = response.get("rowsWritten")
        change_id = response.get("changeId")
        if not isinstance(rows_written, int) or rows_written < 0:
            raise CloudflareNativeIndeterminate("d1_write_evidence_unclassified")
        if not isinstance(change_id, str) or not change_id:
            raise CloudflareNativeIndeterminate("d1_change_identity_unclassified")
        if rows_written > estimated_rows_written:
            raise CloudflareNativeIndeterminate("d1_write_actual_usage_exceeded_reservation")
        self.planner.ledger.commit(operation_id)
        return CloudflareD1WriteResult(operation_id, change_id, rows_written)


class CloudflareBrowserRunner:
    def __init__(self, planner: CloudflareFreeExecutionPlanner, bridge: Any) -> None:
        self.planner = planner
        self.bridge = bridge

    def run(
        self,
        *,
        operation_id: str,
        action: CloudflareBrowserAction,
        arguments: dict[str, Any],
        estimated_seconds: int,
        day: date,
    ) -> CloudflareBrowserResult:
        if not isinstance(action, CloudflareBrowserAction):
            raise ValueError("cloudflare_browser_action_invalid")
        self.planner.reserve(
            operation_id=operation_id,
            work_class=CloudflareWorkClass.BROWSER,
            estimate=CloudflareFreeEstimate(browser_seconds=estimated_seconds),
            day=day,
        )
        try:
            response = self.bridge.browser_run(
                operation_id=operation_id,
                action=action,
                arguments=arguments,
                estimated_seconds=estimated_seconds,
            )
        except CloudflareDispatchNotStarted:
            self.planner.ledger.release(operation_id, reason="browser_run_not_started")
            raise
        except Exception as exc:
            raise CloudflareNativeIndeterminate("browser_run_outcome_unclassified") from exc
        seconds = response.get("browserSeconds")
        artifact_ref = response.get("artifactRef")
        usage_basis = response.get("usageBasis")
        if not isinstance(seconds, int) or seconds < 0:
            raise CloudflareNativeIndeterminate("browser_usage_evidence_unclassified")
        if not isinstance(artifact_ref, str) or not artifact_ref:
            raise CloudflareNativeIndeterminate("browser_artifact_identity_unclassified")
        if usage_basis not in {"provider_reported", "reserved_ceiling"}:
            raise CloudflareNativeIndeterminate("browser_usage_basis_unclassified")
        if usage_basis == "reserved_ceiling" and seconds != estimated_seconds:
            raise CloudflareNativeIndeterminate("browser_reserved_ceiling_mismatch")
        if usage_basis == "provider_reported" and seconds > estimated_seconds:
            raise CloudflareNativeIndeterminate("browser_actual_usage_exceeded_reservation")
        self.planner.ledger.commit(operation_id)
        return CloudflareBrowserResult(operation_id, artifact_ref, seconds, usage_basis)


class CloudflareWorkersAIInferencer:
    def __init__(self, planner: CloudflareFreeExecutionPlanner, bridge: Any) -> None:
        self.planner = planner
        self.bridge = bridge

    def infer(
        self,
        *,
        operation_id: str,
        model: str,
        input_payload: dict[str, Any],
        estimated_neurons: int,
        day: date,
    ) -> CloudflareWorkersAIResult:
        try:
            catalog = self.bridge.ai_model_catalog()
        except CloudflareDispatchNotStarted:
            raise
        except Exception as exc:
            raise CloudflareDispatchNotStarted(
                "CLOUDFLARE_AI_CATALOG_DISCOVERY_UNCLASSIFIED"
            ) from exc
        if not isinstance(catalog, CloudflareAIModelCatalogSnapshot):
            raise CloudflareDispatchNotStarted(
                "CLOUDFLARE_AI_CATALOG_RESULT_INVALID"
            )
        self.planner.reserve(
            operation_id=operation_id,
            work_class=CloudflareWorkClass.INFERENCE,
            estimate=CloudflareFreeEstimate(
                ai_model=model,
                ai_neurons=estimated_neurons,
            ),
            day=day,
            ai_catalog=catalog,
        )
        try:
            response = self.bridge.workers_ai(
                operation_id=operation_id,
                model=model,
                input_payload=input_payload,
                estimated_neurons=estimated_neurons,
            )
        except CloudflareDispatchNotStarted:
            self.planner.ledger.release(operation_id, reason="workers_ai_not_started")
            raise
        except Exception as exc:
            raise CloudflareNativeIndeterminate("workers_ai_outcome_unclassified") from exc
        neurons = response.get("neurons")
        usage_basis = response.get("usageBasis")
        if not isinstance(neurons, int) or neurons < 0:
            raise CloudflareNativeIndeterminate("workers_ai_usage_evidence_unclassified")
        if usage_basis not in {"provider_reported", "reserved_ceiling"}:
            raise CloudflareNativeIndeterminate("workers_ai_usage_basis_unclassified")
        if usage_basis == "reserved_ceiling" and neurons != estimated_neurons:
            raise CloudflareNativeIndeterminate("workers_ai_reserved_ceiling_mismatch")
        if usage_basis == "provider_reported" and neurons > estimated_neurons:
            raise CloudflareNativeIndeterminate("workers_ai_actual_usage_exceeded_reservation")
        self.planner.ledger.commit(operation_id)
        return CloudflareWorkersAIResult(
            operation_id=operation_id,
            model=model,
            output=response.get("output"),
            neurons=neurons,
            usage_basis=usage_basis,
            catalog_digest=catalog.source_digest,
            catalog_fetched_at=catalog.fetched_at.isoformat(),
        )


@dataclass(frozen=True)
class CloudflareNativeSurfaces:
    workers: CloudflareWorkersCoordinator
    queues: CloudflareQueueDelegator
    d1: CloudflareD1StateStore
    browser: CloudflareBrowserRunner
    ai: CloudflareWorkersAIInferencer
