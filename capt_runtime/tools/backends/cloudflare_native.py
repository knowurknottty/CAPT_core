"""Typed free-tier-native Cloudflare execution surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .cloudflare_ai_catalog import CloudflareAIModelCatalogSnapshot
from .cloudflare_free_planner import CloudflareFreeExecutionPlanner
from .cloudflare_free_router import CloudflareFreeEstimate, CloudflareWorkClass
from .cloudflare_workflows import require_provider_status


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
    artifact_sha256: str | None = None
    artifact_bytes: int | None = None
    media_type: str | None = None
    artifact_action: str | None = None
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
        artifact_sha256 = response.get("artifactSha256")
        artifact_bytes = response.get("artifactBytes")
        media_type = response.get("mediaType")
        artifact_action = response.get("artifactAction")
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
        if action in {CloudflareBrowserAction.PDF, CloudflareBrowserAction.SCREENSHOT}:
            if not artifact_ref.startswith("cloudflare-artifact://"):
                raise CloudflareNativeIndeterminate("browser_binary_artifact_ref_unclassified")
            if not isinstance(artifact_sha256, str) or not artifact_sha256.startswith("sha256:"):
                raise CloudflareNativeIndeterminate("browser_binary_artifact_digest_unclassified")
            if isinstance(artifact_bytes, bool) or not isinstance(artifact_bytes, int) or artifact_bytes < 1:
                raise CloudflareNativeIndeterminate("browser_binary_artifact_size_unclassified")
            if not isinstance(media_type, str) or not media_type:
                raise CloudflareNativeIndeterminate("browser_binary_artifact_media_type_unclassified")
            if artifact_action != action.value:
                raise CloudflareNativeIndeterminate("browser_binary_artifact_action_mismatch")
        self.planner.ledger.commit(operation_id)
        return CloudflareBrowserResult(
            operation_id=operation_id,
            artifact_ref=artifact_ref,
            browser_seconds=seconds,
            usage_basis=usage_basis,
            artifact_sha256=artifact_sha256,
            artifact_bytes=artifact_bytes,
            media_type=media_type,
            artifact_action=artifact_action,
        )


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


class CloudflareWorkflowIndeterminate(CloudflareNativeIndeterminate):
    def __init__(
        self,
        code: str,
        *,
        operation_id: str,
        instance_id: str | None,
        estimate: CloudflareFreeEstimate | None = None,
    ) -> None:
        self.code = code
        self.operation_id = operation_id
        self.instance_id = instance_id
        self.estimate = estimate
        super().__init__(code)


@dataclass(frozen=True)
class CloudflareWorkflowStartResult:
    operation_id: str
    workflow: str
    instance_id: str
    provider_status: str
    estimate: CloudflareFreeEstimate
    effect: str = "workflow_instance_start_acknowledged"


@dataclass(frozen=True)
class CloudflareWorkflowStatusResult:
    workflow: str
    instance_id: str
    provider_status: str
    evidence: Any
    estimate: CloudflareFreeEstimate | None = None
    effect: str = "workflow_provider_status_observed"


@dataclass(frozen=True)
class CloudflareWorkflowEventResult:
    operation_id: str
    workflow: str
    instance_id: str
    event_type: str
    timestamp: str
    effect: str = "workflow_event_acknowledged"


@dataclass(frozen=True)
class CloudflareWorkflowStepEvidenceResult:
    operation_id: str
    workflow: str
    instance_id: str
    evidence: dict[str, Any]
    effect: str = "workflow_step_evidence_observed"


class CloudflareWorkflowOrchestrator:
    def __init__(self, planner: CloudflareFreeExecutionPlanner, bridge: Any) -> None:
        self.planner = planner
        self.bridge = bridge

    def start(
        self,
        *,
        operation_id: str,
        workflow: str,
        params: dict[str, Any],
        max_steps: int,
        day: date,
    ) -> CloudflareWorkflowStartResult:
        instance_id = self.bridge.workflow_expected_instance_id(
            operation_id=operation_id, workflow=workflow
        )
        estimate = CloudflareFreeEstimate(workflow_steps=max_steps)
        self.planner.reserve(
            operation_id=operation_id,
            work_class=CloudflareWorkClass.DURABLE_ORCHESTRATION,
            estimate=estimate,
            day=day,
        )
        try:
            response = self.bridge.workflow_instance_start(
                operation_id=operation_id, workflow=workflow, params=params
            )
        except CloudflareDispatchNotStarted:
            self.planner.ledger.release(
                operation_id, reason="workflow_start_not_started"
            )
            raise
        except Exception as exc:
            raise CloudflareWorkflowIndeterminate(
                "workflow_instance_start_indeterminate",
                operation_id=operation_id,
                instance_id=instance_id,
                estimate=estimate,
            ) from exc
        if response.get("instanceId") != instance_id:
            raise CloudflareWorkflowIndeterminate(
                "workflow_instance_start_identity_unclassified",
                operation_id=operation_id,
                instance_id=instance_id,
                estimate=estimate,
            )
        try:
            status = require_provider_status(response.get("status"))
        except Exception as exc:
            raise CloudflareWorkflowIndeterminate(
                "workflow_instance_start_status_unclassified",
                operation_id=operation_id,
                instance_id=instance_id,
                estimate=estimate,
            ) from exc
        self.planner.ledger.commit(operation_id)
        return CloudflareWorkflowStartResult(
            operation_id, workflow, instance_id, status, estimate
        )

    def reconcile_start(
        self,
        *,
        operation_id: str,
        workflow: str,
        max_steps: int,
        day: date,
    ) -> CloudflareWorkflowStatusResult:
        instance_id = self.bridge.workflow_expected_instance_id(
            operation_id=operation_id, workflow=workflow
        )
        estimate = CloudflareFreeEstimate(workflow_steps=max_steps)
        try:
            checked = self.planner.ledger.require_reservation_match(
                operation_id,
                CloudflareWorkClass.DURABLE_ORCHESTRATION.value,
                estimate,
                day=day,
            )
        except KeyError as exc:
            raise CloudflareDispatchNotStarted(
                "CLOUDFLARE_WORKFLOW_RESERVATION_NOT_FOUND"
            ) from exc
        if checked["state"] == "released":
            raise CloudflareDispatchNotStarted(
                "CLOUDFLARE_WORKFLOW_RESERVATION_RELEASED"
            )
        try:
            response = self.bridge.workflow_instance_status(
                workflow=workflow, instance_id=instance_id
            )
        except Exception as exc:
            raise CloudflareWorkflowIndeterminate(
                "workflow_instance_reconciliation_indeterminate",
                operation_id=operation_id,
                instance_id=instance_id,
                estimate=estimate,
            ) from exc
        try:
            status = require_provider_status(response.get("status"))
        except Exception as exc:
            raise CloudflareWorkflowIndeterminate(
                "workflow_instance_reconciliation_status_unclassified",
                operation_id=operation_id,
                instance_id=instance_id,
                estimate=estimate,
            ) from exc
        self.planner.ledger.commit(operation_id)
        return CloudflareWorkflowStatusResult(
            workflow=workflow,
            instance_id=instance_id,
            provider_status=status,
            evidence=response.get("evidence"),
            estimate=estimate,
            effect="workflow_instance_start_reconciled",
        )

    def status(
        self, *, workflow: str, instance_id: str
    ) -> CloudflareWorkflowStatusResult:
        response = self.bridge.workflow_instance_status(
            workflow=workflow, instance_id=instance_id
        )
        status = require_provider_status(response.get("status"))
        return CloudflareWorkflowStatusResult(
            workflow=workflow,
            instance_id=instance_id,
            provider_status=status,
            evidence=response.get("evidence"),
        )

    def event(
        self,
        *,
        operation_id: str,
        workflow: str,
        instance_id: str,
        event_type: str,
        body: dict[str, Any],
    ) -> CloudflareWorkflowEventResult:
        try:
            response = self.bridge.workflow_instance_event(
                operation_id=operation_id,
                workflow=workflow,
                instance_id=instance_id,
                event_type=event_type,
                body=body,
            )
        except CloudflareDispatchNotStarted:
            raise
        except Exception as exc:
            raise CloudflareWorkflowIndeterminate(
                "workflow_event_delivery_indeterminate",
                operation_id=operation_id,
                instance_id=instance_id,
            ) from exc
        if response.get("instanceId") != instance_id:
            raise CloudflareWorkflowIndeterminate(
                "workflow_event_identity_unclassified",
                operation_id=operation_id,
                instance_id=instance_id,
            )
        timestamp = response.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp:
            raise CloudflareWorkflowIndeterminate(
                "workflow_event_timestamp_unclassified",
                operation_id=operation_id,
                instance_id=instance_id,
            )
        return CloudflareWorkflowEventResult(
            operation_id, workflow, instance_id, event_type, timestamp
        )

    def step_evidence(
        self,
        *,
        operation_id: str,
        workflow: str,
        instance_id: str,
        step_name: str,
        step_type: str,
        attempt: int | None = None,
    ) -> CloudflareWorkflowStepEvidenceResult:
        evidence = self.bridge.workflow_instance_step_evidence(
            operation_id=operation_id,
            workflow=workflow,
            instance_id=instance_id,
            step_name=step_name,
            step_type=step_type,
            attempt=attempt,
        )
        if not isinstance(evidence, dict) or evidence.get("kind") not in {
            "json",
            "binary",
        }:
            raise RuntimeError("cloudflare_workflow_step_evidence_unclassified")
        return CloudflareWorkflowStepEvidenceResult(
            operation_id, workflow, instance_id, evidence
        )


@dataclass(frozen=True)
class CloudflareNativeSurfaces:
    workers: CloudflareWorkersCoordinator
    queues: CloudflareQueueDelegator
    d1: CloudflareD1StateStore
    browser: CloudflareBrowserRunner
    ai: CloudflareWorkersAIInferencer
    workflows: CloudflareWorkflowOrchestrator
