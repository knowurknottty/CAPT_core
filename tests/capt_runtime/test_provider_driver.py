from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from capt_runtime.drivers.provider import ProviderDriver, ProviderDriverFailure


class _Server(BaseHTTPRequestHandler):
    seen = {}

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        self.__class__.seen = {
            "path": self.path,
            "body": json.loads(raw),
            "auth": self.headers.get("Authorization"),
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = (
            {"response": "CAPT TEST"}
            if self.path.endswith("/api/generate")
            else {"choices": [{"message": {"content": "CAPT TEST"}}]}
        )
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def _resolver():
    class Resolver:
        def resolve_for_execution(self, **_):
            return type("Task", (), {"objective": "minimal prompt"})()

    return Resolver()


def test_openrouter_driver_provenance_and_secret_not_persisted(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        secret = "synthetic-secret-not-to-persist"
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="openrouter",
            model="deepseek/deepseek-v4-flash-0731",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key=secret,
            task_resolver=_resolver(),
            reasoning_effort="xhigh",
        )
        out = asyncio.run(
            driver.submit(
                {
                    "driverRunId": "dr-1",
                    "missionId": "m-1",
                    "taskId": "t-1",
                    "contextSlice": {},
                    "submittedAt": "2026-01-01T00:00:00Z",
                }
            )
        )
        assert _Server.seen["path"] == "/v1/chat/completions"
        assert _Server.seen["body"]["model"] == "deepseek/deepseek-v4-flash-0731"
        assert _Server.seen["body"]["max_tokens"] == 49_152
        assert _Server.seen["body"]["reasoning"] == {"effort": "xhigh"}
        assert _Server.seen["auth"] == "Bearer " + secret
        assert out["state"] == "completed"
        assert out["dispatchBoundary"] == "result_persisted"
        assert out["transportCancellationSupported"] is False
        assert out["diagnostics"]["provider"] == "openrouter"
        assert out["diagnostics"]["reasoningEffortRequested"] == "xhigh"
        assert out["diagnostics"]["promptDigest"].startswith("sha256:")
        assert out["diagnostics"]["responseDigest"].startswith("sha256:")
        assert secret not in str(out)
        assert secret not in Path(out["artifactCandidate"]["artifactPath"]).read_text()
        inspected = asyncio.run(driver.inspect("dr-1"))
        assert inspected["state"] == "completed"
        assert inspected["dispatchBoundary"] == "result_persisted"
        reconciled = asyncio.run(driver.reconcile("dr-1"))
        assert reconciled["result"] == "response_completed"
    finally:
        server.shutdown()
        server.server_close()



def test_provider_driver_http_timeout_uses_governed_work_order_budget(monkeypatch, tmp_path: Path):
    import capt_runtime.drivers.provider as provider_module

    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "CAPT_TIMEOUT_BUDGET_OK"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            }).encode()

    def fake_urlopen(_request, timeout):
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(provider_module.urllib.request, "urlopen", fake_urlopen)
    driver = ProviderDriver(
        str(tmp_path), provider_id="mtplx", model="local-model",
        base_url="http://127.0.0.1:18085/v1", task_resolver=_resolver(),
    )
    out = asyncio.run(driver.submit({
        "driverRunId": "dr-timeout-budget",
        "missionId": "m-timeout-budget",
        "taskId": "t-timeout-budget",
        "contextSlice": {"budgets": {"maxSeconds": 600}},
        "submittedAt": "2026-09-15T00:00:00Z",
    }))

    assert out["state"] == "completed"
    assert 590 < seen["timeout"] <= 600
    inspected = asyncio.run(driver.inspect("dr-timeout-budget"))
    assert inspected["requestTimeoutBudgetSeconds"] == 600.0
    assert "dr-timeout-budget" not in driver._request_deadlines


def test_provider_driver_timeout_defaults_to_legacy_bound_without_work_order_budget():
    assert ProviderDriver._work_order_timeout_seconds({"contextSlice": {}}) == 120.0
    assert ProviderDriver._work_order_timeout_seconds(
        {"contextSlice": {"budgets": {"maxSeconds": 600}}}
    ) == 600.0

def test_ollama_driver_uses_native_generate_endpoint(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="ollama",
            model="local-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
        )
        out = asyncio.run(
            driver.submit(
                {
                    "driverRunId": "dr-2",
                    "missionId": "m-1",
                    "taskId": "t-1",
                    "contextSlice": {},
                    "submittedAt": "2026-01-01T00:00:00Z",
                }
            )
        )
        assert _Server.seen["path"] == "/api/generate"
        assert _Server.seen["body"] == {
            "model": "local-model",
            "prompt": "minimal prompt",
            "stream": False,
            "options": {"num_predict": 49_152},
        }
        assert _Server.seen["auth"] is None
        assert out["state"] == "completed"
        assert out["diagnostics"]["endpointClass"] == "local"
    finally:
        server.shutdown()
        server.server_close()


def test_cancel_is_truthful_request_not_false_transport_abort(tmp_path: Path):
    driver = ProviderDriver(
        str(tmp_path),
        provider_id="ollama",
        model="local-model",
        base_url="http://127.0.0.1:1/v1",
        task_resolver=_resolver(),
    )
    driver.runs["dr-cancel"] = {
        "state": "running",
        "cancelRequested": False,
        "dispatchBoundary": "request_started",
    }
    receipt = asyncio.run(driver.cancel("dr-cancel", "operator requested"))
    assert receipt == {
        "driverRunId": "dr-cancel",
        "state": "cancel_requested",
        "transportCancellationSupported": False,
    }
    inspected = asyncio.run(driver.inspect("dr-cancel"))
    assert inspected["cancelRequested"] is True
    assert inspected["state"] == "cancel_requested"
    reconciled = asyncio.run(driver.reconcile("dr-cancel"))
    assert reconciled["result"] == "external_state_unknown"


def test_cancel_rejects_unknown_run(tmp_path: Path):
    driver = ProviderDriver(
        str(tmp_path),
        provider_id="ollama",
        model="local-model",
        base_url="http://127.0.0.1:1/v1",
    )
    try:
        asyncio.run(driver.cancel("missing", "operator requested"))
    except ProviderDriverFailure as exc:
        assert "unknown driverRunId" in str(exc)
    else:
        raise AssertionError("unknown cancellation must fail")


def test_governed_provider_uses_explicit_approved_dispatch_prompt(tmp_path: Path):
    from capt_runtime.approval_dispatch import register_expected_prompt_digest
    import hashlib

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        approved = "approved-dispatch\n" + ("context evidence " * 60)
        digest = "sha256:" + hashlib.sha256(approved.encode()).hexdigest()
        register_expected_prompt_digest("dr-bound-long", digest)
        driver = ProviderDriver(
            str(tmp_path), provider_id="ollama", model="local-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(), dispatch_prompt=approved,
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-bound-long", "missionId": "m-1",
            "taskId": "t-1", "contextSlice": {},
            "submittedAt": "2026-01-01T00:00:00Z",
        }))
        assert len(approved) > 512
        assert _Server.seen["body"]["prompt"] == approved
        assert out["diagnostics"]["promptDigest"] == digest
    finally:
        server.shutdown()
        server.server_close()


def test_governed_provider_explicit_prompt_still_fails_closed_on_digest_mismatch(tmp_path: Path):
    from capt_runtime.approval_dispatch import register_expected_prompt_digest
    import hashlib

    approved = "approved prompt"
    expected = "different approved prompt"
    register_expected_prompt_digest(
        "dr-bound-mismatch", "sha256:" + hashlib.sha256(expected.encode()).hexdigest()
    )
    driver = ProviderDriver(
        str(tmp_path), provider_id="ollama", model="local-model",
        base_url="http://127.0.0.1:1/v1", task_resolver=_resolver(),
        dispatch_prompt=approved,
    )
    with __import__("pytest").raises(Exception, match="DISPATCH_DIGEST_MISMATCH"):
        asyncio.run(driver.submit({
            "driverRunId": "dr-bound-mismatch", "missionId": "m-1",
            "taskId": "t-1", "contextSlice": {},
            "submittedAt": "2026-01-01T00:00:00Z",
        }))


def test_openai_compatible_loopback_driver_reports_local_endpoint(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="mtplx",
            model="qwen3.8-27b-mtplx",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-local-openai",
            "missionId": "m-local",
            "taskId": "t-local",
            "contextSlice": {},
            "submittedAt": "2026-08-18T00:00:00Z",
        }))
        assert _Server.seen["path"] == "/v1/chat/completions"
        assert _Server.seen["auth"] is None
        assert out["diagnostics"]["endpointClass"] == "local"
        assert "EndpointClass: local" in Path(out["artifactCandidate"]["artifactPath"]).read_text()
    finally:
        server.shutdown()
        server.server_close()


class _ToolLoopServer(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        self.__class__.calls.append({"path": self.path, "body": body})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if len(self.__class__.calls) == 1:
            payload = {
                "choices": [{"message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call-read-1",
                        "type": "function",
                        "function": {
                            "name": "capt_file_read",
                            "arguments": json.dumps({"path": "hello.txt"}),
                        },
                    }],
                }}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            }
        else:
            payload = {
                "choices": [{"message": {
                    "role": "assistant",
                    "content": "The file says CAPT_TOOL_LOOP_OK",
                }}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 8},
            }
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_openai_provider_tool_loop_executes_real_capt_toolbridge(tmp_path: Path):
    from capt_runtime.composition import create_runtime
    from capt_runtime.model_authority import normalize_model_authority
    from tests.capt_runtime.test_model_tool_bridge import _bridge

    (tmp_path / "hello.txt").write_text("CAPT_TOOL_LOOP_OK")
    runtime = create_runtime(str(tmp_path / "rt.db"))
    profile = normalize_model_authority(None, target_root=str(tmp_path))
    bridge = _bridge(runtime, tmp_path, profile, profile["toolOperations"])
    _ToolLoopServer.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ToolLoopServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path / "staging"),
            provider_id="mtplx",
            model="tool-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
            tool_bridge=bridge,
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-provider-tool-loop",
            "missionId": "m-model-tools",
            "taskId": "t-model-tools",
            "contextSlice": {},
            "submittedAt": "2026-09-07T06:00:00Z",
        }))
        assert out["state"] == "completed"
        assert out["observations"][0]["summary"] == "The file says CAPT_TOOL_LOOP_OK"
        assert len(_ToolLoopServer.calls) == 2
        first = _ToolLoopServer.calls[0]["body"]
        assert [item["function"]["name"] for item in first["tools"]] == [
            "capt_file_read", "capt_file_search"
        ]
        second_messages = _ToolLoopServer.calls[1]["body"]["messages"]
        tool_message = next(item for item in second_messages if item["role"] == "tool")
        assert "CAPT_TOOL_LOOP_OK" in tool_message["content"]
        assert out["diagnostics"]["toolCallCount"] == 1
    finally:
        server.shutdown()
        server.server_close()
        runtime.close()


class _NineRoundToolServer(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        self.__class__.calls.append(json.loads(raw))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        round_index = len(self.__class__.calls) - 1
        if round_index < 9:
            message = {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": f"call-{round_index}", "type": "function",
                    "function": {"name": "capt_file_read", "arguments": "{}"},
                }],
            }
        else:
            message = {"role": "assistant", "content": "NINTH_ROUND_COMPLETED"}
        payload = {
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


class _BoundedBridge:
    max_calls = 32

    @staticmethod
    def openai_tools():
        return [{
            "type": "function",
            "function": {"name": "capt_file_read", "description": "read", "parameters": {"type": "object", "properties": {}}},
        }]

    @staticmethod
    def execute_call(_name, _arguments, *, call_id):
        return {"toolExecutionId": "te-" + call_id, "status": "succeeded", "values": {}}


def test_openai_tool_rounds_use_existing_bridge_capability_budget(tmp_path: Path):
    _NineRoundToolServer.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _NineRoundToolServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path / "staging"), provider_id="mtplx", model="tool-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(), tool_bridge=_BoundedBridge(),
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-nine-rounds", "missionId": "m-nine-rounds",
            "taskId": "t-nine-rounds", "contextSlice": {},
            "submittedAt": "2026-09-15T00:00:00Z",
        }))
        assert out["state"] == "completed"
        assert out["observations"][0]["summary"] == "NINTH_ROUND_COMPLETED"
        assert out["diagnostics"]["toolCallCount"] == 9
        assert len(_NineRoundToolServer.calls) == 10
    finally:
        server.shutdown()
        server.server_close()



class _ToolBudgetClosureServer(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        self.__class__.calls.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        index = len(self.__class__.calls) - 1
        if index < 2:
            message = {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": f"closure-call-{index}", "type": "function",
                    "function": {"name": "capt_file_read", "arguments": "{}"},
                }],
            }
        else:
            assert "tools" not in body
            assert any(
                m.get("role") == "user" and "tool authority budget is exhausted" in str(m.get("content", ""))
                for m in body["messages"]
            )
            message = {"role": "assistant", "content": "BUDGET_CLOSED_FINAL"}
        payload = {
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


class _TwoCallBridge(_BoundedBridge):
    max_calls = 2


def test_openai_tool_budget_closes_tools_and_forces_final_answer(tmp_path: Path):
    _ToolBudgetClosureServer.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ToolBudgetClosureServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path / "staging"), provider_id="mtplx", model="tool-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(), tool_bridge=_TwoCallBridge(),
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-tool-budget-closure", "missionId": "m-tool-budget",
            "taskId": "t-tool-budget", "contextSlice": {},
            "submittedAt": "2026-09-15T00:00:00Z",
        }))
        assert out["state"] == "completed"
        assert out["observations"][0]["summary"] == "BUDGET_CLOSED_FINAL"
        assert out["diagnostics"]["toolCallCount"] == 2
        assert len(_ToolBudgetClosureServer.calls) == 3
        assert "tools" not in _ToolBudgetClosureServer.calls[-1]
    finally:
        server.shutdown()
        server.server_close()


class _OllamaToolLoopServer(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        self.__class__.calls.append({"path": self.path, "body": body})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if len(self.__class__.calls) == 1:
            payload = {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "capt_file_read",
                            "arguments": {"path": "hello.txt"},
                        }
                    }],
                },
                "prompt_eval_count": 11,
                "eval_count": 3,
            }
        else:
            payload = {
                "message": {
                    "role": "assistant",
                    "content": "Ollama saw CAPT_OLLAMA_TOOL_OK",
                },
                "prompt_eval_count": 19,
                "eval_count": 7,
            }
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_ollama_provider_tool_loop_uses_chat_and_real_capt_toolbridge(tmp_path: Path):
    from capt_runtime.composition import create_runtime
    from capt_runtime.model_authority import normalize_model_authority
    from tests.capt_runtime.test_model_tool_bridge import _bridge

    (tmp_path / "hello.txt").write_text("CAPT_OLLAMA_TOOL_OK")
    runtime = create_runtime(str(tmp_path / "rt.db"))
    profile = normalize_model_authority(None, target_root=str(tmp_path))
    bridge = _bridge(runtime, tmp_path, profile, profile["toolOperations"])
    _OllamaToolLoopServer.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaToolLoopServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path / "staging"),
            provider_id="ollama",
            model="tool-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
            tool_bridge=bridge,
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-ollama-tool-loop",
            "missionId": "m-model-tools",
            "taskId": "t-model-tools",
            "contextSlice": {},
            "submittedAt": "2026-09-07T06:00:00Z",
        }))
        assert out["state"] == "completed"
        assert out["observations"][0]["summary"] == "Ollama saw CAPT_OLLAMA_TOOL_OK"
        assert len(_OllamaToolLoopServer.calls) == 2
        first = _OllamaToolLoopServer.calls[0]
        assert first["path"] == "/api/chat"
        assert [item["function"]["name"] for item in first["body"]["tools"]] == [
            "capt_file_read", "capt_file_search"
        ]
        second_messages = _OllamaToolLoopServer.calls[1]["body"]["messages"]
        tool_message = next(item for item in second_messages if item["role"] == "tool")
        assert tool_message["tool_name"] == "capt_file_read"
        assert "CAPT_OLLAMA_TOOL_OK" in tool_message["content"]
        assert out["diagnostics"]["toolCallCount"] == 1
    finally:
        server.shutdown()
        server.server_close()
        runtime.close()


class _ContextHeadroomServer(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        self.__class__.calls.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        index = len(self.__class__.calls) - 1
        if index == 0:
            message = {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": "headroom-call-0", "type": "function",
                    "function": {"name": "capt_file_read", "arguments": "{}"},
                }],
            }
            usage = {"prompt_tokens": 22000, "completion_tokens": 32}
        else:
            assert "tools" not in body
            assert any(
                m.get("role") == "user" and "final answer" in str(m.get("content", "")).lower()
                for m in body["messages"]
            )
            message = {"role": "assistant", "content": "HEADROOM_FINAL_COMPLETE"}
            usage = {"prompt_tokens": 21100, "completion_tokens": 1200}
        self.wfile.write(json.dumps({"choices": [{"message": message}], "usage": usage}).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_openai_tool_loop_preserves_final_answer_context_headroom(tmp_path: Path):
    _ContextHeadroomServer.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ContextHeadroomServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        driver = ProviderDriver(
            str(tmp_path / "staging"), provider_id="mtplx", model="tool-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(), tool_bridge=_BoundedBridge(),
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-context-headroom", "missionId": "m-context-headroom",
            "taskId": "t-context-headroom",
            "contextSlice": {"budgets": {"maxSeconds": 600, "maxTokens": 32000}},
            "submittedAt": "2026-09-15T00:00:00Z",
        }))
        assert out["state"] == "completed"
        assert out["observations"][0]["summary"] == "HEADROOM_FINAL_COMPLETE"
        assert out["diagnostics"]["toolCallCount"] == 0
        assert out["diagnostics"]["toolClosureReason"] == "context_headroom"
        assert len(_ContextHeadroomServer.calls) == 2
        assert "tools" not in _ContextHeadroomServer.calls[-1]
    finally:
        server.shutdown()
        server.server_close()


def test_openrouter_reasoning_effort_uses_reasoning_map_and_records_diagnostics(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="openrouter",
            model="stealth/space-bunny-alpha",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
            reasoning_effort="xhigh",
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-reasoning-openrouter",
            "missionId": "m-reasoning",
            "taskId": "t-reasoning",
            "contextSlice": {},
            "submittedAt": "2026-09-23T00:00:00Z",
        }))
        assert _Server.seen["body"]["reasoning"] == {"effort": "xhigh"}
        assert "reasoning_effort" not in _Server.seen["body"]
        assert out["diagnostics"]["reasoningEffort"] == "xhigh"
        assert "ReasoningEffort: xhigh" in Path(
            out["artifactCandidate"]["artifactPath"]
        ).read_text()
    finally:
        server.shutdown()
        server.server_close()


class _ImageServer(BaseHTTPRequestHandler):
    seen = {}

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        self.__class__.seen = {
            "path": self.path,
            "body": json.loads(raw),
            "auth": self.headers.get("Authorization"),
        }
        payload = b"\x89PNG\r\n\x1a\nCAPT_IMAGE_TEST"
        import base64
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "data": [{"b64_json": base64.b64encode(payload).decode()}],
            "usage": {"prompt_tokens": 17, "cost": 0.0},
        }).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_openrouter_image_driver_uses_dedicated_endpoint_and_binary_artifact(tmp_path: Path):
    _ImageServer.seen = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ImageServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        secret = "synthetic-image-secret"
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="openrouter",
            model="inclusionai/ming-image-0.1-design",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key=secret,
            dispatch_prompt="render one governed campaign board",
            output_modality="image",
            output_format="png",
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-image-1",
            "missionId": "m-image",
            "taskId": "t-image",
            "contextSlice": {"budgets": {"maxSeconds": 300, "maxTokens": 32000}},
            "submittedAt": "2026-09-26T00:00:00Z",
        }))
        assert _ImageServer.seen["path"] == "/v1/images"
        assert _ImageServer.seen["body"] == {
            "model": "inclusionai/ming-image-0.1-design",
            "prompt": "render one governed campaign board",
            "output_format": "png",
        }
        assert _ImageServer.seen["auth"] == "Bearer " + secret
        assert out["state"] == "completed"
        assert out["artifactCandidate"]["artifactKind"] == "image"
        assert out["artifactCandidate"]["mediaType"] == "image/png"
        artifact = Path(out["artifactCandidate"]["artifactPath"])
        assert artifact.suffix == ".png"
        assert artifact.read_bytes() == b"\x89PNG\r\n\x1a\nCAPT_IMAGE_TEST"
        assert out["diagnostics"]["outputModality"] == "image"
        assert out["diagnostics"]["outputFormat"] == "png"
        assert out["diagnostics"]["imageBytes"] == len(artifact.read_bytes())
        assert "b64_json" not in str(out)
        assert secret not in str(out)
        assert secret.encode() not in artifact.read_bytes()
    finally:
        server.shutdown()
        server.server_close()


def test_generic_openai_compatible_reasoning_effort_uses_top_level_field(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Server)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="mtplx",
            model="reasoning-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
            reasoning_effort="high",
        )
        asyncio.run(driver.submit({
            "driverRunId": "dr-reasoning-generic",
            "missionId": "m-reasoning",
            "taskId": "t-reasoning",
            "contextSlice": {},
            "submittedAt": "2026-09-23T00:00:00Z",
        }))
        assert _Server.seen["body"]["reasoning_effort"] == "high"
        assert "reasoning" not in _Server.seen["body"]
    finally:
        server.shutdown()
        server.server_close()


def test_provider_image_modality_validates_format(tmp_path: Path):
    try:
        ProviderDriver(
            str(tmp_path), provider_id="openrouter", model="image-model",
            base_url="https://example.invalid/v1",
            output_modality="image", output_format="gif",
        )
    except ValueError as exc:
        assert str(exc) == "PROVIDER_IMAGE_OUTPUT_FORMAT_INVALID"
    else:
        raise AssertionError("unsupported image format must fail closed")


class _ErrorServer(BaseHTTPRequestHandler):
    secret = ""

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps({
            "error": {
                "message": "route missing credential=" + self.__class__.secret + " " + ("x" * 5000)
            }
        }).encode()
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_provider_http_error_body_is_bounded_and_secret_redacted(tmp_path: Path):
    secret = "synthetic-super-secret"
    _ErrorServer.secret = secret
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ErrorServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        driver = ProviderDriver(
            str(tmp_path),
            provider_id="openrouter",
            model="inclusionai/ming-image-0.1-design",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key=secret,
            dispatch_prompt="render",
            output_modality="image",
            output_format="png",
        )
        try:
            asyncio.run(driver.submit({
                "driverRunId": "dr-image-error",
                "contextSlice": {"budgets": {"maxSeconds": 30, "maxTokens": 32000}},
            }))
        except ProviderDriverFailure as exc:
            message = str(exc)
            assert message.startswith("provider HTTP 404:")
            assert "route missing" in message
            assert secret not in message
            assert "[REDACTED]" in message
            assert len(message) < 1100
        else:
            raise AssertionError("HTTP 404 must fail closed")
    finally:
        server.shutdown()
        server.server_close()


def test_reasoning_effort_rejects_invalid_or_native_ollama_values(tmp_path: Path):
    from capt_runtime.reasoning import ReasoningConfigurationError

    with __import__("pytest").raises(
        ReasoningConfigurationError, match="REASONING_EFFORT_UNSUPPORTED"
    ):
        ProviderDriver(
            str(tmp_path / "bad"),
            provider_id="openrouter",
            model="model",
            base_url="https://openrouter.ai/api/v1",
            reasoning_effort="turbo-max",
        )
    with __import__("pytest").raises(
        ReasoningConfigurationError, match="REASONING_EFFORT_UNSUPPORTED_PROVIDER"
    ):
        ProviderDriver(
            str(tmp_path / "ollama"),
            provider_id="ollama",
            model="model",
            base_url="http://127.0.0.1:11434/v1",
            reasoning_effort="high",
        )


class _OpenRouterAnswerOnlyClosureServer(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(raw)
        self.__class__.calls.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        index = len(self.__class__.calls) - 1
        if index < 2:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": f"answer-only-call-{index}",
                    "type": "function",
                    "function": {"name": "capt_file_read", "arguments": "{}"},
                }],
            }
        else:
            message = {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "ANSWER_ONLY_FINAL"},
                    {"type": "text", "text": "SECOND_BLOCK"},
                ],
            }
        payload = {
            "choices": [{"message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4},
        }
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_openrouter_tool_closure_serializes_answer_only_reasoning_and_visible_text(tmp_path: Path):
    _OpenRouterAnswerOnlyClosureServer.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OpenRouterAnswerOnlyClosureServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        driver = ProviderDriver(
            str(tmp_path / "staging-answer-only"),
            provider_id="openrouter",
            model="test/reasoning-model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            task_resolver=_resolver(),
            tool_bridge=_TwoCallBridge(),
            reasoning_effort="high",
        )
        out = asyncio.run(driver.submit({
            "driverRunId": "dr-answer-only-closure",
            "missionId": "m-answer-only-closure",
            "taskId": "t-answer-only-closure",
            "contextSlice": {},
            "submittedAt": "2026-10-07T00:00:00Z",
        }))
        assert out["state"] == "completed"
        assert out["observations"][0]["summary"] == "ANSWER_ONLY_FINAL\nSECOND_BLOCK"
        assert len(_OpenRouterAnswerOnlyClosureServer.calls) == 3
        assert _OpenRouterAnswerOnlyClosureServer.calls[0]["reasoning"] == {"effort": "high"}
        assert _OpenRouterAnswerOnlyClosureServer.calls[1]["reasoning"] == {"effort": "high"}
        assert _OpenRouterAnswerOnlyClosureServer.calls[2]["reasoning"] == {"effort": "none"}
        assert "tools" not in _OpenRouterAnswerOnlyClosureServer.calls[2]
        assert out["diagnostics"]["finalizationReasoningMode"] == "answer_only"
        assert out["diagnostics"]["finalizationTextSource"] == "closure_response"
        assert out["diagnostics"]["finalizationFinishReason"] == "stop"
    finally:
        server.shutdown()
        server.server_close()


def test_final_facing_text_rejects_hidden_reasoning_only():
    assert ProviderDriver._final_facing_text({
        "content": "",
        "reasoning": "hidden reasoning must not count",
    }) == ""


def test_tool_closure_does_not_promote_stale_prior_visible_text(tmp_path: Path, monkeypatch):
    driver = ProviderDriver(
        str(tmp_path / "staging-stale-prior"),
        provider_id="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        reasoning_effort="high",
    )
    rid = "dr-stale-prior-visible"
    driver.runs[rid] = {"state": "running"}

    def fake_post(_rid, _url, _body, _headers, **_kwargs):
        return {
            "choices": [{"message": {"content": "", "reasoning": "hidden only"}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 0},
        }

    monkeypatch.setattr(driver, "_post_json", fake_post)
    messages = [
        {"role": "user", "content": "work"},
        {"role": "assistant", "content": "prior synthesis before tool evidence", "tool_calls": [{
            "id": "stale-call",
            "type": "function",
            "function": {"name": "capt_file_read", "arguments": "{}"},
        }]},
        {"role": "tool", "tool_call_id": "stale-call", "name": "capt_file_read", "content": "{\"new\":\"evidence\"}"},
    ]
    import pytest
    with pytest.raises(ProviderDriverFailure, match="no final-facing content after tool budget closure"):
        driver._openai_finalize_after_tool_budget(
            rid,
            "https://example.invalid/v1/chat/completions",
            {},
            messages,
            0, 0, 0.0, 1,
        )
    assert driver.runs[rid]["finalizationTextSource"] == "none"
    assert driver.runs[rid]["finalizationFinishReason"] == "length"


def test_provider_response_read_enforces_absolute_wall_clock_deadline(tmp_path: Path, monkeypatch):
    import time
    import pytest

    class SlowResponse:
        def __init__(self):
            self.closed = threading.Event()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

        def close(self):
            self.closed.set()

        def read(self):
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and not self.closed.is_set():
                time.sleep(0.01)
            if self.closed.is_set():
                raise OSError("response closed")
            return b'{"choices":[{"message":{"content":"late"}}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: SlowResponse())
    driver = ProviderDriver(
        str(tmp_path / "staging-hard-deadline"),
        provider_id="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
    )
    rid = "dr-hard-deadline"
    driver.runs[rid] = {"state": "running"}
    driver._request_deadlines[rid] = time.monotonic() + 0.08
    started = time.monotonic()
    with pytest.raises(ProviderDriverFailure, match="wall-clock budget exhausted"):
        driver._post_json(
            rid,
            "https://example.invalid/v1/chat/completions",
            {"model": "test/model", "messages": []},
            {},
        )
    assert time.monotonic() - started < 0.8
    assert driver.runs[rid]["state"] == "failed"
    assert driver.runs[rid]["dispatchBoundary"] == "request_timeout"


class _SlowDripProviderServer(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        import time
        self.rfile.read(int(self.headers["Content-Length"]))
        payload = json.dumps({
            "choices": [{"message": {"content": "TOO_LATE"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        for byte in payload:
            try:
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                break
            time.sleep(0.01)

    def log_message(self, format, *args):  # noqa: N802,A002
        return


def test_provider_real_http_slow_drip_cannot_extend_wall_clock_budget(tmp_path: Path):
    import time
    import pytest

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SlowDripProviderServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        driver = ProviderDriver(
            str(tmp_path / "staging-slow-drip"),
            provider_id="openrouter",
            model="test/model",
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
        )
        started = time.monotonic()
        with pytest.raises(ProviderDriverFailure, match="wall-clock budget exhausted"):
            asyncio.run(driver.submit({
                "driverRunId": "dr-slow-drip-deadline",
                "missionId": "m-slow-drip-deadline",
                "taskId": "t-slow-drip-deadline",
                "contextSlice": {"budgets": {"maxSeconds": 0.12, "maxTokens": 32000}},
                "submittedAt": "2026-10-07T00:00:00Z",
            }))
        assert time.monotonic() - started < 0.8
        assert driver.runs["dr-slow-drip-deadline"]["dispatchBoundary"] == "request_timeout"
    finally:
        server.shutdown()
        server.server_close()


def test_strict_44_vessel_charter_reserves_geometry_aware_final_output(tmp_path: Path):
    driver = ProviderDriver(
        str(tmp_path / "staging-charter-reserve"),
        provider_id="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        cohort_spec={
            "cohortId": "mimo26pro",
            "vesselsPerCohort": 44,
            "configurationId": "high",
            "vesselCharterPolicy": {
                "schemaVersion": "2.0.0",
                "candidateMultiplier": 3,
                "candidateMaxWords": 48,
                "strictLedger": True,
            },
        },
    )
    assert driver._charter_minimum_output_tokens() == 19_968
    assert driver._final_answer_reserve_tokens(32_000) == 19_968
    assert driver._final_answer_reserve_tokens(96_000) == 48_000


def test_strict_charter_finalization_prioritizes_physical_ledger(tmp_path: Path, monkeypatch):
    driver = ProviderDriver(
        str(tmp_path / "staging-charter-finalize"),
        provider_id="openrouter",
        model="test/model",
        base_url="https://example.invalid/v1",
        cohort_spec={
            "cohortId": "mimo26pro",
            "vesselsPerCohort": 44,
            "configurationId": "high",
            "vesselCharterPolicy": {
                "schemaVersion": "2.0.0",
                "candidateMultiplier": 3,
                "candidateMaxWords": 48,
                "strictLedger": True,
            },
        },
    )
    rid = "dr-charter-finalize"
    driver.runs[rid] = {"state": "running"}
    seen = {}

    def fake_post(_rid, _url, body, _headers, **kwargs):
        seen["body"] = body
        seen["kwargs"] = kwargs
        return {
            "choices": [{"message": {"content": "CAPT_COHORT_INCOMPLETE"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    monkeypatch.setattr(driver, "_post_json", fake_post)
    driver._openai_finalize_after_tool_budget(
        rid,
        "https://example.invalid/v1/chat/completions",
        {},
        [{"role": "user", "content": "work"}],
        0, 0, 0.0, 0,
        reason="context headroom reserve reached",
        context_budget_tokens=96_000,
    )
    closure = seen["body"]["messages"][-1]["content"]
    assert "CAPT_CANDIDATE" in closure
    assert "CAPT_CHARTER_AUDIT" in closure
    assert "CAPT_VESSEL" in closure
    assert "ledger first" in closure.lower()
    assert seen["body"]["max_tokens"] == 48_000
    assert seen["kwargs"]["reasoning_policy"] == "answer_only"
