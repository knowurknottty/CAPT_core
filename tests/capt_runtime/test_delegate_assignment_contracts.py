from __future__ import annotations

from capt_contracts import validate

NOW = "2026-09-08T17:00:00Z"
LATER = "2026-09-08T18:00:00Z"


def _actor():
    return {"actorId": "researcher", "kind": "cognitive_plane", "displayName": None}


def _assignment():
    return {"schemaVersion": "1.0.0", "assignmentId": "da-1",
        "parentBotId": "researcher", "delegateBotId": "delegate-1",
        "missionId": "m1", "taskId": None, "depth": 1, "state": "active",
        "createdAt": NOW, "expiresAt": LATER, "createdBy": _actor(),
        "lastTransitionAt": NOW, "transitionReason": None}


def test_delegate_assignment_contract_exists():
    assert validate("DelegateAssignment", _assignment()) == []


def test_delegate_event_is_closed_contract_member():
    payload = {"eventType": "DelegateAssigned", "assignment": _assignment()}
    envelope = {"schemaVersion": "1.0.0", "eventId": "ev-da-1",
        "streamId": "delegate_assignment-da-1", "streamVersion": 1,
        "globalSequence": 1, "eventType": "DelegateAssigned", "occurredAt": NOW,
        "actor": _actor(), "missionId": "m1", "taskId": None, "claimId": None,
        "correlationId": "corr-da-1", "causationId": "cmd-da-1",
        "payload": payload, "payloadDigest": "sha256:" + "0" * 64}
    assert validate("EventEnvelope", envelope) == []
