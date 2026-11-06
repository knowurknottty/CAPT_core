from __future__ import annotations

import pytest

from capt_runtime.node.identity import ControllerIdentity, NodeIdentity
from capt_runtime.node.pairing import PairingRecord, PairingState, pairing_short_code


def test_private_key_never_appears_in_public_identity():
    node = NodeIdentity.generate("node-1", "captain-mbp")
    public = node.public_dict()
    assert public["nodeId"] == "node-1"
    assert "private" not in " ".join(public).lower()
    assert node.private_key_bytes() not in repr(public).encode()


def test_pairing_grants_authentication_not_execution_authority():
    node = NodeIdentity.generate("node-1", "captain-mbp")
    controller = ControllerIdentity.generate("controller-1", "capt-runtime")
    record = PairingRecord.pending(node, controller)
    assert record.state is PairingState.PENDING
    assert record.execution_authority is False
    assert pairing_short_code(node.public_key_bytes(), controller.public_key_bytes()) == record.short_code
    active = record.activate(record.short_code)
    assert active.state is PairingState.ACTIVE
    assert active.execution_authority is False


def test_revoked_pairing_cannot_be_reactivated():
    node = NodeIdentity.generate("node-1", "captain-mbp")
    controller = ControllerIdentity.generate("controller-1", "capt-runtime")
    record = PairingRecord.pending(node, controller).activate(
        pairing_short_code(node.public_key_bytes(), controller.public_key_bytes())
    ).revoke("human_revoked")
    assert record.state is PairingState.REVOKED
    with pytest.raises(ValueError, match="pairing_terminal"):
        record.activate(record.short_code)


def test_identity_private_round_trip_preserves_public_keys():
    node = NodeIdentity.generate("node-roundtrip", "captain-mbp")
    restored_node = NodeIdentity.from_private_bytes(
        "node-roundtrip", "captain-mbp", node.private_key_bytes()
    )
    assert restored_node.public_key_bytes() == node.public_key_bytes()

    controller = ControllerIdentity.generate("controller-roundtrip", "capt-runtime")
    restored_controller = ControllerIdentity.from_private_bytes(
        "controller-roundtrip", "capt-runtime", controller.private_key_bytes()
    )
    assert restored_controller.public_key_bytes() == controller.public_key_bytes()
