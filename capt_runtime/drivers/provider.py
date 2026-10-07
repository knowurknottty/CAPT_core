"""Bounded, untrusted provider ExecutionDriver for CAPT governed work orders."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from ..approval_dispatch import require_expected_prompt_digest
from ..provider_endpoint import endpoint_class
from ..resource_governor import BudgetCeilingExceeded, TokenCostGovernor
from ..reasoning import normalize_reasoning_effort, openai_reasoning_fields

DRIVER_ID = "provider"
DESCRIPTOR = {
    "schemaVersion": "1.0.0",
    "driverId": DRIVER_ID,
    "driverVersion": "0.1.2",
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
        output_modality: str = "text",
        output_format: str = "",
        governor: Optional[TokenCostGovernor] = None,
        tool_bridge=None,
        reasoning_effort: str = "",
        cohort_spec: Optional[Dict[str, Any]] = None,
    ):
        self.root = Path(staging_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.provider_id = provider_id
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.task_resolver = task_resolver
        self.dispatch_prompt = dispatch_prompt
        self.output_modality = str(output_modality or "text").strip().lower()
        self.output_format = str(output_format or "").strip().lower()
        if self.output_modality not in ("text", "image"):
            raise ValueError("PROVIDER_OUTPUT_MODALITY_INVALID")
        if self.output_modality == "image":
            self.output_format = self.output_format or "png"
            if self.output_format not in ("png", "jpeg", "webp"):
                raise ValueError("PROVIDER_IMAGE_OUTPUT_FORMAT_INVALID")
        elif self.output_format:
            raise ValueError("PROVIDER_TEXT_OUTPUT_FORMAT_FORBIDDEN")
        self.reasoning_effort = normalize_reasoning_effort(reasoning_effort)
        self._reasoning_fields = openai_reasoning_fields(
            self.provider_id, self.base_url, self.reasoning_effort
        )
        self.governor = governor or TokenCostGovernor()
        self.tool_bridge = tool_bridge
        self.cohort_spec = dict(cohort_spec) if isinstance(cohort_spec, dict) else None
        self.runs: Dict[str, Dict[str, Any]] = {}
        self._request_deadlines: Dict[str, float] = {}
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
                "reasoningEffort": self.reasoning_effort or None,
            }
        try:
            return await asyncio.to_thread(self._execute, rid, work_order)
        finally:
            self._request_deadlines.pop(rid, None)

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

    @staticmethod
    def _work_order_timeout_seconds(work_order: dict[str, Any]) -> float:
        """Bind provider I/O to the governed DriverRun wall-clock budget."""
        context = work_order.get("contextSlice")
        budgets = context.get("budgets") if isinstance(context, dict) else None
        value = budgets.get("maxSeconds") if isinstance(budgets, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            return 120.0
        return min(float(value), 3600.0)

    def _remaining_request_timeout(self, rid: str) -> float:
        deadline = self._request_deadlines.get(rid)
        if deadline is None:
            return 120.0
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("provider DriverRun wall-clock budget exhausted")
        return max(0.001, remaining)

    def _read_response_with_deadline(self, rid: str, response) -> bytes:
        remaining = self._remaining_request_timeout(rid)
        done = threading.Event()
        payload = []
        errors = []
        def reader():
            try:
                payload.append(response.read())
            except Exception as exc:
                errors.append(exc)
            finally:
                done.set()
        worker = threading.Thread(target=reader, daemon=True)
        worker.start()
        if not done.wait(timeout=remaining):
            def closer():
                try:
                    response.close()
                except Exception:
                    pass
            threading.Thread(target=closer, daemon=True).start()
            raise TimeoutError("provider DriverRun wall-clock budget exhausted")
        if errors:
            raise errors[0]
        self._remaining_request_timeout(rid)
        return payload[0] if payload else b""

    @staticmethod
    def _work_order_context_budget_tokens(work_order: dict[str, Any]) -> int | None:
        context = work_order.get("contextSlice")
        budgets = context.get("budgets") if isinstance(context, dict) else None
        value = budgets.get("maxTokens") if isinstance(budgets, dict) else None
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None
        return value

    def _strict_charter_policy(self) -> dict[str, Any] | None:
        spec = self.cohort_spec
        if not isinstance(spec, dict):
            return None
        policy = spec.get("vesselCharterPolicy")
        if not isinstance(policy, dict) or not bool(policy.get("strictLedger")):
            return None
        return policy

    def _charter_minimum_output_tokens(self) -> int:
        """Reserve enough final output for the frozen strict-ledger geometry."""
        policy = self._strict_charter_policy()
        spec = self.cohort_spec
        if policy is None or not isinstance(spec, dict):
            return 0
        vessels = spec.get("vesselsPerCohort")
        multiplier = policy.get("candidateMultiplier", 3)
        candidate_max_words = policy.get("candidateMaxWords", 48)
        if (
            isinstance(vessels, bool) or not isinstance(vessels, int) or vessels <= 0
            or isinstance(multiplier, bool) or not isinstance(multiplier, int) or multiplier <= 0
            or isinstance(candidate_max_words, bool)
            or not isinstance(candidate_max_words, int)
            or candidate_max_words <= 0
        ):
            return 0

        candidates = vessels * multiplier
        # Compact ledger budgeting. Candidate rows are capped by contract; selected
        # vessel rows target <=140 words. Convert words to token headroom at 4/3,
        # then add fixed synthesis and structural allowance.
        candidate_tokens = candidates * ((candidate_max_words * 4 + 2) // 3)
        vessel_tokens = vessels * 192
        synthesis_tokens = 2048
        structural_tokens = 1024
        return candidate_tokens + vessel_tokens + synthesis_tokens + structural_tokens

    def _final_answer_reserve_tokens(self, context_budget: int) -> int:
        fraction_reserve = (
            context_budget // 2
            if self._strict_charter_policy() is not None
            else context_budget // 3
        )
        reserve = max(1024, fraction_reserve, self._charter_minimum_output_tokens())
        reserve = min(reserve, int(self.governor.max_output_tokens_per_request))
        return min(reserve, max(1, context_budget - 1))

    def _post_json(
        self,
        rid: str,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        *,
        reasoning_policy: str = "configured",
    ) -> dict[str, Any]:
        try:
            if reasoning_policy not in {"configured", "answer_only"}:
                raise ProviderDriverFailure("unsupported provider reasoning policy")
            outbound = dict(body)
            if self.provider_id == "openrouter" and url.endswith("/chat/completions"):
                if reasoning_policy == "answer_only":
                    outbound["reasoning"] = {"effort": "none"}
                elif self.reasoning_effort:
                    outbound["reasoning"] = {"effort": self.reasoning_effort}
            req = urllib.request.Request(
                url, data=json.dumps(outbound).encode(), headers=headers, method="POST"
            )
            with self._lock:
                self.runs[rid]["dispatchBoundary"] = "request_started"
            response = urllib.request.urlopen(
                req, timeout=self._remaining_request_timeout(rid)
            )
            with self._lock:
                self.runs[rid]["dispatchBoundary"] = "response_started"
            completed_read = False
            try:
                raw_response = self._read_response_with_deadline(rid, response)
                completed_read = True
                data = json.loads(raw_response.decode())
                self._remaining_request_timeout(rid)
                with self._lock:
                    self.runs[rid]["dispatchBoundary"] = "response_completed"
            finally:
                if completed_read:
                    close_response = getattr(response, "close", None)
                    if callable(close_response):
                        close_response()
            if not isinstance(data, dict):
                raise ProviderDriverFailure("provider returned non-object JSON")
            return data
        except urllib.error.HTTPError as exc:
            with self._lock:
                self.runs[rid]["state"] = "failed"
            try:
                raw_detail = exc.read(4096).decode("utf-8", errors="replace")
            except Exception:
                raw_detail = ""
            detail = " ".join(raw_detail.split())[:1000]
            if self.api_key and detail:
                detail = detail.replace(self.api_key, "[REDACTED]")
            message = "provider HTTP %s" % exc.code
            if detail:
                message += ": " + detail
            raise ProviderDriverFailure(message) from exc
        except TimeoutError as exc:
            with self._lock:
                self.runs[rid]["state"] = "failed"
                self.runs[rid]["dispatchBoundary"] = "request_timeout"
            raise ProviderDriverFailure(
                "provider DriverRun wall-clock budget exhausted"
            ) from exc
        except ProviderDriverFailure:
            with self._lock:
                self.runs[rid]["state"] = "failed"
            raise
        except Exception as exc:
            with self._lock:
                self.runs[rid]["state"] = "failed"
            raise ProviderDriverFailure(
                "provider unavailable: %s" % type(exc).__name__
            ) from exc

    @staticmethod
    def _usage_from(data: dict[str, Any]) -> tuple[int | None, int | None, float]:
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        raw_cost = usage.get("cost", usage.get("cost_usd", 0.0))
        return (
            int(prompt_tokens) if isinstance(prompt_tokens, (int, float)) else None,
            int(completion_tokens) if isinstance(completion_tokens, (int, float)) else None,
            float(raw_cost) if isinstance(raw_cost, (int, float)) else 0.0,
        )

    def _openai_with_tools(
        self,
        rid: str,
        prompt: str,
        headers: dict[str, str],
        context_budget_tokens: int | None = None,
    ) -> tuple[str, int, int, float, int]:
        """Run a bounded OpenAI-compatible function-calling loop through ToolBroker."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        tools = self.tool_bridge.openai_tools()
        tool_call_count = 0
        prompt_tokens_total = 0
        completion_tokens_total = 0
        cost_total = 0.0
        max_tool_rounds = int(self.tool_bridge.max_calls)
        if max_tool_rounds <= 0:
            raise ProviderDriverFailure("provider tool capability budget is invalid")
        url = self.base_url + "/chat/completions"

        for round_index in range(max_tool_rounds + 1):
            body = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "max_tokens": self.governor.max_output_tokens_per_request,
                "tools": tools,
                **self._reasoning_fields,
            }
            data = self._post_json(rid, url, body, headers)
            p_tokens, c_tokens, cost = self._usage_from(data)
            prompt_tokens_total += p_tokens or 0
            completion_tokens_total += c_tokens or 0
            cost_total += cost

            choices = data.get("choices") or []
            message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
            if not isinstance(message, dict):
                raise ProviderDriverFailure("provider returned malformed assistant message")
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                text = self._final_facing_text(message)
                if not text:
                    raise ProviderDriverFailure("provider returned no content")
                return (
                    text,
                    prompt_tokens_total,
                    completion_tokens_total,
                    cost_total,
                    tool_call_count,
                )
            if not isinstance(tool_calls, list):
                raise ProviderDriverFailure("provider returned malformed tool_calls")

            if context_budget_tokens is not None and p_tokens is not None:
                reserve = self._final_answer_reserve_tokens(context_budget_tokens)
                if p_tokens >= context_budget_tokens - reserve:
                    with self._lock:
                        self.runs[rid]["toolClosureReason"] = "context_headroom"
                        self.runs[rid]["contextBudgetTokens"] = context_budget_tokens
                        self.runs[rid]["finalAnswerReserveTokens"] = reserve
                    return self._openai_finalize_after_tool_budget(
                        rid, url, headers, messages, prompt_tokens_total,
                        completion_tokens_total, cost_total, tool_call_count,
                        reason="context headroom reserve reached",
                        context_budget_tokens=context_budget_tokens,
                    )

            remaining_calls = max_tool_rounds - tool_call_count
            if round_index >= max_tool_rounds or len(tool_calls) > remaining_calls:
                return self._openai_finalize_after_tool_budget(
                    rid, url, headers, messages, prompt_tokens_total,
                    completion_tokens_total, cost_total, tool_call_count,
                    reason="tool authority budget is exhausted",
                    context_budget_tokens=context_budget_tokens,
                )

            messages.append({
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": tool_calls,
            })
            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict) or call.get("type") != "function":
                    raise ProviderDriverFailure("provider returned unsupported tool call")
                function = call.get("function")
                if not isinstance(function, dict):
                    raise ProviderDriverFailure("provider returned malformed function call")
                call_id = call.get("id")
                name = function.get("name")
                if not isinstance(call_id, str) or not call_id:
                    raise ProviderDriverFailure("provider tool call missing id")
                if not isinstance(name, str) or not name:
                    raise ProviderDriverFailure("provider tool call missing function name")
                tool_result = self.tool_bridge.execute_call(
                    name,
                    function.get("arguments", "{}"),
                    call_id=call_id,
                )
                tool_call_count += 1
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": json.dumps(tool_result, sort_keys=True, separators=(",", ":")),
                })
            if tool_call_count >= max_tool_rounds:
                return self._openai_finalize_after_tool_budget(
                    rid, url, headers, messages, prompt_tokens_total,
                    completion_tokens_total, cost_total, tool_call_count,
                    reason="tool authority budget is exhausted",
                    context_budget_tokens=context_budget_tokens,
                )
        raise ProviderDriverFailure("provider tool-call loop did not terminate")

    @staticmethod
    def _final_facing_text(message: dict[str, Any]) -> str:
        """Extract only provider fields intended as visible assistant output."""
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            chunks: list[str] = []
            for part in content:
                if isinstance(part, str) and part.strip():
                    chunks.append(part.strip())
                    continue
                if not isinstance(part, dict):
                    continue
                value = part.get("text")
                if isinstance(value, str) and value.strip():
                    chunks.append(value.strip())
                    continue
                value = part.get("content")
                if isinstance(value, str) and value.strip():
                    chunks.append(value.strip())
            if chunks:
                return "\n".join(chunks)
        for key in ("text", "output_text", "final", "final_answer"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _openai_finalize_after_tool_budget(
        self,
        rid: str,
        url: str,
        headers: dict[str, str],
        messages: list[dict[str, Any]],
        prompt_tokens_total: int,
        completion_tokens_total: int,
        cost_total: float,
        tool_call_count: int,
        reason: str = "tool authority budget is exhausted",
        context_budget_tokens: int | None = None,
    ) -> tuple[str, int, int, float, int]:
        """Close tool authority and require one evidence-bounded final answer."""
        final_messages = list(messages)
        closure_instruction = (
            "CAPT tool access is now closed because " + reason + ". Do not request or assume "
            "additional tool access. Produce the best final answer now using only "
            "evidence already present in this conversation. Preserve uncertainty "
            "and mark unresolved claims BLOCKED or UNVERIFIED."
        )
        if self._strict_charter_policy() is not None:
            closure_instruction += (
                " This run is bound to a strict CAPT Vessel Charter. Use the reserved final "
                "output for the physical ledger first: emit all required CAPT_CANDIDATE rows, "
                "then CAPT_CHARTER_AUDIT, then all required CAPT_VESSEL rows, before optional "
                "synthesis. Keep rows compact and schema-complete. Do not substitute prose for "
                "countable ledger rows. Emit CAPT_COHORT_INCOMPLETE only if the required ledger "
                "still cannot be completed inside this reserved final-output budget."
            )
        final_messages.append({"role": "user", "content": closure_instruction})
        final_output_tokens = (
            self._final_answer_reserve_tokens(context_budget_tokens)
            if context_budget_tokens is not None
            else int(self.governor.max_output_tokens_per_request)
        )
        body = {
            "model": self.model,
            "messages": final_messages,
            "stream": False,
            "max_tokens": final_output_tokens,
        }
        data = self._post_json(
            rid, url, body, headers, reasoning_policy="answer_only"
        )
        p_tokens, c_tokens, cost = self._usage_from(data)
        prompt_tokens_total += p_tokens or 0
        completion_tokens_total += c_tokens or 0
        cost_total += cost
        choices = data.get("choices") or []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = choice.get("message", {})
        if not isinstance(message, dict):
            raise ProviderDriverFailure("provider returned malformed final assistant message")
        text = self._final_facing_text(message)
        finish_reason = choice.get("finish_reason")
        if not isinstance(finish_reason, str) or not finish_reason:
            finish_reason = None
        with self._lock:
            run = self.runs.setdefault(rid, {})
            run.setdefault("toolClosureReason", reason)
            run["finalizationReasoningMode"] = "answer_only"
            run["finalizationTextSource"] = "closure_response" if text else "none"
            run["finalizationFinishReason"] = finish_reason
        if not text:
            raise ProviderDriverFailure(
                "provider returned no final-facing content after tool budget closure"
            )
        return (
            text, prompt_tokens_total, completion_tokens_total, cost_total, tool_call_count,
        )

    def _ollama_with_tools(
        self,
        rid: str,
        prompt: str,
        headers: dict[str, str],
    ) -> tuple[str, int, int, float, int]:
        """Run a bounded Ollama /api/chat tool loop through the same ToolBroker bridge."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        tools = self.tool_bridge.openai_tools()
        tool_call_count = 0
        prompt_tokens_total = 0
        completion_tokens_total = 0
        max_tool_rounds = int(self.tool_bridge.max_calls)
        if max_tool_rounds <= 0:
            raise ProviderDriverFailure("provider tool capability budget is invalid")
        url = self.base_url.replace("/v1", "") + "/api/chat"

        for round_index in range(max_tool_rounds + 1):
            body = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "stream": False,
                "options": {"num_predict": self.governor.max_output_tokens_per_request},
            }
            data = self._post_json(rid, url, body, headers)
            prompt_value = data.get("prompt_eval_count")
            completion_value = data.get("eval_count")
            if isinstance(prompt_value, (int, float)):
                prompt_tokens_total += int(prompt_value)
            if isinstance(completion_value, (int, float)):
                completion_tokens_total += int(completion_value)

            message = data.get("message")
            if not isinstance(message, dict):
                raise ProviderDriverFailure("ollama returned malformed assistant message")
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                text = message.get("content") or ""
                if not isinstance(text, str) or not text:
                    raise ProviderDriverFailure("provider returned no content")
                return (
                    text,
                    prompt_tokens_total,
                    completion_tokens_total,
                    0.0,
                    tool_call_count,
                )
            if round_index >= max_tool_rounds:
                raise ProviderDriverFailure("provider tool-call round limit exceeded")
            if not isinstance(tool_calls, list):
                raise ProviderDriverFailure("ollama returned malformed tool_calls")

            messages.append({
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls,
            })
            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict):
                    raise ProviderDriverFailure("ollama returned malformed tool call")
                function = call.get("function")
                if not isinstance(function, dict):
                    raise ProviderDriverFailure("ollama returned malformed function call")
                name = function.get("name")
                if not isinstance(name, str) or not name:
                    raise ProviderDriverFailure("ollama tool call missing function name")
                call_id = "ollama-call-%d-%d-%s" % (round_index, index, name)
                if tool_call_count >= self.tool_bridge.max_calls:
                    raise ProviderDriverFailure("provider tool-call count limit exceeded")
                tool_result = self.tool_bridge.execute_call(
                    name,
                    function.get("arguments", {}),
                    call_id=call_id,
                )
                tool_call_count += 1
                messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": json.dumps(tool_result, sort_keys=True, separators=(",", ":")),
                })
        raise ProviderDriverFailure("provider tool-call loop did not terminate")

    def _execute_image(
        self,
        rid: str,
        wo: dict[str, Any],
        prompt: str,
        prompt_digest: str,
        headers: dict[str, str],
        estimated_prompt_tokens: int,
    ) -> dict[str, Any]:
        if self.provider_id == "ollama":
            raise ProviderDriverFailure("image modality is not supported by the ollama provider path")
        url = self.base_url + "/images"
        body = {
            "model": self.model,
            "prompt": prompt,
            "output_format": self.output_format,
        }
        data = self._post_json(rid, url, body, headers)
        items = data.get("data")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise ProviderDriverFailure("image provider returned no image data")
        encoded = items[0].get("b64_json")
        if not isinstance(encoded, str) or not encoded:
            raise ProviderDriverFailure("image provider returned no base64 image")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ProviderDriverFailure("image provider returned invalid base64 image") from exc
        if not image_bytes:
            raise ProviderDriverFailure("image provider returned an empty image")
        if len(image_bytes) > 64 * 1024 * 1024:
            raise ProviderDriverFailure("image provider artifact exceeds 64 MiB safety limit")

        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        prompt_tokens = usage.get("prompt_tokens")
        prompt_tokens = (
            int(prompt_tokens)
            if isinstance(prompt_tokens, (int, float))
            else estimated_prompt_tokens
        )
        completion_tokens = usage.get("completion_tokens")
        completion_tokens = (
            int(completion_tokens)
            if isinstance(completion_tokens, (int, float))
            else 0
        )
        raw_cost = usage.get("cost", usage.get("cost_usd", 0.0))
        cost_usd = float(raw_cost) if isinstance(raw_cost, (int, float)) else 0.0
        resource_receipt = self.governor.record_usage(
            prompt_tokens=max(1, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
            cost_usd=cost_usd,
        )

        response_digest = "sha256:" + hashlib.sha256(image_bytes).hexdigest()
        extension = "jpg" if self.output_format == "jpeg" else self.output_format
        media_type = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }[self.output_format]
        path = self.root / ("provider-image-%s.%s" % (rid, extension))
        path.write_bytes(image_bytes)
        artifact_digest = "sha256:" + hashlib.sha256(image_bytes).hexdigest()
        ep_class = endpoint_class(self.base_url)
        summary = (
            "Generated untrusted provider image artifact "
            f"{artifact_digest} ({self.output_format}, {len(image_bytes)} bytes)."
        )
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
                    "summary": summary,
                    "observedAt": wo.get("submittedAt", ""),
                }
            ],
            "artifactCandidate": {
                "schemaVersion": "1.0.0",
                "candidateId": "ac-" + rid,
                "driverRunId": rid,
                "artifactPath": str(path),
                "artifactDigest": artifact_digest,
                "artifactKind": "image",
                "mediaType": media_type,
                "producedAt": wo.get("submittedAt", ""),
            },
            "diagnostics": {
                "provider": self.provider_id,
                "model": self.model,
                "reasoningEffortRequested": self.reasoning_effort or None,
                "endpointClass": ep_class,
                "promptDigest": prompt_digest,
                "responseDigest": response_digest,
                "outputModality": "image",
                "outputFormat": self.output_format,
                "imageBytes": len(image_bytes),
                "dispatchBoundary": dispatch_boundary,
                "cancelRequested": cancel_requested,
                "toolCallCount": 0,
                "contextBudgetTokens": self._work_order_context_budget_tokens(wo),
                "requestTimeoutBudgetSeconds": self.runs[rid].get("requestTimeoutBudgetSeconds"),
                "resourceUsage": resource_receipt,
            },
        }

    def _execute(self, rid, wo):
        timeout_seconds = self._work_order_timeout_seconds(wo)
        self._request_deadlines[rid] = time.monotonic() + timeout_seconds
        with self._lock:
            self.runs[rid]["requestTimeoutBudgetSeconds"] = timeout_seconds
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

        if self.output_modality == "image":
            return self._execute_image(
                rid, wo, prompt, prompt_digest, headers, estimated_prompt_tokens
            )

        tool_call_count = 0
        context_budget_tokens = self._work_order_context_budget_tokens(wo)
        if self.provider_id == "ollama" and self.tool_bridge is not None:
            text, prompt_tokens, completion_tokens, cost_usd, tool_call_count = self._ollama_with_tools(
                rid, prompt, headers
            )
        elif self.tool_bridge is not None:
            text, prompt_tokens, completion_tokens, cost_usd, tool_call_count = self._openai_with_tools(
                rid, prompt, headers, context_budget_tokens
            )
        else:
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
                    **self._reasoning_fields,
                }
            data = self._post_json(rid, url, body, headers)
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

        if prompt_tokens <= 0:
            prompt_tokens = estimated_prompt_tokens
        if completion_tokens <= 0:
            completion_tokens = max(1, len(text) // 4)
        resource_receipt = self.governor.record_usage(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost_usd
        )
        response_digest = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
        ep_class = endpoint_class(self.base_url)
        artifact = (
            "# CAPT Provider Observation\n\n"
            "Provider: %s\nModel: %s\nEndpointClass: %s\nReasoningEffort: %s\nPromptDigest: %s\n"
            "ResponseDigest: %s\n\n%s\n"
            % (
                self.provider_id,
                self.model,
                ep_class,
                self.reasoning_effort or "provider-default",
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
                "reasoningEffort": self.reasoning_effort or None,
                "reasoningEffortRequested": self.reasoning_effort or None,
                "endpointClass": ep_class,
                "promptDigest": prompt_digest,
                "responseDigest": response_digest,
                "dispatchBoundary": dispatch_boundary,
                "cancelRequested": cancel_requested,
                "toolCallCount": tool_call_count,
                "toolClosureReason": self.runs[rid].get("toolClosureReason"),
                "contextBudgetTokens": context_budget_tokens,
                "finalAnswerReserveTokens": self.runs[rid].get("finalAnswerReserveTokens"),
                "charterMinimumOutputTokens": self._charter_minimum_output_tokens() or None,
                "finalizationReasoningMode": self.runs[rid].get("finalizationReasoningMode"),
                "finalizationTextSource": self.runs[rid].get("finalizationTextSource"),
                "finalizationFinishReason": self.runs[rid].get("finalizationFinishReason"),
                "resourceUsage": resource_receipt,
            },
        }
