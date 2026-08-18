"""Governed commands implemented at UPG-011 must be discoverable to clients."""
from capt_runtime.store import EventStore
from desktop.capt_runtime_service import RuntimeQueryService


def test_runtime_capabilities_advertise_governed_steering_and_revocation():
    store = EventStore(":memory:")
    try:
        result = RuntimeQueryService(store).handle({"op": "capabilities"})
        assert result["ok"] is True
        ops = set(result["result"]["commandOperations"])
        assert "steer_deliberation" in ops
        assert "revoke_capability" in ops
    finally:
        store.close()
