"""Bounded, untrusted provider ExecutionDriver for CAPT governed work orders."""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from ..approval_dispatch import require_expected_prompt_digest
from ..provider_endpoint import endpoint_class
from ..resource_governor import BudgetCeilingExceeded, TokenCostGovernor

DRIVER_ID = "provider"
DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "driverId": DRIVER_ID,
    "driverVersion": "0.1.1",
    "supportedOperations": ["submit", "inspect", "cancel", "resume", "reconcile"],
    "writeCapable": False,
}


class ProviderDriverFailure(RuntimeError):
    pass


class ProviderDriver:
    KIND = DRIVER_ID

    def __init__(
        self,
        staging_root: str,
        *,
        provider_id: str,
        model: str,
        base_url: str,
        api_key: str = "",
        task_resolver=None,
        dispatch_prompt: str = "",
        governor: Optional[TokenCostGovernor] = None,
    ):
        self.root = Path(staging_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.provider_id = provider_id
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.task_resolver = task_resolver
        self.dispatch_prompt = dispatch_prompt
        self.governor = governor or TokenCostGovernor()
        self.runs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def describe(self):
        return dict(DESCRIPTOR)

    async def submit(self, work_order):
        rid = work_order["driverRunId"]
        with self._lock:
            if rid in self.runs:
                raise ProviderDriverFailure("duplicate driverRunId")
            self.runs[rid] = {
                "state": "running",
                "cancelRequested": False,
                "dispatchBoundary": "prepared",
            }
        return await asyncio.to_thread(self._execute, rid, work_order)

    async def inspect(self, rid):
        with self._lock:
            state = dict(self.runs.get(rid, {}))
        if not state:
            return {"driverRunId": rid, "state": "unknown"}
        return {"driverRunId": rid, **state}

    async def cancel(self, rid, reason):
        """Request cancellation without pretending urllib transport was aborted."""
        with self._lock:
            run = self.runs.get(rid)
            if run is None:
                raise ProviderDriverFailure("unknown driverRunId")
            run["cancelRequested"] = True
            run["cancelReason"] = reason
            if run.get("state") not in ("completed", "failed"):
                run["state"] = "cancel_requested"
        return {
            "driverRunId": rid,
            "state": "cancel_requested",
            "transportCancellationSupported": False,
        }

    async def resume(self, rid, resume_input=None):
        raise ProviderDriverFailure("provider runs are not resumable")

    async def reconcile(self, rid):
        with self._lock:
            run = dict(self.runs.get(rid, {}))
        if not run:
            return {
                "driverRunId": rid,
                "result": "external_state_unknown",
                "anomalies": ["unknown_driver_run"],
            }
        boundary = run.get("dispatchBoundary", "unknown")
        if boundary == "prepared":
            result = "pre_dispatch"
        elif boundary == "response_completed":
            result = "response_completed"
        else:
            result = "external_state_unknown"
        return {
            "driverRunId": rid,
            "result": result,
            "dispatchBoundary": boundary,
            "cancelRequested": bool(run.get("cancelRequested")),
            "anomalies": [],
        }

    def _execute(self, rid, wo):
        prompt = self.dispatch_prompt or (
            self.task_resolver.resolve_for_execution(
                mission_id=wo["missionId"], task_id=wo["taskId"]
            ).objective
            if self.task_resolver
            else "Provide a bounded evidence-backed observation."
        )
        estimated_prompt_tokens = max(1, len(prompt) // 4)
        try:
            self.governor.check_pre_dispatch(
                estimated_prompt_tokens=estimated_prompt_tokens
            )
        except BudgetCeilingExceeded as exc:
            with self._lock:
                self.runs[rid]["state"] = "failed"
                self.runs[rid]["dispatchBoundary"] = "budget_rejected"
            raise ProviderDriverFailure(f"budget ceiling exceeded: {exc}") from exc

        prompt_digest = "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()
        require_expected_prompt_digest(rid, prompt_digest)
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        if self.provider_id == "ollama":
            url = self.base_url.replace("/v1", "") + "/api/generate"
            body = {
                "model": self.model, "prompt": prompt, "stream": False,
                "options": {"num_predict": self.governor.max_output_tokens_per_request},
            }
        else:
            url = self.base_url + "/chat/completions"
            body = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": self.governor.max_output_tokens_per_request,
            }
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode(), headers=headers, method="POST"
            )
            with self._lock:
                self.runs[rid]["dispatchBoundary"] = "request_started"
            with urllib.request.urlopen(req, timeout=120) as response:
                with self._lock:
                    self.runs[rid]["dispatchBoundary"] = "response_started"
                data = json.loads(response.read().decode())
                with self._lock:
                    self.runs[rid]["dispatchBoundary"] = "response_completed"
        except urllib.error.HTTPError as exc:
            with self._lock:
                self.runs[rid]["state"] = "failed"
            raise ProviderDriverFailure("provider HTTP %s" % exc.code) from exc
        except Exception as exc:
            with self._lock:
                self.runs[rid]["state"] = "failed"
            raise ProviderDriverFailure(
                "provider unavailable: %s" % type(exc).__name__
            ) from exc
        text = (
            data.get("response")
            if self.provider_id == "ollama"
            else ((data.get("choices") or [{}])[0].get("message", {}).get("content"))
        ) or ""
        if not text:
            with self._lock:
                self.runs[rid]["state"] = "failed"
            raise ProviderDriverFailure("provider returned no content")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        if self.provider_id == "ollama":
            prompt_tokens = data.get("prompt_eval_count", prompt_tokens)
            completion_tokens = data.get("eval_count", completion_tokens)
        prompt_tokens = int(prompt_tokens) if isinstance(prompt_tokens, (int, float)) else estimated_prompt_tokens
        completion_tokens = int(completion_tokens) if isinstance(completion_tokens, (int, float)) else max(1, len(text) // 4)
        raw_cost = usage.get("cost", usage.get("cost_usd", 0.0))
        cost_usd = float(raw_cost) if isinstance(raw_cost, (int, float)) else 0.0
        resource_receipt = self.governor.record_usage(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost_usd
        )
        response_digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        ep_class = endpoint_class(self.base_url)
        artifact = (
            "# CAPT Provider Observation\n\n"
            "Provider: %s\nModel: %s\nEndpointClass: %s\nPromptDigest: %s\n"
            "ResponseDigest: %s\n\n%s\n"
            % (
                self.provider_id,
                self.model,
                ep_class,
                prompt_digest,
                response_digest,
                text,
            )
        )
        path = self.root / ("provider-analysis-%s.md" % rid)
        path.write_text(artifact)
        artifact_digest = "sha256:" + hashlib.sha256(artifact.encode()).hexdigest()
        with self._lock:
            run = self.runs[rid]
            run["state"] = "completed"
            cancel_requested = bool(run.get("cancelRequested"))
            dispatch_boundary = run.get("dispatchBoundary", "response_completed")
        return {
            "driverRunId": rid,
            "externalRunId": "%s-%s" % (self.provider_id, rid),
            "state": "completed",
            "cancelRequested": cancel_requested,
            "transportCancellationSupported": False,
            "dispatchBoundary": dispatch_boundary,
            "observations": [
                {
                    "schemaVersion": "1.0.0",
                    "observationId": "obs-" + rid,
                    "observedBy": DRIVER_ID,
                    "trust": "untrusted",
                    "workOrderId": rid,
                    "summary": text[:8192],
                    "observedAt": wo.get("submittedAt", ""),
                }
            ],
            "artifactCandidate": {
                "schemaVersion": "1.0.0",
                "candidateId": "ac-" + rid,
                "driverRunId": rid,
                "artifactPath": str(path),
                "artifactDigest": artifact_digest,
                "producedAt": wo.get("submittedAt", ""),
            },
            "diagnostics": {
                "provider": self.provider_id,
                "model": self.model,
                "endpointClass": ep_class,
                "promptDigest": prompt_digest,
                "responseDigest": response_digest,
                "dispatchBoundary": dispatch_boundary,
                "cancelRequested": cancel_requested,
                "resourceUsage": resource_receipt,
            },
        }
