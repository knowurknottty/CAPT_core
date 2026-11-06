from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from capt_runtime.node.authority import sign_capability, verify_capability_authority
from capt_runtime.node.identity import CapabilityAuthorityIdentity, ControllerIdentity
from capt_runtime.node.types import OperationCapability

NOW = datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)


def _capability():
    return OperationCapability(
        capability_id="cap-1",
        bot_id="bot-1",
        mission_id="m-1",
        task_id="t-1",
        controller_id="controller-1",
        node_id="node-1",
        permitted_operations=frozenset({"shell.exec"}),
        filesystem_roots=("/tmp/capt",),
        issued_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )


def test_capability_requires_distinct_authority_signature():
    authority = CapabilityAuthorityIdentity.generate("authority-1")
    signed = sign_capability(_capability(), authority)
    assert signed.authority_issuer_id == "authority-1"
    assert signed.authority_signature
    verify_capability_authority(signed, {"authority-1": authority.public_key_bytes()})


def test_unsigned_capability_is_not_authorized_by_controller_pairing():
    controller = ControllerIdentity.generate("controller-1", "transport-only")
    with pytest.raises(PermissionError, match="capability_authority_signature_missing"):
        verify_capability_authority(_capability(), {"controller-1": controller.public_key_bytes()})
