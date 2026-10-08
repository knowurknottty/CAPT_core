"""Authenticated native Bot registration without live capability grants."""
from __future__ import annotations

from uuid import uuid4

from tests.capt_runtime.test_desktop_m1 import _start_runtime
from desktop.desktop_runtime_client import RuntimeClient
from capt_runtime.store import EventStore


def _bot(bot_id: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "botId": bot_id, "displayName": "Issue Steward",
        "roleKind": "crew",
        "role": "Review GitHub issue backlog one at a time with evidence gates",
        "modelStrategy": {"primary": "openrouter/deepseek/deepseek-v4.1-flash", "fallbacks": []},
        "cognitionPolicy": {"promotionMode": "governed"},
        "localityPolicy": {"defaultRuntime": "either", "privateData": "local_only"},
        "collaboration": {"mayDelegate": False, "maxSpawnDepth": 0},
        "missionId": None, "authorityTemplateRef": None,
    }


def test_register_bot_via_authenticated_runtime(tmp_path):
    sock, token, ledger = _start_runtime(str(tmp_path))
    c = RuntimeClient(sock, token)
    c.connect()
    try:
        bot_id = "bot-test-" + uuid4().hex[:8]
        manifest = _bot(bot_id)
        receipt = c.command("register_bot", {"bot": manifest}, idempotency_key="create-" + bot_id)
        assert receipt["status"] == "accepted", receipt
        assert receipt["result"]["botId"] == bot_id
        assert receipt["result"]["identityOnly"] is True
        state = c.get_state("bot-" + bot_id)
        assert state["createdBy"]["actorId"] == c.operator_id
        assert state["createdBy"]["kind"] == "human"
        assert state["modelStrategy"]["primary"] == manifest["modelStrategy"]["primary"]
        assert "credentials" not in state
        q = c._query({"op":"bots"})["result"]
        assert any(x["botId"] == bot_id for x in q["bots"])
        assert "register_bot" in c.capabilities()["commandOperations"]
        replay = c.command("register_bot", {"bot": manifest}, idempotency_key="create-" + bot_id)
        assert replay["status"] == "idempotent", replay
        assert sum(x["botId"] == bot_id for x in c._query({"op":"bots"})["result"]["bots"]) == 1
    finally:
        c.disconnect()


def test_register_bot_refuses_actor_spoofing(tmp_path):
    sock, token, ledger = _start_runtime(str(tmp_path))
    c = RuntimeClient(sock, token)
    c.connect()
    try:
        bot_id = "bot-test-" + uuid4().hex[:8]
        manifest = _bot(bot_id)
        manifest["createdBy"] = {"actorId": "fake-root", "kind": "system"}
        response = c.command("register_bot", {"bot": manifest})
        assert response["status"] == "rejected", response
        assert all(x["botId"] != bot_id for x in c._query({"op": "bots"})["result"]["bots"])
    finally:
        c.disconnect()
