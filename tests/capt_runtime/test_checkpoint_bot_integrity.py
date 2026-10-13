"""Checkpoint coverage for durable Bot and later aggregate kinds."""

from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.aggregates import ALL_AGGREGATES
from capt_runtime.checkpoint import (
    _KIND_TO_FIELD,
    create_checkpoint,
    manifest_integrity_digest,
    verify_checkpoint,
)
from capt_runtime.errors import IntegrityViolation
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.replay import checkpoint_replay, full_replay, replay_equivalent
from capt_runtime.store import EventStore

NOW = "2026-10-13T01:08:19Z"
ZERO = "sha256:" + "0" * 64


def _register_bot(store: EventStore) -> None:
    manifest = {
        "schemaVersion": "1.0.0", "botId": "capt-checkpoint-bot",
        "displayName": "Checkpoint bot", "roleKind": "crew",
        "role": "research", "missionId": None,
        "modelStrategy": {"primary": None, "fallbacks": []},
        "cognitionPolicy": {"promotionMode": "governed"},
        "localityPolicy": {"defaultRuntime": "local", "privateData": "local_only"},
        "collaboration": {"mayDelegate": False, "maxSpawnDepth": 0},
        "authorityTemplateRef": None,
        "createdBy": {"actorId": "operator", "kind": "human", "displayName": None},
        "createdAt": NOW,
    }
    metadata = commands.command(
        command_id="cmd-checkpoint-bot",
        idempotency_key="idem-checkpoint-bot",
        operation_fingerprint=commands.fingerprint(
            "register_bot", {"botId": manifest["botId"]}
        ),
        correlation_id="corr-checkpoint-bot",
        actor_id="operator", actor_kind="human", issued_at=NOW,
    )
    GovernedRuntimeService(store).register_bot(manifest, metadata)


def test_checkpoint_replay_captures_bot_without_weaking_integrity(tmp_path):
    store = EventStore(str(tmp_path / "bot-ledger.db"))
    _register_bot(store)
    manifest = create_checkpoint(store, "cp-bot", NOW, ZERO)
    assert manifest["botVersions"] == [
        {"streamId": "bot-capt-checkpoint-bot", "version": 1}
    ]
    verify_checkpoint(manifest)
    assert replay_equivalent(full_replay(store), checkpoint_replay(store, manifest))
    saved = store.load_checkpoint("cp-bot")
    assert saved["botVersions"] == manifest["botVersions"]

    # The new optional field is integrity-bound and actively replay-checked.
    tampered = dict(manifest)
    tampered["botVersions"] = [
        {"streamId": "bot-capt-checkpoint-bot", "version": 2}
    ]
    with pytest.raises(IntegrityViolation):
        verify_checkpoint(tampered)
    tampered["integrityDigest"] = manifest_integrity_digest(tampered)
    verify_checkpoint(tampered)
    with pytest.raises(IntegrityViolation, match="checkpoint stream .* version mismatch"):
        checkpoint_replay(store, tampered)
    store.close()


def test_checkpoint_kinds_cover_all_implemented_aggregates():
    assert set(_KIND_TO_FIELD) == {aggregate.KIND for aggregate in ALL_AGGREGATES}
    assert len(set(_KIND_TO_FIELD.values())) == len(_KIND_TO_FIELD)


def test_preexisting_checkpoint_without_new_optional_field_remains_compatible(tmp_path):
    store = EventStore(str(tmp_path / "old-ledger.db"))
    manifest = create_checkpoint(store, "cp-before-bot", NOW, ZERO)
    del manifest["botVersions"]
    manifest["integrityDigest"] = manifest_integrity_digest(manifest)
    verify_checkpoint(manifest)
    assert replay_equivalent(full_replay(store), checkpoint_replay(store, manifest))
    store.close()
