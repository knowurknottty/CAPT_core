"""Human-configurable governed Council workflow contract.

This module is presentation/orchestration glue only. It builds exact approval
intents and council launch payloads; RuntimeService remains the authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from capt_runtime.cohort_contract import MAX_COHORTS, MAX_VESSELS_PER_COHORT


class CouncilWorkflowError(ValueError):
    """A human-authored Council workflow is invalid or incomplete."""


def _slug(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip()).strip("-")
    if not out:
        raise CouncilWorkflowError("WORKFLOW_IDENTIFIER_REQUIRED")
    return out[:120]


@dataclass(frozen=True)
class CohortWorkflow:
    cohort_id: str
    provider: str
    model: str
    objective: str
    vessels_per_cohort: int
    configuration_id: str = "default"
    task_id: str = ""
    driver_run_id: str = ""

    def validate(self) -> "CohortWorkflow":
        if not self.cohort_id.strip():
            raise CouncilWorkflowError("COHORT_ID_REQUIRED")
        if not self.provider.strip() or not self.model.strip():
            raise CouncilWorkflowError("COHORT_PROVIDER_MODEL_REQUIRED")
        if not self.objective.strip():
            raise CouncilWorkflowError("COHORT_OBJECTIVE_REQUIRED")
        vessels = self.vessels_per_cohort
        if isinstance(vessels, bool) or not isinstance(vessels, int):
            raise CouncilWorkflowError("COHORT_VESSEL_COUNT_INVALID")
        if not 1 <= vessels <= MAX_VESSELS_PER_COHORT:
            raise CouncilWorkflowError("COHORT_VESSEL_COUNT_RANGE")
        if not self.configuration_id.strip():
            raise CouncilWorkflowError("COHORT_CONFIGURATION_ID_REQUIRED")
        return self

    def to_record(self) -> dict[str, Any]:
        return {
            "cohortId": self.cohort_id,
            "provider": self.provider,
            "model": self.model,
            "objective": self.objective,
            "vesselsPerCohort": self.vessels_per_cohort,
            "configurationId": self.configuration_id,
            "taskId": self.task_id,
            "driverRunId": self.driver_run_id,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CohortWorkflow":
        return cls(
            cohort_id=str(value.get("cohortId") or ""),
            provider=str(value.get("provider") or ""),
            model=str(value.get("model") or ""),
            objective=str(value.get("objective") or ""),
            vessels_per_cohort=int(value.get("vesselsPerCohort") or 0),
            configuration_id=str(value.get("configurationId") or "default"),
            task_id=str(value.get("taskId") or ""),
            driver_run_id=str(value.get("driverRunId") or ""),
        )


@dataclass(frozen=True)
class CouncilWorkflow:
    council_id: str
    mission_id: str
    target_root: str
    cohorts: tuple[CohortWorkflow, ...]
    max_concurrent_cohorts: int = 1
    requested_context_budget: int = 128_000
    requested_execution_seconds: int = 900
    response_mode: str = "SPOCK"
    prompt_enhancement: str = "OFF"
    human_verification_required: bool = True
    file_mutation_allowed: bool = True
    shell_access_allowed: bool = True
    provider_network_policy: str = "remote_allowed"
    charter_schema_version: str = "2.0.0"

    @property
    def logical_vessels(self) -> int:
        return sum(c.vessels_per_cohort for c in self.cohorts)

    def validate(self, *, require_target_exists: bool = True) -> "CouncilWorkflow":
        _slug(self.council_id)
        _slug(self.mission_id)
        if not self.target_root.strip():
            raise CouncilWorkflowError("COUNCIL_TARGET_ROOT_REQUIRED")
        if require_target_exists:
            root = Path(self.target_root).expanduser().resolve(strict=False)
            if not root.exists() or not root.is_dir():
                raise CouncilWorkflowError("COUNCIL_TARGET_ROOT_NOT_DIRECTORY")
        if not 1 <= len(self.cohorts) <= MAX_COHORTS:
            raise CouncilWorkflowError("COUNCIL_COHORT_COUNT_RANGE")
        if isinstance(self.max_concurrent_cohorts, bool):
            raise CouncilWorkflowError("COUNCIL_CONCURRENCY_INVALID")
        if not 1 <= self.max_concurrent_cohorts <= len(self.cohorts):
            raise CouncilWorkflowError("COUNCIL_CONCURRENCY_RANGE")
        if not 1 <= self.requested_context_budget <= 10_000_000:
            raise CouncilWorkflowError("COUNCIL_CONTEXT_BUDGET_RANGE")
        if not 60 <= self.requested_execution_seconds <= 3600:
            raise CouncilWorkflowError("COUNCIL_EXECUTION_SECONDS_RANGE")
        ids = []
        counts = set()
        for cohort in self.cohorts:
            cohort.validate()
            ids.append(cohort.cohort_id)
            counts.add(cohort.vessels_per_cohort)
        if len(set(ids)) != len(ids):
            raise CouncilWorkflowError("COUNCIL_DUPLICATE_COHORT_ID")
        if len(counts) != 1:
            raise CouncilWorkflowError("COUNCIL_VESSEL_COUNT_MISMATCH")
        return self

    def _authority_profile(self) -> dict[str, Any]:
        return {
            "filesystemScope": "project",
            "filesystemRoot": str(Path(self.target_root).expanduser().resolve(strict=False)),
            "fileMutationAllowed": bool(self.file_mutation_allowed),
            "shellAccessAllowed": bool(self.shell_access_allowed),
            "providerNetworkPolicy": self.provider_network_policy,
        }

    def approval_payloads(self) -> list[dict[str, Any]]:
        self.validate()
        mission_slug = _slug(self.mission_id)
        payloads: list[dict[str, Any]] = []
        for cohort in self.cohorts:
            cohort_slug = _slug(cohort.cohort_id)
            task_id = cohort.task_id or f"t-{mission_slug}-{cohort_slug}"
            run_id = cohort.driver_run_id or f"dr-{mission_slug}-{cohort_slug}"
            payloads.append({
                "objective": cohort.objective,
                "targetRoot": str(Path(self.target_root).expanduser().resolve()),
                "provider": cohort.provider,
                "model": cohort.model,
                "missionId": self.mission_id,
                "taskId": task_id,
                "driverRunId": run_id,
                "requestedContextBudget": self.requested_context_budget,
                "requestedExecutionSeconds": self.requested_execution_seconds,
                "humanVerificationRequired": self.human_verification_required,
                "responseMode": self.response_mode,
                "promptEnhancement": self.prompt_enhancement,
                "cohortSpec": {
                    "cohortId": cohort.cohort_id,
                    "vesselsPerCohort": cohort.vessels_per_cohort,
                    "configurationId": cohort.configuration_id,
                    "vesselCharterPolicy": {
                        "schemaVersion": self.charter_schema_version,
                    },
                },
                "authorityProfile": self._authority_profile(),
            })
        return payloads

    def to_record(self) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "councilId": self.council_id,
            "missionId": self.mission_id,
            "targetRoot": self.target_root,
            "maxConcurrentCohorts": self.max_concurrent_cohorts,
            "requestedContextBudget": self.requested_context_budget,
            "requestedExecutionSeconds": self.requested_execution_seconds,
            "responseMode": self.response_mode,
            "promptEnhancement": self.prompt_enhancement,
            "humanVerificationRequired": self.human_verification_required,
            "fileMutationAllowed": self.file_mutation_allowed,
            "shellAccessAllowed": self.shell_access_allowed,
            "providerNetworkPolicy": self.provider_network_policy,
            "charterSchemaVersion": self.charter_schema_version,
            "cohorts": [c.to_record() for c in self.cohorts],
            "logicalVessels": self.logical_vessels,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CouncilWorkflow":
        return cls(
            council_id=str(value.get("councilId") or ""),
            mission_id=str(value.get("missionId") or ""),
            target_root=str(value.get("targetRoot") or ""),
            cohorts=tuple(CohortWorkflow.from_mapping(x) for x in value.get("cohorts") or ()),
            max_concurrent_cohorts=int(value.get("maxConcurrentCohorts", 1)),
            requested_context_budget=int(value.get("requestedContextBudget", 128_000)),
            requested_execution_seconds=int(value.get("requestedExecutionSeconds", 900)),
            response_mode=str(value.get("responseMode") or "SPOCK"),
            prompt_enhancement=str(value.get("promptEnhancement") or "OFF"),
            human_verification_required=bool(value.get("humanVerificationRequired", True)),
            file_mutation_allowed=bool(value.get("fileMutationAllowed", True)),
            shell_access_allowed=bool(value.get("shellAccessAllowed", True)),
            provider_network_policy=str(value.get("providerNetworkPolicy") or "remote_allowed"),
            charter_schema_version=str(value.get("charterSchemaVersion") or "2.0.0"),
        )


def workflow_digest(workflow: CouncilWorkflow) -> str:
    raw = json.dumps(workflow.to_record(), sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def bind_approval_results(
    workflow: CouncilWorkflow,
    approval_results: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Bind runtime-owned approval identities to exact human-authored executions."""
    payloads = workflow.approval_payloads()
    if len(payloads) != len(approval_results):
        raise CouncilWorkflowError("COUNCIL_APPROVAL_COUNT_MISMATCH")
    executions: list[dict[str, Any]] = []
    for payload, result in zip(payloads, approval_results):
        request_id = str(result.get("requestId") or "")
        if not request_id:
            raise CouncilWorkflowError("COUNCIL_APPROVAL_REQUEST_ID_MISSING")
        expected = payload["cohortSpec"]["cohortId"]
        observed = (result.get("cohortSpec") or {}).get("cohortId")
        if observed and str(observed) != expected:
            raise CouncilWorkflowError("COUNCIL_APPROVAL_COHORT_MISMATCH")
        executions.append({
            **payload,
            "approvalRequestId": request_id,
            "missionId": str(result.get("missionId") or payload["missionId"]),
            "taskId": str(result.get("taskId") or payload["taskId"]),
            "driverRunId": str(result.get("driverRunId") or payload["driverRunId"]),
        })
    return executions


def council_launch_payload(
    workflow: CouncilWorkflow,
    executions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    workflow.validate()
    if len(executions) != len(workflow.cohorts):
        raise CouncilWorkflowError("COUNCIL_EXECUTION_COUNT_MISMATCH")
    return {
        "councilId": workflow.council_id,
        "maxConcurrentCohorts": workflow.max_concurrent_cohorts,
        "executions": [dict(x) for x in executions],
    }


def donor_convergence_workflow(target_root: str) -> CouncilWorkflow:
    """The exact 3-model × 11-vessel workflow used for donor convergence."""
    shared = (
        "Execute the CAPT donor cherry-pick and integration mission. Inspect frozen donor "
        "SHAs/licenses, preserve provenance, integrate only justified mechanisms behind "
        "RuntimeService/EventStore/ToolBroker authority, implement tests, and leave "
        "unsupported claims explicitly UNPROVEN."
    )
    cohorts = (
        CohortWorkflow(
            "qwen38-flash", "openrouter", "qwen/qwen3.8-flash",
            shared + " Phase 1: source archaeology, architecture mapping, first-pass implementation.",
            11,
        ),
        CohortWorkflow(
            "mimo26-flash", "openrouter", "xiaomi/mimo-v2.6-flash",
            shared + " Phase 2: adversarial review, licensing/compatibility, gap closure and repair.",
            11,
        ),
        CohortWorkflow(
            "glm53-flash", "openrouter", "z-ai/glm-5.3-flash",
            shared + " Phase 3: final convergence, hardening, deduplication and verification closure.",
            11,
        ),
    )
    return CouncilWorkflow(
        council_id="council-capt-donor-convergence-r1",
        mission_id="m-capt-donor-convergence-r1",
        target_root=target_root,
        cohorts=cohorts,
        max_concurrent_cohorts=1,
        requested_context_budget=128_000,
        requested_execution_seconds=1800,
    ).validate()
