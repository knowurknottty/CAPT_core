"""Genuine OpenHarness external ExecutionDriver adapter (Gate A).

This adapter implements the frozen CAPT ``ExecutionDriver`` Protocol by invoking
the REAL ``oh`` binary (openharness-ai==0.1.9) as a separate sandboxed
subprocess. The harness performs the actual repository analysis using a local
Ollama model. CAPT never grants the harness any authoritative capability.

Trust boundary:
- The adapter owns ONLY process invocation, environment allowlisting, prompt
  translation, output capture, lifecycle inspection, cancellation forwarding,
  untrusted-record normalization, and external-error translation.
- The adapter does NOT own policy evaluation, capability grants, lease issuance,
  aggregate mutation, authoritative event emission, evidence promotion, claim
  verification, ClaimGuard decisions, or task/mission completion.

The adapter imports NO OpenHarness Python code; it shells out to the ``oh``
binary. Therefore uninstalling OpenHarness does not break base CAPT imports, and
base CAPT runtime remains usable when the external dependency is absent.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ...drivers import require  # frozen contract validation (no external import)
from .errors import OpenHarnessExecutionError, OpenHarnessLifecycleError
from .lifecycle import DESCRIPTOR, OpenHarnessRunLifecycle
from .sandbox import build_allowlisted_env, validate_paths
from .translation import (
    build_prompt,
    build_receipt,
    normalize_observation,
    write_artifact_and_candidate,
)


def _resolve_oh_binary(explicit: Optional[str] = None) -> str:
    """Locate the genuine ``oh`` binary.

    Resolution order:
    1. explicit path (tests / config),
    2. CAPT_OH_BINARY env,
    3. repo-local isolated venv (Gate A layout),
    4. PATH.
    """
    if explicit:
        return explicit
    import os
    env_path = os.environ.get("CAPT_OH_BINARY")
    if env_path:
        return env_path
    repo_venv = Path(__file__).resolve().parents[4] / ".venv-external" / "bin" / "oh"
    if repo_venv.exists():
        return str(repo_venv)
    return "oh"


class OpenHarnessExternalDriver:
    """External driver that delegates analysis to genuine OpenHarness (oh)."""

    KIND = "openharness-external"

    def __init__(
        self,
        staging_root: str,
        *,
        oh_binary: Optional[str] = None,
        config_dir: Optional[str] = None,
        model: str = "ornith-1.0-9b",
        max_turns: int = 6,
    ) -> None:
        self._staging_root = str(staging_root)
        self._oh_binary = _resolve_oh_binary(oh_binary)
        self._model = model
        self._max_turns = max_turns
        if config_dir is None:
            config_dir = (Path(self._staging_root) / ".." / ".oh-config").resolve().as_posix()
        self._config_dir = config_dir
        self._ensure_config_dir()
        self._runs: Dict[str, OpenHarnessRunLifecycle] = {}

    def _ensure_config_dir(self) -> None:
        """Create the sandboxed OpenHarness config dir with a localhost-Ollama
        settings.json if it does not already exist. This keeps the adapter
        self-contained and prevents falling back to a hosted provider."""
        cfg = Path(self._config_dir)
        cfg.mkdir(parents=True, exist_ok=True)
        settings = cfg / "settings.json"
        if not settings.exists():
            settings.write_text(
                json.dumps(
                    {
                        "api_format": "openai",
                        "base_url": "http://127.0.0.1:11434/v1",
                        "model": self._model,
                        "api_key": "ollama-local",
                    },
                    indent=2,
                )
            )

    # -- ExecutionDriver surface ------------------------------------------

    def describe(self) -> Dict[str, Any]:
        return dict(DESCRIPTOR)

    async def submit(self, work_order: Dict[str, Any]) -> Dict[str, Any]:
        require("ExecutionDriverWorkOrder", work_order)
        run_id = work_order["driverRunId"]
        allowed = work_order.get("contextSlice", {}).get("filesystemPolicy", {}).get("allowedPaths", [])
        target = allowed[0] if allowed else None
        if target is None:
            raise ValueError("no allowed path in context slice")
        paths = validate_paths(target, self._staging_root)

        lifecycle = OpenHarnessRunLifecycle(run_id)
        self._runs[run_id] = lifecycle

        prompt = build_prompt(work_order, paths["target_repo"])
        env = build_allowlisted_env(self._config_dir, self._model)
        observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Run the genuine OpenHarness process (separate-process isolation).
        try:
            proc = subprocess.Popen(
                [
                    self._oh_binary,
                    "-p", prompt,
                    "--output-format", "text",
                    "--max-turns", str(self._max_turns),
                    "--permission-mode", "default",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=paths["target_repo"],
                env=env,
                text=True,
            )
        except FileNotFoundError as exc:
            raise OpenHarnessExecutionError("oh binary not found: %s" % self._oh_binary) from exc

        lifecycle.start(proc)
        stdout, stderr = proc.communicate(timeout=600)
        lifecycle.mark_completed(stdout or "", stderr or "", proc.returncode)

        if proc.returncode != 0:
            raise OpenHarnessExecutionError(
                "oh process failed", returncode=proc.returncode, stderr=(stderr or "")[:2000]
            )

        summary = (stdout or "").strip()
        if not summary:
            raise OpenHarnessExecutionError("oh produced no analysis output")

        observation = normalize_observation(run_id, work_order.get("missionId", ""),
                                            work_order.get("taskId", ""), summary, observed_at)
        artifact_candidate = write_artifact_and_candidate(
            run_id, self._staging_root, summary, paths["target_repo"], observed_at
        )
        receipt = build_receipt(run_id, lifecycle.external_run_id, summary, observed_at)

        return {
            "driverRunId": run_id,
            "externalRunId": lifecycle.external_run_id,
            "state": lifecycle.state,
            "observations": [observation],
            "artifactCandidate": artifact_candidate,
            "receipts": [receipt],
        }

    async def inspect(self, run_id: str) -> Dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError("unknown run %s" % run_id)
        return run.inspect()

    async def cancel(self, run_id: str, reason: str) -> None:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError("unknown run %s" % run_id)
        run.cancel()

    async def resume(
        self, run_id: str, resume_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # Honest: oh -p is one-shot and non-resumable. Do not fake a resume.
        raise OpenHarnessLifecycleError(
            "resume is not supported for the one-shot OpenHarness external driver"
        )

    async def reconcile(self, run_id: str) -> Dict[str, Any]:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError("unknown run %s" % run_id)
        return run.reconcile()
