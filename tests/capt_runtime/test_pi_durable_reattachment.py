"""PI admission and status are durable, scoped and never retry external effects."""
import threading
import time
import uuid

import pytest

from capt_runtime.store import EventStore
from capt_runtime.services import RuntimeService
from capt_runtime.prompt_proposals import durable_pi_compile, pi_attempt_status
from capt_runtime.prompt_compiler import PromptCompiler
from desktop.m1_command_service import RuntimeCommandService
from tests.capt_runtime.test_prompt_proposal_commands import _cmd, _compile_payload


class BlockedCompiler:
    def __init__(self, failure=False):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        self.failure = failure

    def compile(self, request):
        self.calls += 1
        self.entered.set()
        assert self.release.wait(5)
        if self.failure:
            raise OSError("simulated loss after paid provider dispatch")
        return PromptCompiler().compile(request)


def _setup(tmp_path):
    ledger = str(tmp_path / "ledger.db")
    store = EventStore(ledger)
    root = tmp_path / "repo"
    root.mkdir()
    return store, root, ledger


def _command(root, proposal_id="pp-test-reattach-12345678"):
    return _cmd("compile_prompt_proposal", {
        **_compile_payload(str(root)), "proposalId": proposal_id
    }, proposal_id)


def test_in_flight_socket_reader_can_observe_without_second_dispatch(tmp_path):
    store, root, _ = _setup(tmp_path)
    block = BlockedCompiler()
    live = set()
    relay = RuntimeCommandService(store, "operator", "session",
                                  runtime_service=RuntimeService(store), prompt_compiler=block)
    relay.pi_active_attempts = live
    cmd = _command(root)
    output = []
    t = threading.Thread(target=lambda: output.append(relay.execute(cmd)))
    t.start()
    assert block.entered.wait(4)
    assert pi_attempt_status(store, cmd["payload"]["proposalId"], live)["status"] == "in_progress"
    duplicate = relay.execute(cmd)
    assert duplicate["status"] == "in_progress"
    assert block.calls == 1
    block.release.set()
    t.join(5)
    assert output[0]["status"] == "accepted"
    assert block.calls == 1
    final = pi_attempt_status(store, cmd["payload"]["proposalId"], live)
    assert final["status"] == "completed"
    assert final["proposal"]["compilationStatus"] == "compiler_unavailable"
    assert final["safeToAutoRetry"] is False
    again = relay.execute(cmd)
    assert again["status"] == "idempotent"
    assert block.calls == 1
    store.close()


def test_lost_reply_after_admission_is_indeterminate_on_restart(tmp_path):
    store, root, ledger = _setup(tmp_path)
    block = BlockedCompiler(failure=True)
    block.release.set()
    cmd = _command(root, "pp-failed-reattach-12345678")
    relay = RuntimeCommandService(store, "operator", "session",
                                  runtime_service=RuntimeService(store), prompt_compiler=block)
    assert relay.execute(cmd)["status"] == "rejected"
    assert block.calls == 1
    store.close()
    restarted = EventStore(ledger)
    status = pi_attempt_status(restarted, cmd["payload"]["proposalId"])
    assert status["status"] == "indeterminate"
    assert status["safeToAutoRetry"] is False
    relay2 = RuntimeCommandService(restarted, "operator", "session",
                                  runtime_service=RuntimeService(restarted), prompt_compiler=block)
    assert relay2.execute(cmd)["status"] == "in_progress"
    assert block.calls == 1
    restarted.close()


def test_distinct_payload_under_same_id_is_refused_without_dispatch(tmp_path):
    store, root, _ = _setup(tmp_path)
    relay = RuntimeCommandService(store, "operator", "session",
                                  runtime_service=RuntimeService(store),
                                  prompt_compiler=PromptCompiler())
    cmd = _command(root, "pp-conflict-reattach-12345678")
    assert relay.execute(cmd)["status"] == "accepted"
    tampered = _command(root, "pp-conflict-reattach-12345678")
    tampered["payload"]["originalPrompt"] = "different secret payload"
    assert relay.execute(tampered)["status"] == "rejected"
    assert pi_attempt_status(store, "pp-conflict-reattach-12345678")["status"] == "completed"
    store.close()


def test_unknown_id_does_not_imply_safe_retry(tmp_path):
    store, root, _ = _setup(tmp_path)
    unknown = pi_attempt_status(store, "pp-unknown-12345678")
    assert unknown["status"] == "not_found"
    assert unknown["safeToAutoRetry"] is False
    with pytest.raises(ValueError):
        pi_attempt_status(store, "../bad")
    store.close()


def test_authenticated_socket_query_recovers_completed_attempt_without_write(tmp_path):
    from desktop.capt_runtime_service import serve as serve_runtime
    from desktop.desktop_runtime_client import RuntimeClient

    import os
    import tempfile
    temp = tempfile.mkdtemp(prefix="/tmp/piar-")
    sock = os.path.join(temp, "r.sock")
    token = os.path.join(temp, "token")
    ledger = os.path.join(temp, "rt.db")
    thread = threading.Thread(
        target=serve_runtime, args=(ledger, sock, token, False), daemon=True
    )
    thread.start()
    for _ in range(120):
        if os.path.exists(sock) and os.path.exists(token):
            break
        time.sleep(.05)
    client = RuntimeClient(sock, token)
    client.connect()
    try:
        proposal_id = "pp-socket-reattach-12345678"
        result = client.command("compile_prompt_proposal", {
            "proposalId": proposal_id,
            "originalPrompt": "Review this simulated repository without network.",
            "targetRoot": str(tmp_path),
            "promptIntelligence": "OFF",
            "provider": "none",
            "model": "none",
            "remoteCompilationAuthorized": False,
        }, idempotency_key="socket-reattach-12345678")
        assert result["status"] == "accepted", result
        head = client._query({"op": "identity"})["result"]["headSequence"]
        response = client._query({"op": "pi_request_status", "proposalId": proposal_id})
        assert response["ok"] is True, response
        assert response["result"]["status"] == "completed"
        assert response["result"]["proposal"]["originalPrompt"] == (
            "Review this simulated repository without network.")
        assert response["result"]["safeToAutoRetry"] is False
        repeated = client._query({"op": "pi_request_status", "proposalId": proposal_id})
        assert repeated == response
        assert client._query({"op": "identity"})["result"]["headSequence"] == head
        assert "pi_request_status" in client.capabilities()["queryOperations"]
    finally:
        client.disconnect()
