from types import SimpleNamespace

import capt_cli
import capt_runtime.cli_ramp as cli_ramp
import desktop.desktop_runtime_client as runtime_client


class FakeRuntimeClient:
    instances = []

    def __init__(self, sock, token):
        self.sock = sock
        self.token = token
        self.calls = []
        self.__class__.instances.append(self)

    def connect(self):
        return {"integrity": "ok"}

    def disconnect(self):
        pass

    def command(self, op, payload, key):
        self.calls.append((op, payload, key))
        if op == "request_model_prompt_approval":
            return {
                "status": "accepted",
                "result": {
                    "requestId": "approval-1",
                    "missionId": "mission-1",
                    "taskId": "task-1",
                    "driverRunId": "run-1",
                },
            }
        if op == "submit_approval_decision":
            return {"status": "accepted", "result": {"state": "approved"}}
        if op == "run_approved_hermes_inspection":
            return {"status": "accepted", "result": {"driverRunId": "run-1"}}
        raise AssertionError(op)


def _args(**overrides):
    values = {
        "provider": "openrouter",
        "model": "stealth/space-bunny-alpha",
        "prompt": "review this exact prompt",
        "reasoning_effort": "xhigh",
        "approve_exact_prompt": False,
        "state_dir": None,
        "idempotency_key": "cli-test-run",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _wire(monkeypatch, tmp_path):
    sock = tmp_path / "runtime.sock"
    token = tmp_path / "runtime.token"
    sock.touch()
    token.write_text("opaque-test-token")
    monkeypatch.setattr(
        cli_ramp,
        "default_paths",
        lambda: {
            "state_dir": tmp_path,
            "ledger": tmp_path / "runtime.db",
            "sock": sock,
            "token": token,
            "pid": tmp_path / "runtime.pid",
        },
    )
    monkeypatch.setattr(cli_ramp, "is_running", lambda _sock: True)
    monkeypatch.setattr(runtime_client, "RuntimeClient", FakeRuntimeClient)
    FakeRuntimeClient.instances.clear()


def test_run_without_exact_approval_creates_request_only(monkeypatch, tmp_path, capsys):
    _wire(monkeypatch, tmp_path)

    rc = capt_cli._cmd_run(_args(), True)

    assert rc == 2
    out = capsys.readouterr().out
    assert '"status": "approval_required"' in out
    calls = FakeRuntimeClient.instances[-1].calls
    assert [call[0] for call in calls] == ["request_model_prompt_approval"]
    payload = calls[0][1]
    assert payload["reasoningEffort"] == "xhigh"
    assert payload["authorityProfile"]["fileMutationAllowed"] is False
    assert payload["authorityProfile"]["shellAccessAllowed"] is False
    assert payload["authorityProfile"]["providerNetworkPolicy"] == "remote_allowed"
    assert calls[0][2] == "cli-test-run:approval-request"


def test_run_with_exact_approval_binds_and_dispatches(monkeypatch, tmp_path, capsys):
    _wire(monkeypatch, tmp_path)

    rc = capt_cli._cmd_run(_args(approve_exact_prompt=True), True)

    assert rc == 0
    capsys.readouterr()
    calls = FakeRuntimeClient.instances[-1].calls
    assert [call[0] for call in calls] == [
        "request_model_prompt_approval",
        "submit_approval_decision",
        "run_approved_hermes_inspection",
    ]
    assert calls[1][1]["decision"] == "approve"
    assert calls[1][2] == "cli-test-run:approval-decision"
    run_payload = calls[2][1]
    assert run_payload["approvalRequestId"] == "approval-1"
    assert run_payload["missionId"] == "mission-1"
    assert run_payload["taskId"] == "task-1"
    assert run_payload["driverRunId"] == "run-1"
    assert run_payload["reasoningEffort"] == "xhigh"
    assert calls[2][2] == "cli-test-run:dispatch"
