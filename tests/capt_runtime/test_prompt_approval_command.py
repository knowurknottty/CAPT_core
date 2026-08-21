from __future__ import annotations

import time

from desktop.m1_command_service import RuntimeCommandService
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def _command(op, payload, command_id="cmd-prompt-approval"):
    return {
        "commandId": command_id,
        "operatorId": "operator",
        "sessionId": "session",
        "schemaVersion": "1.0.0",
        "correlationId": "corr-prompt-approval",
        "idempotencyKey": command_id + "-idem",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "op": op,
        "payload": payload,
    }


def test_command_relay_creates_then_decides_exact_prompt_approval(tmp_path):
    store = EventStore(str(tmp_path / "ledger.db"))
    relay = RuntimeCommandService(
        store,
        "operator",
        "session",
        runtime_service=RuntimeService(store),
    )
    intent = {
        "objective": "Inspect the repository and report concrete findings.",
        "targetRoot": "/tmp/project",
        "provider": "ollama",
        "model": "qwen",
        "responseMode": "SPOCK",
        "promptEnhancement": "OFF",
    }

    receipt = relay.execute(_command("request_model_prompt_approval", intent))
    assert receipt["status"] == "accepted"
    planned = receipt["result"]
    assert planned["requestId"]
    assert planned["missionId"]
    assert planned["taskId"]
    assert planned["driverRunId"]
    assert planned["promptAssemblyDigest"].startswith("sha256:")

    decision = relay.execute(
        _command(
            "submit_approval_decision",
            {"requestId": planned["requestId"], "decision": "approve"},
            command_id="cmd-prompt-decision",
        )
    )
    assert decision["status"] == "accepted"
    state = store.require_state("human_approval-" + planned["requestId"])
    assert state["state"] == "approved"
    assert state["promptAssemblyDigest"] == planned["promptAssemblyDigest"]
    store.close()
