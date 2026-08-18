"""CAPT-UPG-009 authoritative promotion lifecycle tests."""

from __future__ import annotations

import hashlib

import pytest

from capt_runtime import commands
from capt_runtime.aggregates.artifact_promotion import ArtifactPromotionAggregate
from capt_runtime.errors import AuthorityViolation
from capt_runtime.governed_service import GovernedRuntimeService
from capt_runtime.replay import full_replay
from capt_runtime.store import EventStore


def _meta(actor, kind, step):
    return commands.command(
        command_id="cmd-promote-" + step,
        idempotency_key="idem-promote-" + step,
        operation_fingerprint=commands.fingerprint("promotion-" + step, {"step": step}),
        correlation_id="corr-promote",
        actor_id=actor,
        actor_kind=kind,
        issued_at="2026-08-18T00:00:%02dZ" % (int(step.split("-")[0]) if step[0].isdigit() else 0),
    )


def _claim(claim_id):
    return {
        "schemaVersion": "1.0.0",
        "claimId": claim_id,
        "missionId": "m-1",
        "kind": "observation",
        "statement": "candidate artifact has expected bytes",
        "evidenceIds": [],
        "promotionState": "proposed",
        "proposedBy": {"actorId": "exec", "kind": "execution_plane"},
        "proposedAt": "2026-08-18T00:00:00Z",
    }


def _evidence(evidence_id, content_digest, artifact_path):
    return {
        "schemaVersion": "1.0.0",
        "evidenceId": evidence_id,
        "missionId": "m-1",
        "evidence": {
            "kind": "artifact_hash",
            "artifactPath": artifact_path,
            "artifactDigest": content_digest,
        },
        "collectedBy": {"actorId": "exec", "kind": "execution_plane"},
        "collectedAt": "2026-08-18T00:00:02Z",
        "trust": "capt_authoritative",
    }


def _verification(verification_id, claim_id, evidence_id, kind="verified"):
    if kind == "verified":
        status = {"kind": "verified", "supportingEvidenceIds": [evidence_id]}
    else:
        status = {"kind": kind, "reason": "superseded by later review"}
    return {
        "schemaVersion": "1.0.0",
        "verificationId": verification_id,
        "claimId": claim_id,
        "strategy": "artifact_hashing",
        "status": status,
        "verifiedBy": {"actorId": "ver", "kind": "verification_plane"},
        "verifiedAt": "2026-08-18T00:00:03Z",
    }


def _seed_verified_claim(svc, source):
    payload = source.read_bytes()
    content_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    svc.propose_claim(_claim("cl-1"), _meta("exec", "execution_plane", "1-claim"))
    svc.record_evidence(
        "cl-1", _evidence("ev-1", content_digest, str(source)),
        _meta("exec", "execution_plane", "2-evidence"),
    )
    svc.record_verification(
        _verification("ver-1", "cl-1", "ev-1"),
        _meta("ver", "verification_plane", "3-verify"),
    )
    return content_digest


def _promotion_spec(source, destination, content_digest):
    return {
        "promotionId": "p-1",
        "candidateId": "cand-1",
        "workspaceId": "ws-1",
        "sourcePath": str(source),
        "destinationPath": str(destination),
        "contentDigest": content_digest,
        "claimId": "cl-1",
        "verificationId": "ver-1",
        "evidenceId": "ev-1",
        "preparedAt": "2026-08-18T00:00:04Z",
    }


def test_verified_candidate_promotes_without_claimguard_becoming_filesystem_authority(tmp_path):
    source = tmp_path / "staging" / "candidate.bin"
    source.parent.mkdir()
    source.write_bytes(b"verified artifact bytes")
    destination = tmp_path / "canonical" / "artifact.bin"

    store = EventStore(str(tmp_path / "runtime.db"))
    svc = GovernedRuntimeService(store)
    content_digest = _seed_verified_claim(svc, source)

    svc.prepare_artifact_promotion(
        _promotion_spec(source, destination, content_digest),
        _meta("exec", "execution_plane", "4-prepare"),
    )
    prepared = store.require_state("artifact_promotion-p-1")
    assert prepared["state"] == "prepared"
    # ClaimGuard has not accepted this claim. That is intentional: verification
    # and workspace adoption are separate authority domains.
    assert store.require_state("claim-cl-1")["promotionState"] == "proposed"

    svc.authorize_artifact_promotion("p-1", _meta("captain", "human", "5-authorize"))
    authorized = store.require_state("artifact_promotion-p-1")
    assert authorized["state"] == "authorized"
    assert not destination.exists()

    svc.adopt_artifact_promotion("p-1", _meta("exec", "execution_plane", "6-adopt"))
    adopted = store.require_state("artifact_promotion-p-1")
    assert adopted["state"] == "adopted"
    assert destination.read_bytes() == b"verified artifact bytes"
    assert adopted["adoptionReceipt"]["contentDigest"] == content_digest

    replay = full_replay(store)
    assert replay.aggregates["artifact_promotion-p-1"] == adopted
    store.close()


def test_stale_verification_cannot_authorize_promotion(tmp_path):
    source = tmp_path / "candidate.bin"
    source.write_bytes(b"v1 bytes")
    destination = tmp_path / "canonical.bin"
    store = EventStore(str(tmp_path / "runtime.db"))
    svc = GovernedRuntimeService(store)
    content_digest = _seed_verified_claim(svc, source)
    svc.prepare_artifact_promotion(
        _promotion_spec(source, destination, content_digest),
        _meta("exec", "execution_plane", "4-prepare"),
    )

    svc.record_verification(
        _verification("ver-2", "cl-1", "ev-1", kind="inconclusive"),
        _meta("ver", "verification_plane", "5-reverify"),
    )
    with pytest.raises(AuthorityViolation, match="no longer the claim's current verification"):
        svc.authorize_artifact_promotion(
            "p-1", _meta("captain", "human", "6-authorize")
        )
    assert not destination.exists()
    store.close()


def test_source_mutation_after_verification_fails_closed(tmp_path):
    source = tmp_path / "candidate.bin"
    source.write_bytes(b"verified")
    destination = tmp_path / "canonical.bin"
    store = EventStore(str(tmp_path / "runtime.db"))
    svc = GovernedRuntimeService(store)
    content_digest = _seed_verified_claim(svc, source)
    svc.prepare_artifact_promotion(
        _promotion_spec(source, destination, content_digest),
        _meta("exec", "execution_plane", "4-prepare"),
    )
    source.write_bytes(b"tampered")
    with pytest.raises(Exception, match="staged artifact changed"):
        svc.authorize_artifact_promotion(
            "p-1", _meta("captain", "human", "5-authorize")
        )
    assert not destination.exists()
    store.close()


def test_adopt_exact_retry_is_idempotent_and_destination_is_bound(tmp_path):
    source = tmp_path / "candidate.bin"
    source.write_bytes(b"verified")
    destination = tmp_path / "canonical.bin"
    store = EventStore(str(tmp_path / "runtime.db"))
    svc = GovernedRuntimeService(store)
    content_digest = _seed_verified_claim(svc, source)
    svc.prepare_artifact_promotion(
        _promotion_spec(source, destination, content_digest),
        _meta("exec", "execution_plane", "4-prepare"),
    )
    svc.authorize_artifact_promotion("p-1", _meta("captain", "human", "5-authorize"))
    first_meta = _meta("exec", "execution_plane", "6-adopt")
    first = svc.adopt_artifact_promotion("p-1", first_meta)
    second = svc.adopt_artifact_promotion("p-1", first_meta)
    assert first["promotion"]["destinationPath"] == str(destination.resolve())
    assert second["status"] == "idempotent"
    assert destination.read_bytes() == b"verified"
    store.close()


def test_aggregate_rejects_destination_substitution_receipt():
    state = ArtifactPromotionAggregate.prepare({
        "promotionId": "p",
        "candidateId": "c",
        "workspaceId": "w",
        "sourcePath": "/tmp/source",
        "destinationPath": "/tmp/authorized",
        "contentDigest": "sha256:" + "a" * 64,
        "claimId": "cl",
        "verificationId": "v",
        "evidenceId": "e",
        "preparedAt": "2026-08-18T00:00:00Z",
    })
    state = ArtifactPromotionAggregate.authorize(state, "captain", "2026-08-18T00:01:00Z")
    with pytest.raises(AuthorityViolation, match="destination"):
        ArtifactPromotionAggregate.adopt(
            state,
            {
                "destinationPath": "/tmp/substituted",
                "contentDigest": state["contentDigest"],
            },
            "2026-08-18T00:02:00Z",
        )
