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
        assert _Server.seen["body"]["max_tokens"] == 16_384
        assert _Server.seen["auth"] == "Bearer " + secret
        assert out["state"] == "completed"
        assert out["dispatchBoundary"] == "result_persisted"
        assert out["transportCancellationSupported"] is False
        assert out["diagnostics"]["provider"] == "openrouter"
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
            "options": {"num_predict": 16_384},
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
        assert _ContextHeadroomServer.calls[0]["max_tokens"] == 10666
        assert _ContextHeadroomServer.calls[-1]["max_tokens"] == 10666
    finally:
        server.shutdown()
        server.server_close()
