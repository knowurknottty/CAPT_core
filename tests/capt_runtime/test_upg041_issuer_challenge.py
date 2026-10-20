import base64
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from capt_runtime.store import EventStore

from research.quantum_leap_r4.issuer_challenge_store import (
    ENROLL_DOMAIN, REVOKE_DOMAIN, IssuerChallengeRegistry,
    ProofRefused, _canonical,
)
from research.quantum_leap_r4.issuer_signature import signing_bytes


@pytest.fixture
def world(tmp_path):
    now = [datetime(2026,10,19,14,30,0,tzinfo=timezone.utc)]
    root = ec.generate_private_key(ec.SECP256R1())
    signer = ec.generate_private_key(ec.SECP256R1())

    def pem(key):
        return key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    root_pem = pem(root)
    cert = {
        "schemaVersion":"capt.upg041.enrollment.v1",
        "issuerId":"operator-test-1",
        "keyId":"mac-key-1",
        "publicKeyPEM":pem(signer).decode("ascii"),
        "purpose":"decision_offering_issue",
    }
    certificate_sig = base64.b64encode(
        root.sign(ENROLL_DOMAIN + _canonical(cert),ec.ECDSA(hashes.SHA256()))
    ).decode("ascii")
    main = EventStore(str(tmp_path/"main.db"))
    offerings = EventStore(str(tmp_path/"offer.db"))
    registry_path = str(tmp_path/"challenge.db")
    registry = IssuerChallengeRegistry(
        registry_path,enrollment_root_pem=root_pem,
        main_store=main,offering_store=offerings,
        clock=lambda:now[0],
    )

    def challenge():
        return registry.issue(
            issuer_id="operator-test-1",key_id="mac-key-1",
            request_id="request-1",
            command_fingerprint="sha256:"+"1"*64,
            tool_request_digest="sha256:"+"2"*64,
            main_store=main,offering_store=offerings,
        )

    def proof(ch):
        signed=signer.sign(signing_bytes(ch),ec.ECDSA(hashes.SHA256()))
        return {
            "challenge":ch,
            "algorithm":"ECDSA_P256_SHA256",
            "signatureBase64":base64.b64encode(signed).decode("ascii"),
        }

    yield {
        "now":now,"root":root,"root_pem":root_pem,
        "signer":signer,"registry":registry,"registry_path":registry_path,
        "certificate":cert,"certificate_sig":certificate_sig,
        "main":main,"offerings":offerings,"challenge":challenge,"proof":proof,
    }
    main.close()
    offerings.close()
    registry.close()


def enroll(w):
    w["registry"].enroll(w["certificate"],w["certificate_sig"])


def test_real_ecdsa_enrollment_challenge_and_atomic_one_time_consume(world):
    enroll(world)
    challenge = world["challenge"]()
    output = world["registry"].consume(
        world["proof"](challenge),
        main_store=world["main"],offering_store=world["offerings"],
    )
    assert output["signatureValid"]
    assert output["singleUseNonceConsumed"]
    assert not output["operatorPresenceVerified"]
    assert not output["dispatchAllowed"]
    assert not output["rootCustodyIndependentlyVerified"]
    assert world["main"].head_sequence()==0
    assert world["offerings"].head_sequence()==0


def test_durable_replay_rejected_across_connections(world):
    enroll(world)
    proof=world["proof"](world["challenge"]())
    registry=world["registry"]
    registry.consume(proof,main_store=world["main"],offering_store=world["offerings"])
    second=IssuerChallengeRegistry(
        world["registry_path"],enrollment_root_pem=world["root_pem"],
        main_store=world["main"],offering_store=world["offerings"],
        clock=lambda:world["now"][0],
    )
    try:
        with pytest.raises(ProofRefused,match="UNKNOWN_OR_CONSUMED_NONCE"):
            second.consume(proof,main_store=world["main"],offering_store=world["offerings"])
    finally:
        second.close()


def test_invalid_enrollment_root_signature_refused(world):
    bad=base64.b64encode(b"bad signature").decode()
    with pytest.raises(ProofRefused,match="INVALID_ROOT_SIGNATURE"):
        world["registry"].enroll(world["certificate"],bad)
    with pytest.raises(ProofRefused,match="UNENROLLED_OR_REVOKED_ISSUER"):
        world["challenge"]()


def test_unenrolled_key_cannot_receive_challenge(world):
    with pytest.raises(ProofRefused,match="UNENROLLED_OR_REVOKED_ISSUER"):
        world["challenge"]()


def test_wrong_key_cannot_sign_issued_challenge(world):
    enroll(world)
    challenge=world["challenge"]()
    wrong=ec.generate_private_key(ec.SECP256R1())
    signature=wrong.sign(signing_bytes(challenge),ec.ECDSA(hashes.SHA256()))
    forged={
        "challenge":challenge, "algorithm":"ECDSA_P256_SHA256",
        "signatureBase64":base64.b64encode(signature).decode("ascii"),
    }
    with pytest.raises(ProofRefused,match="SIGNED_CHALLENGE_REFUSED"):
        world["registry"].consume(forged,main_store=world["main"],offering_store=world["offerings"])
    assert world["registry"].consume(
        world["proof"](challenge),main_store=world["main"],offering_store=world["offerings"]
    )["singleUseNonceConsumed"]


def test_signed_intent_substitution_fails_without_consumption(world):
    enroll(world)
    challenge=world["challenge"]()
    changed=dict(challenge,requestId="changed-request")
    with pytest.raises(ProofRefused,match="SIGNED_CHALLENGE_REFUSED"):
        world["registry"].consume(
            world["proof"](changed),main_store=world["main"],offering_store=world["offerings"]
        )
    assert world["registry"].consume(
        world["proof"](challenge),main_store=world["main"],offering_store=world["offerings"]
    )["signatureValid"]


def test_time_expiry_refuses_even_with_valid_signature(world):
    enroll(world)
    signed=world["proof"](world["challenge"]())
    world["now"][0]+=timedelta(seconds=61)
    with pytest.raises(ProofRefused,match="SIGNED_CHALLENGE_REFUSED"):
        world["registry"].consume(
            signed,main_store=world["main"],offering_store=world["offerings"]
        )


def test_root_signed_revocation_blocks_existing_challenge(world):
    enroll(world)
    signed=world["proof"](world["challenge"]())
    rev={"schemaVersion":"capt.upg041.revocation.v1","keyId":"mac-key-1"}
    sig=base64.b64encode(
        world["root"].sign(REVOKE_DOMAIN+_canonical(rev),ec.ECDSA(hashes.SHA256()))
    ).decode("ascii")
    world["registry"].revoke("mac-key-1",sig)
    with pytest.raises(ProofRefused,match="SIGNED_CHALLENGE_REFUSED"):
        world["registry"].consume(
            signed,main_store=world["main"],offering_store=world["offerings"]
        )
    with pytest.raises(ProofRefused,match="UNENROLLED_OR_REVOKED_ISSUER"):
        world["challenge"]()


def test_fake_revocation_root_signature_refused(world):
    enroll(world)
    with pytest.raises(ProofRefused,match="INVALID_ROOT_SIGNATURE"):
        world["registry"].revoke("mac-key-1",base64.b64encode(b"fake").decode())
    assert world["challenge"]()


def test_root_rotation_without_governed_ceremony_fails_closed(world):
    other=ec.generate_private_key(ec.SECP256R1())
    other_pem=other.public_key().public_bytes(
        serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with pytest.raises(ProofRefused,match="ROOT_KEY_PIN_MISMATCH"):
        IssuerChallengeRegistry(
            world["registry_path"],enrollment_root_pem=other_pem,
            main_store=world["main"],offering_store=world["offerings"],
            clock=lambda:world["now"][0],
        )


def test_existing_key_cannot_silently_rotate(world):
    enroll(world)
    with pytest.raises(sqlite3.IntegrityError):
        enroll(world)


def test_issued_nonce_is_cryptographically_random_format(world):
    enroll(world)
    a=world["challenge"]()
    b=world["challenge"]()
    assert len(a["nonce"])==64
    assert a["nonce"]!=b["nonce"]
    assert a["mainLedgerDigest"]==world["main"].head_chain()


def test_readonly_verification_never_mutates_CAPT_authority(world):
    enroll(world)
    proof=world["proof"](world["challenge"]())
    result=world["registry"].consume(
        proof,main_store=world["main"],offering_store=world["offerings"]
    )
    assert result["reason"]=="SIGNED_CHALLENGE_CONSUMED_NOT_AUTHORIZATION"
    assert world["main"].head_sequence()==0
    assert world["offerings"].head_sequence()==0

def test_main_ledger_drift_refuses_a_valid_signature(world):
    """Actual EventStore write invalidates the issued world-basis digest."""
    import json
    from copy import deepcopy
    from pathlib import Path
    from capt_runtime import commands
    from capt_runtime.services import RuntimeService
    from capt_runtime.store import AppendRequest

    enroll(world)
    proof=world["proof"](world["challenge"]())
    repo=Path(__file__).resolve().parents[2]
    fixtures=json.loads((repo/"contracts/fixtures/capability_and_events.json").read_text())
    envelope=deepcopy(next(x["value"] for x in fixtures["cases"]
                           if x["id"]=="event-envelope-valid"))
    envelope["eventId"]="upg041-drift-event"
    envelope["streamId"]="mission-upg041-drift"
    envelope["missionId"]="upg041-drift"
    metadata=commands.command(
        command_id="upg041-drift-command",
        idempotency_key="upg041-drift-command",
        operation_fingerprint="sha256:"+"a"*64,
        correlation_id="upg041-drift",
        actor_id="fixture-system",actor_kind="system",
        issued_at="2026-10-19T14:30:00Z",
    )
    RuntimeService(world["main"])._commit([
        AppendRequest(envelope["streamId"],"mission",0,envelope,
                      {"fixture":"upg041-drift"})
    ],metadata)
    with pytest.raises(ProofRefused,match="WORLD_OR_POLICY_LEDGER_CHANGED"):
        world["registry"].consume(
            proof,main_store=world["main"],offering_store=world["offerings"]
        )


def test_signature_from_unauthenticated_enrollment_key_cannot_self_register(world):
    certificate=world["certificate"]
    different=ec.generate_private_key(ec.SECP256R1())
    forged=base64.b64encode(
        different.sign(ENROLL_DOMAIN+_canonical(certificate),
                       ec.ECDSA(hashes.SHA256()))
    ).decode()
    with pytest.raises(ProofRefused,match="INVALID_ROOT_SIGNATURE"):
        world["registry"].enroll(certificate,forged)

def test_registry_cannot_be_initialized_inside_main_eventstore(world):
    with pytest.raises(ProofRefused,match="ISSUER_STORE_MUST_BE_ISOLATED"):
        IssuerChallengeRegistry(
            world["main"].path,enrollment_root_pem=world["root_pem"],
            main_store=world["main"],offering_store=world["offerings"],
        )


def test_issuer_api_cannot_swap_ledger_object_after_construction(world):
    enroll(world)
    with pytest.raises(ProofRefused,match="LEDGER_BINDING_MISMATCH"):
        world["registry"].issue(
            issuer_id="operator-test-1",key_id="mac-key-1",request_id="request-1",
            command_fingerprint="sha256:"+"1"*64,
            tool_request_digest="sha256:"+"2"*64,
            main_store=world["offerings"],offering_store=world["main"],
        )
