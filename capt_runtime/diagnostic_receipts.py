"""Durable bounded CAPT provider diagnostics and council receipt projections.

Only allowlisted fields survive. Raw provider messages, prompts, credentials,
tool outputs, and exception strings never enter the diagnostic store.
These protected SQLite projections are NOT EventStore chain events.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .errors import IdempotencyConflict, IntegrityViolation

_SAFE_FAILURES = frozenset({
    "PROVIDER_HTTP_ERROR", "PROVIDER_NETWORK_ERROR", "PROVIDER_TIMEOUT",
    "PROVIDER_RESPONSE_INVALID", "PROVIDER_BUDGET_EXCEEDED",
    "PROVIDER_BOUNDARY_RECORDING_FAILURE", "PROVIDER_TOOL_FAILURE",
    "PROVIDER_NO_CONTENT", "PROVIDER_UNCLASSIFIED_FAILURE",
    "INTERNAL_DRIVER_ERROR",
})
_SAFE_PHASES = frozenset({
    "pre_dispatch", "request_preparation", "response_headers",
    "response_body", "tool_execution", "result_persistence", "unknown",
})
_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")


def _identity(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("INVALID_" + label)
    return value


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_provider_failure(
    exc: BaseException, *,
    driver_run_id: str, model: str, provider: str,
    dispatch_boundary: str, request_attempts: Optional[int] = None,
) -> Dict[str, Any]:
    """Reduce any exception to a non-secret, bounded diagnostic.

    Untrusted exception strings are intentionally discarded, not truncated.
    """
    run = _identity(driver_run_id, "DRIVER_RUN")
    allowed_code = getattr(exc, "diagnostic_code", None)
    code = allowed_code if allowed_code in _SAFE_FAILURES else "PROVIDER_UNCLASSIFIED_FAILURE"
    allowed_phase = getattr(exc, "diagnostic_phase", None)
    phase = allowed_phase if allowed_phase in _SAFE_PHASES else "unknown"
    status = getattr(exc, "http_status", None)
    status = status if type(status) is int and 100 <= status <= 599 else None
    return {
        "schemaVersion": "capt.provider-failure.v1",
        "driverRunId": run,
        "failureCode": code,
        "phase": phase,
        "httpStatus": status,
        "exceptionClass": (
            type(exc).__name__
            if type(exc).__name__ in {"ProviderDriverFailure", "DispatchBoundaryError", "BudgetCeilingExceeded"}
            else "Other"
        ),
        "provider": provider if provider in {"openrouter", "ollama", "openai", "local"} else "other",
        "modelDigest": _digest(model),
        "dispatchBoundary": dispatch_boundary if dispatch_boundary in {
            "not_dispatched", "prepared", "budget_rejected", "request_started",
            "response_started", "response_completed", "result_persisted",
        } else "unknown",
        "providerHttpRequestAttempts": (
            request_attempts if type(request_attempts) is int and 0 <= request_attempts <= 100000 else None
        ),
        "occurredAt": _now(),
        "externalOutcomeKnown": False,
        "retryAutomatically": False,
        "rawExceptionPersisted": False,
    }


def safe_model_authority_reason(exc: BaseException) -> str:
    """Retain exact CAPT policy denial codes, never free-form exception details."""
    candidate = str(exc)
    exact_codes = frozenset({
        "REMOTE_PROVIDER_NETWORK_NOT_AUTHORIZED",
        "MODEL_TARGET_ROOT_MISSING", "MODEL_TARGET_ROOT_NOT_FOUND",
        "MODEL_TARGET_ROOT_UNAVAILABLE", "MODEL_TARGET_ROOT_NOT_DIRECTORY",
    })
    if candidate in exact_codes:
        return candidate
    match = re.fullmatch(
        r"MODEL_TOOL_NOT_AUTHORIZED:(file[.](?:read|search|write)|terminal[.]exec)",
        candidate,
    )
    return candidate if match else "MODEL_AUTHORITY_FAILURE_DETAILS_REDACTED"


def safe_cohort_receipt(
    cohort_id: str, item: Dict[str, Any], receipt: Dict[str, Any],
    driver_state: Optional[Dict[str, Any]] = None,
    failure_diagnostic: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Retain meaningful terminal metadata, never raw model content."""
    def _text(v: Any, limit: int = 128) -> Optional[str]:
        return v[:limit] if isinstance(v, str) and _IDENTIFIER.fullmatch(v) else None

    error = receipt.get("error") if isinstance(receipt.get("error"), dict) else {}
    result = receipt.get("result") if isinstance(receipt.get("result"), dict) else {}
    observed = driver_state if isinstance(driver_state, dict) else {}
    diagnostic = failure_diagnostic if isinstance(failure_diagnostic, dict) else {}
    status = receipt.get("status")
    artifact = result.get("artifactCandidate") if isinstance(result.get("artifactCandidate"), dict) else {}
    result_digest = result.get("artifactDigest") or artifact.get("artifactDigest")
    return {
        "cohortId": _identity(cohort_id, "COHORT"),
        "driverRunId": _text(item.get("driverRunId")),
        "missionId": _text(item.get("missionId")),
        "approvalRequestId": _text(item.get("approvalRequestId")),
        "status": status if isinstance(status, str) and status in {"accepted", "rejected", "idempotent"} else "unknown",
        "driverRunState": _text(observed.get("state"), 32),
        "dispatchBoundary": _text(observed.get("dispatchBoundary"), 48),
        "providerHttpRequestAttempts": (
            observed.get("providerHttpRequestAttempts")
            if type(observed.get("providerHttpRequestAttempts")) is int
            and 0 <= observed["providerHttpRequestAttempts"] <= 100000
            else None
        ),
        "reconciliationStatus": _text(observed.get("reconciliationStatus"), 64),
        "sanitizedProviderFailureCode": _text(diagnostic.get("failureCode"), 64),
        "classification": _text(receipt.get("classification"), 60),
        "errorCategory": _text(error.get("category"), 60),
        "errorCode": _text(error.get("code"), 60),
        "artifactDigest": _text(result_digest, 96),
        "receiptDigest": _digest(receipt),
        "diagnosticLookup": _text(item.get("driverRunId")),
        "finishedAt": _now(),
        "rawProviderResponsePersisted": False,
    }


def persist_provider_diagnostic(store: Any, record: Dict[str, Any]) -> None:
    run_id = _identity(record.get("driverRunId"), "DRIVER_RUN")
    store.store_provider_failure_diagnostic(run_id, record)


def council_submission_digest(cmd: Dict[str, Any]) -> str:
    return _digest({
        "operation": "run_approved_council_inspection",
        "operatorId": cmd["operatorId"],
        "sessionId": cmd["sessionId"],
        "payload": cmd["payload"],
    })
