"""Canonical execution binding for governed model-operator approvals.

The human-visible/model-visible prompt is only one part of execution identity.
This module binds it to the concrete run identity and to the exact text that
will cross the selected driver boundary.  It is pure construction code: no
approval state is created or consumed here.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contracts import digest
from .drivers.hermes import build_prompt as build_hermes_prompt
from .operator_provenance import build_model_operator_prompt_assembly

MODEL_OPERATOR_OPERATIONS = [
    "RepositoryRead",
    "FilesystemRead",
    "ArtifactCreate",
    "AnalysisOnly",
]
MODEL_OPERATOR_TOOLS = ["terminal"]
MODEL_OPERATOR_BUDGETS = {
    "maxSeconds": 600,
    "maxArtifacts": 1,
    "maxObservations": 10,
}


def raw_text_digest(text: str) -> str:
    """Digest exact UTF-8 bytes sent to an external model boundary."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def staging_root_for_ledger(ledger_path: str, driver_run_id: str) -> str:
    return str(Path(ledger_path).parent / "staging" / driver_run_id)


def build_bound_model_operator_approval(
    *,
    human_prompt: str,
    response_mode: str,
    enhancement_engine: str,
    mission_id: str,
    task_id: str,
    driver_run_id: str,
    target_root: str,
    provider: str,
    model: str,
    requested_context_budget: int,
    human_verification_required: bool,
    executable: str,
    staging_root: str,
    context_pack_digest: str = "",
    continuation_context: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return the model-visible assembly plus its execution admission binding."""
    assembly = build_model_operator_prompt_assembly(
        human_prompt=human_prompt,
        response_mode=response_mode,
        enhancement_engine=enhancement_engine,
        context_pack_digest=context_pack_digest or None,
        continuation_context=continuation_context,
    )
    provider_id = str(provider or "")
    model_id = str(model or "")
    executable_selector = str(executable or "")
    driver_kind = "provider" if provider_id else "hermes"

    if driver_kind == "provider":
        dispatch_prompt = assembly["modelVisiblePrompt"]
    else:
        dispatch_prompt = build_hermes_prompt(
            {
                "filesystemPolicy": {
                    "rootPath": target_root,
                    "allowedPaths": [target_root, staging_root],
                    "writesAllowed": False,
                },
                "permittedTools": list(MODEL_OPERATOR_TOOLS),
                "budgets": dict(MODEL_OPERATOR_BUDGETS),
            },
            list(MODEL_OPERATOR_OPERATIONS),
            objective=assembly["modelVisiblePrompt"],
        )

    dispatch_prompt_digest = raw_text_digest(dispatch_prompt)
    binding = {
        "missionId": mission_id,
        "taskId": task_id,
        "driverRunId": driver_run_id,
        "targetRoot": target_root,
        "provider": provider_id,
        "model": model_id,
        "requestedContextBudget": int(requested_context_budget),
        "humanVerificationRequired": bool(human_verification_required),
        "executable": executable_selector,
        "driverKind": driver_kind,
        "basePromptAssemblyDigest": assembly["promptAssemblyDigest"],
        "dispatchPromptDigest": dispatch_prompt_digest,
    }
    approval_digest = digest(
        {
            "basePromptAssemblyDigest": assembly["promptAssemblyDigest"],
            "executionBinding": binding,
        }
    )
    return {
        **assembly,
        "basePromptAssemblyDigest": assembly["promptAssemblyDigest"],
        "promptAssemblyDigest": approval_digest,
        "executionBinding": binding,
        "dispatchPromptDigest": dispatch_prompt_digest,
    }
