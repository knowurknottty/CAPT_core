"""Typed MemoryQuery construction (M1-memory, ADR-DT-M1-MEM-001).

When a retrieval trigger fires, CAPT constructs a typed MemoryQuery carrying
full governance context. No anonymous text blobs. The query is validated
against the MemoryQuery contract before being issued to the store.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from ..contracts import require
from .policy import TRIGGER_INTERVAL_TOKENS


def build_memory_query(
    *,
    mission_id: str,
    task_id: str,
    actor: str,
    requesting_subsystem: str,
    trigger_boundary: int,
    context_usage: int,
    requested_memory_classes: List[str],
    purpose: str,
    record_limit: int = 20,
    token_budget: int = 0,
    driver_run_id: Optional[str] = None,
    project_scope: Optional[str] = None,
    relevance_criteria: Optional[str] = None,
    time_range: Optional[Dict[str, Any]] = None,
    trust_threshold: float = 0.0,
    consent_scope: Optional[str] = None,
    sensitivity_allowance: Optional[str] = None,
    provenance_requirement: Optional[str] = None,
    causation_id: Optional[str] = None,
) -> Dict[str, Any]:
    query = {
        "schemaVersion": "1.0.0",
        "missionId": mission_id,
        "taskId": task_id,
        "driverRunId": driver_run_id,
        "actor": actor,
        "requestingSubsystem": requesting_subsystem,
        "triggerBoundary": trigger_boundary,
        "contextUsage": context_usage,
        "requestedMemoryClasses": list(requested_memory_classes),
        "projectScope": project_scope,
        "purpose": purpose,
        "relevanceCriteria": relevance_criteria,
        "timeRange": time_range,
        "trustThreshold": trust_threshold,
        "consentScope": consent_scope,
        "sensitivityAllowance": sensitivity_allowance,
        "recordLimit": record_limit,
        "tokenBudget": token_budget,
        "provenanceRequirement": provenance_requirement,
        "correlationId": "corr-" + uuid.uuid4().hex[:12],
        "causationId": causation_id,
    }
    require("MemoryQuery", query)
    return query
