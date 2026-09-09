"""Conformance tests: claim integrity and ClaimGuard authority (spec 12.2)."""

from __future__ import annotations

import pytest

from capt_runtime import commands
from capt_runtime.aggregates import ClaimAggregate
from capt_runtime.errors import AuthorityViolation
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore


def _svc():
    return RuntimeService(EventStore(":memory:"))


def _verification(verification_id, claim_id, status_kind, supporting_evidence=None):
    if status_kind == "verified":
        status = {"kind": "verified", "supportingEvidenceIds": supporting_evidence or []}
    elif status_kind == "observed_unverified":
        status = {"kind": "observed_unverified", "reason": "not yet independently verified"}
    elif status_kind == "inference":
        status = {"kind": "inference", "basis": "model inference"}
    elif status_kind == "contradicted":
        status = {"kind": "contradicted", "contradictingEvidenceIds": supporting_evidence or []}
    elif status_kind == "inconclusive":
        status = {"kind": "inconclusive", "reason": "could not determine"}
    else:  # not_tested
        status = {"kind": "not_tested"}
    return {
        "schemaVersion": "1.0.0",
        "verificationId": verification_id,
        "claimId": claim_id,
        "strategy": "artifact_hashing",
        "status": status,
        "verifiedBy": {"actorId": "ver", "kind": "verification_plane"},
        "verifiedAt": "2026-08-02T00:05:00Z",
    }


def _evidence(evidence_id, claim_id="c1", mission_id="m1"):
    return {
        "schemaVersion": "1.0.0",
        "evidenceId": evidence_id,
        "missionId": mission_id,
        "evidence": {
            "kind": "artifact_hash",
            "artifactPath": "/tmp/artifact",
            "artifactDigest": "sha256:" + "a" * 64,
        },
        "collectedBy": {"actorId": "exec", "kind": "execution_plane"},
        "collectedAt": "2026-08-02T00:04:00Z",
        "trust": "capt_authoritative",
    }


def _decision(claim_id, verdict, decided_by_kind="claim_authority", verification_id=None,
              qualification=None):
    return {
        "schemaVersion": "1.0.0",
        "decisionId": "dec-" + claim_id,
        "claimId": claim_id,
        "verdict": verdict,
        "rationale": "m0a proof",
        "decidedBy": {"actorId": "cg", "kind": decided_by_kind},
        "decidedAt": "2026-08-02T00:10:00Z",
        "verificationId": verification_id,
        "qualification": qualification,
    }


def _claim(claim_id, kind, evidence_ids, statement="done"):
    return {
        "schemaVersion": "1.0.0",
        "claimId": claim_id,
        "missionId": "m1",
        "kind": kind,
        "statement": statement,
        "evidenceIds": evidence_ids,
        "promotionState": "proposed",
        "proposedBy": {"actorId": "exec", "kind": "execution_plane"},
        "proposedAt": "2026-08-02T00:00:00Z",
    }


def _meta(actor_id, actor_kind, step):
    return commands.command(
        command_id="cmd-" + step, idempotency_key="idem-" + step,
        operation_fingerprint=commands.fingerprint("claim-" + step, {"x": step}),
        correlation_id="c", actor_id=actor_id, actor_kind=actor_kind,
        issued_at="2026-08-02T00:00:00Z",
    )


def test_unverified_completion_rejected():
    """A completion claim cannot be accepted without verified status."""
    svc = _svc()
    claim = _claim("c1", "completion", ["e1"])
    svc.propose_claim(claim, _meta("exec", "execution_plane", "1"))
    with pytest.raises(AuthorityViolation):
        svc.decide_claim(
            _decision("c1", "accept"),
            _meta("cg", "claim_authority", "2"),
        )


def test_verified_completion_accepted():
    svc = _svc()
    claim = _claim("c1", "completion", ["e1"])
    svc.propose_claim(claim, _meta("exec", "execution_plane", "1"))
    svc.record_evidence("c1", _evidence("e1"),
                        _meta("exec", "execution_plane", "2"))
    svc.record_verification(
        _verification("v1", "c1", "verified", ["e1"]),
        _meta("ver", "verification_plane", "3"),
    )
    svc.decide_claim(
        _decision("c1", "accept", verification_id="v1"),
        _meta("cg", "claim_authority", "4"),
    )
    state = svc.store.require_state("claim-c1")
    assert state["promotionState"] == "accepted"


def test_observation_persists_unverified():
    """An observed claim may stay proposed; it is not auto-promoted."""
    svc = _svc()
    claim = _claim("c2", "observation", [])
    svc.propose_claim(claim, _meta("exec", "execution_plane", "1"))
    svc.record_verification(
        _verification("v2", "c2", "observed_unverified"),
        _meta("ver", "verification_plane", "2"),
    )
    state = svc.store.require_state("claim-c2")
    assert state["promotionState"] == "proposed"  # not promoted
    assert state["verificationStatus"] == "observed_unverified"


def test_claimguard_cannot_fabricate_evidence():
    """Verification citing evidence the claim does not hold is rejected."""
    svc = _svc()
    claim = _claim("c3", "completion", [])
    svc.propose_claim(claim, _meta("exec", "execution_plane", "1"))
    with pytest.raises(AuthorityViolation):
        svc.record_verification(
            _verification("v3", "c3", "verified", ["ghost"]),
            _meta("ver", "verification_plane", "2"),
        )


def test_completion_requires_evidence_state():
    svc = _svc()
    claim = _claim("c4", "completion", [])
    svc.propose_claim(claim, _meta("exec", "execution_plane", "1"))
    # A 'verified' verification must cite evidence the claim actually holds.
    # The claim has none, so even recording the verification is refused — the
    # required evidence state is enforced at the verification boundary, not
    # only at claim acceptance.
    with pytest.raises(AuthorityViolation):
        svc.record_verification(
            _verification("v4", "c4", "verified", ["e-ext"]),
            _meta("ver", "verification_plane", "2"),
        )


def test_verified_claim_still_qualifiable():
    """Policy may downgrade a verified completion claim."""
    svc = _svc()
    claim = _claim("c5", "completion", ["e1"])
    svc.propose_claim(claim, _meta("exec", "execution_plane", "1"))
    svc.record_evidence("c5", _evidence("e1", claim_id="c5"),
                        _meta("exec", "execution_plane", "2"))
    svc.record_verification(
        _verification("v5", "c5", "verified", ["e1"]),
        _meta("ver", "verification_plane", "3"),
    )
    svc.decide_claim(
        _decision("c5", "qualify", verification_id="v5",
                  qualification="needs human sign-off"),
        _meta("cg", "claim_authority", "4"),
    )
    assert svc.store.require_state("claim-c5")["promotionState"] == "qualified"


def test_claim_and_evidence_can_be_persisted_as_one_atomic_command():
    svc = _svc()
    claim = _claim("c-atomic", "completion", ["e1", "e2"])
    claim_meta = _meta("exec", "execution_plane", "atomic")
    records = [
        (_evidence("e1", claim_id="c-atomic"), _meta("exec", "execution_plane", "atomic-e1")),
        (_evidence("e2", claim_id="c-atomic"), _meta("exec", "execution_plane", "atomic-e2")),
    ]

    result = svc.propose_claim_with_evidence(claim, records, claim_meta)

    assert len(result["eventIds"]) == 3
    events = svc.store.read_stream("claim-c-atomic")
    assert [event["eventType"] for event in events] == [
        "ClaimCreated", "EvidenceRecorded", "EvidenceRecorded"
    ]
    assert svc.store.require_state("claim-c-atomic")["evidenceIds"] == ["e1", "e2"]


def _awaiting_task(svc, task_id="t-human-review"):
    node = {
        "taskId": task_id, "missionId": "m1", "title": "review provider result",
        "state": "pending", "consequential": True, "capabilityRequirements": [],
        "assignedDriverId": None, "attempt": 0, "maxAttempts": 1,
        "recoveryState": "none",
    }
    svc.create_task(node, _meta("cog", "cognitive_plane", task_id + "-create"))
    svc.transition_task(task_id, "ready", "planned", _meta("exec", "execution_plane", task_id + "-ready"))
    svc.transition_task(task_id, "assigned", "assigned", _meta("exec", "execution_plane", task_id + "-assigned"))
    svc.transition_task(task_id, "running", "running", _meta("exec", "execution_plane", task_id + "-running"))
    svc.transition_task(task_id, "awaiting_verification", "result recorded", _meta("exec", "execution_plane", task_id + "-await"))


def _review_claim(svc, claim_id="c-human-review", task_id="t-human-review"):
    claim = _claim(claim_id, "completion", ["e-result"], statement="Provider response and immutable artifact recorded for independent verification.")
    claim["taskId"] = task_id
    evidence = _evidence("e-result", claim_id=claim_id)
    evidence["taskId"] = task_id
    svc.propose_claim_with_evidence(
        claim,
        [(evidence, _meta("exec", "execution_plane", claim_id + "-evidence"))],
        _meta("exec", "execution_plane", claim_id + "-claim"),
    )


def test_human_review_accept_atomically_promotes_claim_and_succeeds_task():
    svc = _svc()
    _awaiting_task(svc)
    _review_claim(svc)

    result = svc.review_claim_with_human_attestation(
        claim_id="c-human-review",
        disposition="accept",
        operator_id="captain",
        note="I verified the provider result matches the requested smoke-test token.",
        metadata=_meta("captain", "human", "human-review-accept"),
    )

    claim = svc.store.require_state("claim-c-human-review")
    task = svc.store.require_state("task-t-human-review")
    events = svc.store.read_stream("claim-c-human-review")
    assert [e["eventType"] for e in events[-3:]] == [
        "EvidenceRecorded", "ClaimVerified", "ClaimGuardDecided"
    ]
    attestation = events[-3]["payload"]["evidence"]
    verification = events[-2]["payload"]["verification"]
    decision = events[-1]["payload"]["decision"]
    assert attestation["evidence"]["kind"] == "human_attestation"
    assert attestation["evidence"]["attestedBy"] == {"actorId": "captain", "kind": "human"}
    assert verification["strategy"] == "human_review"
    assert verification["status"] == {"kind": "verified", "supportingEvidenceIds": [attestation["evidenceId"]]}
    assert decision["verdict"] == "accept"
    assert decision["verificationId"] == verification["verificationId"]
    assert claim["promotionState"] == "accepted"
    assert task["state"] == "succeeded"
    assert result["claimId"] == "c-human-review"
    assert result["taskState"] == "succeeded"


def test_human_review_reject_rejects_claim_and_fails_task():
    svc = _svc()
    _awaiting_task(svc, "t-human-reject")
    _review_claim(svc, "c-human-reject", "t-human-reject")

    result = svc.review_claim_with_human_attestation(
        claim_id="c-human-reject",
        disposition="reject",
        operator_id="captain",
        note="The provider result does not satisfy the requested acceptance criterion.",
        metadata=_meta("captain", "human", "human-review-reject"),
    )

    claim = svc.store.require_state("claim-c-human-reject")
    task = svc.store.require_state("task-t-human-reject")
    verification = svc.store.read_stream("claim-c-human-reject")[-2]["payload"]["verification"]
    assert verification["strategy"] == "human_review"
    assert verification["status"]["kind"] == "observed_unverified"
    assert claim["promotionState"] == "rejected"
    assert claim["guardVerdict"] == "reject"
    assert task["state"] == "failed"
    assert result["taskState"] == "failed"
