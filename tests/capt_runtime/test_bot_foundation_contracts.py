from __future__ import annotations

from capt_contracts import validate


def _actor(kind: str = "human"):
    return {"actorId": "captain", "kind": kind, "displayName": None}


def test_bot_manifest_contract_exists_and_rejects_live_credentials():
    manifest = {
        "schemaVersion": "1.0.0", "botId": "researcher", "displayName": "Researcher",
        "roleKind": "crew", "role": "research", "missionId": None,
        "modelStrategy": {"primary": "openrouter/glm", "fallbacks": ["local/qwen"]},
        "cognitionPolicy": {"promotionMode": "governed"},
        "localityPolicy": {"defaultRuntime": "either", "privateData": "local_only"},
        "collaboration": {"mayDelegate": True, "maxSpawnDepth": 2},
        "authorityTemplateRef": "policy.researcher", "createdBy": _actor(),
        "createdAt": "2026-09-08T16:00:00Z",
    }
    assert validate("BotManifest", manifest) == []
    manifest["apiKey"] = "must-never-live-here"
    assert validate("BotManifest", manifest)


def test_new_bot_event_is_closed_contract_member():
    payload = {"eventType": "BotRegistered", "bot": {
        "schemaVersion": "1.0.0", "botId": "researcher", "displayName": "Researcher",
        "roleKind": "crew", "role": "research", "missionId": None,
        "modelStrategy": {"primary": None, "fallbacks": []},
        "cognitionPolicy": {"promotionMode": "locked"},
        "localityPolicy": {"defaultRuntime": "local", "privateData": "local_only"},
        "collaboration": {"mayDelegate": False, "maxSpawnDepth": 0},
        "authorityTemplateRef": None, "createdBy": _actor(),
        "createdAt": "2026-09-08T16:00:00Z",
    }}
    envelope = {"schemaVersion": "1.0.0", "eventId": "ev-bot-1", "streamId": "bot-researcher",
        "streamVersion": 1, "globalSequence": 1, "eventType": "BotRegistered",
        "occurredAt": "2026-09-08T16:00:00Z", "actor": _actor(), "missionId": None,
        "taskId": None, "claimId": None, "correlationId": "corr-bot-1",
        "causationId": "cmd-bot-1", "payload": payload,
        "payloadDigest": "sha256:" + "0" * 64}
    assert validate("EventEnvelope", envelope) == []