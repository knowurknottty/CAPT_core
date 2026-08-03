"""Protocol translation between CAPT work orders and genuine OpenHarness.

CAPT -> OpenHarness: build a constrained, read-only analysis prompt from the
narrow ``ExecutionDriverWorkOrder`` + ``ContextSlice``. The harness is told to
inspect the target repository, identify its runtime architecture and ONE
evidence-backed code-quality / security observation, and return plain text. It
is explicitly forbidden from writing files.

OpenHarness -> CAPT: normalize the captured stdout into untrusted CAPT driver
records (``DriverObservation`` + ``DriverArtifactCandidate`` + optional
``DriverReceiptCandidate``). CAPT validates and promotes these; the adapter
asserts no authority.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict

SCHEMA_VERSION = "1.0.0"


def build_prompt(work_order: Dict[str, Any], target_repo: str) -> str:
    """Translate a CAPT work order into a constrained OpenHarness prompt.

    The prompt is the ONLY instruction the external harness receives about the
    task. It is bounded, read-only, and forbids file writes.
    """
    mission_id = work_order.get("missionId", "")
    task_id = work_order.get("taskId", "")
    run_id = work_order.get("driverRunId", "")
    ops = ", ".join(work_order.get("operations", []) or ["repository.read", "analysis.execute"])
    prompt = (
        "You are operating as an UNTRUSTED read-only analysis harness inside the "
        "CAPT runtime. You may ONLY read files in the current working directory "
        "(the target repository). You MUST NOT write, edit, delete, or move any "
        "file. You MUST NOT run shell commands that mutate state. You MUST NOT "
        "access any network except the local model endpoint.\n\n"
        "TASK (CAPT mission=%s task=%s driverRun=%s):\n"
        "Inspect the repository at the current working directory in read-only "
        "mode. Then:\n"
        "1. Describe its runtime architecture in at most 4 bullet points.\n"
        "2. Identify exactly ONE evidence-backed code-quality or security "
        "observation, citing the file path and line number.\n"
        "3. Return your answer as plain text. Do not create any file.\n\n"
        "Permitted operations for this work order: %s.\n"
        "Return the analysis now."
        % (mission_id, task_id, run_id, ops)
    )
    return prompt


def normalize_observation(
    run_id: str,
    mission_id: str,
    task_id: str,
    summary: str,
    observed_at: str,
) -> Dict[str, Any]:
    """Build an untrusted ``DriverObservation`` from captured harness output."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "observationId": "obs-" + run_id,
        "observedAt": observed_at,
        "observedBy": "openharness-external",
        "trust": "untrusted",
        "workOrderId": run_id,
        "summary": summary,
    }


def write_artifact_and_candidate(
    run_id: str,
    staging_root: str,
    summary: str,
    target_repo: str,
    observed_at: str,
) -> Dict[str, Any]:
    """Write the analysis artifact into the CAPT-owned staging directory.

    CAPT (not the harness) owns the file write, preserving authority separation.
    Returns a ``DriverArtifactCandidate``.
    """
    stg = Path(staging_root)
    stg.mkdir(parents=True, exist_ok=True)
    artifact_path = stg / ("analysis-%s.md" % run_id)
    body = (
        "# CAPT Gate A External Analysis Artifact\n\n"
        + summary
        + "\n\nTarget repository: %s\nDriverRunId: %s\nObservedAt: %s\n"
        % (target_repo, run_id, observed_at)
    )
    artifact_path.write_text(body)
    digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "candidateId": "ac-" + run_id,
        "driverRunId": run_id,
        "artifactPath": str(artifact_path),
        "artifactDigest": digest,
        "producedAt": observed_at,
    }


def build_receipt(
    run_id: str,
    external_run_id: str,
    summary: str,
    observed_at: str,
) -> Dict[str, Any]:
    """Build an untrusted ``DriverReceiptCandidate`` for the external execution."""
    content_digest = "sha256:" + hashlib.sha256(summary.encode("utf-8")).hexdigest()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "receiptId": "rc-" + run_id,
        "driverRunId": run_id,
        "step": "external_execution",
        "contentDigest": content_digest,
        "claimedAt": observed_at,
    }


def external_run_id_for(run_id: str) -> str:
    """Synthesize an untrusted external run identifier for the one-shot process."""
    return "oh-ext-" + run_id
