"""Real ephemeral ECDSA P-256 tests. No privileged or production key is used."""
import base64
import importlib.util
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

file = Path(__file__).resolve().parents[2] / "research/quantum_leap_r4/issuer_signature.py"
spec = importlib.util.spec_from_file_location("ql_r4_issuer_signature", file)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class IssuerSignatureTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 19, 14, 30, tzinfo=timezone.utc)
        self.key = ec.generate_private_key(ec.SECP256R1())
        public = self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.registry = {"enrolled-1": m.TrustedIssuerKey(
            "enrolled-1", "operator-1", public,
        )}
        self.challenge = {
            "schemaVersion": "capt.decision-offering-issuer-proof.v1",
            "requestId": "request-1",
            "issuerId": "operator-1",
            "keyId": "enrolled-1",
            "issuedAt": "2026-10-19T14:29:50Z",
            "expiresAt": "2026-10-19T14:30:20Z",
            "nonce": "1" * 64,
            "commandFingerprint": "sha256:" + "2" * 64,
            "toolRequestDigest": "sha256:" + "3" * 64,
            "mainLedgerDigest": "sha256:" + "4" * 64,
            "offeringLedgerDigest": "sha256:" + "5" * 64,
            "action": "issue_decision_offering",
        }

    def signed(self, challenge=None, signer=None):
        challenge = self.challenge if challenge is None else challenge
        key = self.key if signer is None else signer
        signature = key.sign(
            m.signing_bytes(challenge), ec.ECDSA(hashes.SHA256())
        )
        return {
            "challenge": dict(challenge),
            "algorithm": "ECDSA_P256_SHA256",
            "signatureBase64": base64.b64encode(signature).decode("ascii"),
        }

    def verify(self, proof=None, expected=None, registry=None, now=None):
        return m.verify_signature_only(
            self.signed() if proof is None else proof,
            self.challenge if expected is None else expected,
            self.registry if registry is None else registry,
            now=self.now if now is None else now,
        )

    def test_valid_signature_never_means_authorization(self):
        result = self.verify()
        self.assertTrue(result["signature_valid_for_supplied_key"])
        self.assertEqual(result["reason"], "SIGNATURE_VALID_BUT_NOT_AUTHORIZATION")
        for key in ("operator_presence_verified", "enrollment_custody_verified",
                    "dispatch_allowed", "completion_verified", "nonce_consumption_verified"):
            self.assertFalse(result[key])

    def test_unknown_public_key(self):
        self.assertEqual(self.verify(registry={})["reason"], "UNKNOWN_ENROLLED_KEY")

    def test_revoked_key(self):
        keys={"enrolled-1":replace(self.registry["enrolled-1"],revoked=True)}
        self.assertEqual(self.verify(registry=keys)["reason"], "KEY_MARKED_REVOKED")

    def test_identity_substitution(self):
        keys={"enrolled-1":replace(self.registry["enrolled-1"],issuer_id="other")}
        self.assertEqual(self.verify(registry=keys)["reason"],"ENROLLMENT_IDENTITY_MISMATCH")

    def test_wrong_key_purpose(self):
        keys={"enrolled-1":replace(self.registry["enrolled-1"],purpose="release_signing")}
        self.assertEqual(self.verify(registry=keys)["reason"], "KEY_PURPOSE_MISMATCH")

    def test_wrong_p256_signer(self):
        forged=ec.generate_private_key(ec.SECP256R1())
        self.assertEqual(self.verify(proof=self.signed(signer=forged))["reason"],"SIGNATURE_INVALID")

    def test_wrong_curve_enrollment(self):
        pub=ec.generate_private_key(ec.SECP384R1()).public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        keys={"enrolled-1":replace(self.registry["enrolled-1"],public_key_pem=pub)}
        self.assertEqual(self.verify(registry=keys)["reason"], "NON_P256_ENROLLED_KEY")

    def test_changed_request_id(self):
        expected=dict(self.challenge,requestId="substituted")
        self.assertEqual(self.verify(expected=expected)["reason"],"SIGNED_INTENT_MISMATCH")

    def test_changed_ledger(self):
        expected=dict(self.challenge,mainLedgerDigest="sha256:"+"a"*64)
        self.assertEqual(self.verify(expected=expected)["reason"],"SIGNED_INTENT_MISMATCH")

    def test_expiration(self):
        self.assertEqual(self.verify(now=self.now+timedelta(seconds=22))["reason"],
                         "SIGNATURE_WINDOW_INACTIVE")

    def test_future_window(self):
        self.assertEqual(self.verify(now=self.now-timedelta(seconds=11))["reason"],
                         "SIGNATURE_WINDOW_INACTIVE")

    def test_noncanonical_timestamp(self):
        bad=dict(self.challenge,expiresAt="2026-10-19T14:30:20+00:00")
        self.assertEqual(self.verify(proof=self.signed(bad),expected=bad)["reason"],
                         "CHALLENGE_INVALID")

    def test_excessive_lifetime(self):
        bad=dict(self.challenge,expiresAt="2026-10-19T14:31:20Z")
        self.assertEqual(self.verify(proof=self.signed(bad),expected=bad)["reason"],
                         "CHALLENGE_INVALID")

    def test_wrong_action_domain(self):
        bad=dict(self.challenge,action="approve_payment")
        self.assertEqual(self.verify(proof=self.signed(bad),expected=bad)["reason"],
                         "CHALLENGE_INVALID")

    def test_extra_public_key_untrusted(self):
        p=self.signed()
        p["publicKeyPem"]="user-supplied"
        self.assertEqual(self.verify(proof=p)["reason"],"PROOF_SHAPE_INVALID")

    def test_invalid_base64(self):
        p=self.signed()
        p["signatureBase64"]="??notbase64"
        self.assertEqual(self.verify(proof=p)["reason"],"SIGNATURE_INVALID")

    def test_replay_not_falsely_claimed_prevented(self):
        p=self.signed()
        self.assertTrue(self.verify(proof=p)["signature_valid_for_supplied_key"])
        result=self.verify(proof=p)
        self.assertTrue(result["signature_valid_for_supplied_key"])
        self.assertFalse(result["nonce_consumption_verified"])

    def test_invalid_registry_fails_closed(self):
        self.assertEqual(
            m.verify_signature_only(self.signed(), self.challenge, None, now=self.now)["reason"], "TRUST_REGISTRY_INVALID"
        )

    def test_corrupted_pinned_pem_fails_closed(self):
        keys={"enrolled-1":replace(self.registry["enrolled-1"], public_key_pem=b"invalid")}
        self.assertEqual(self.verify(registry=keys)["reason"],"SIGNATURE_INVALID")

    def test_untrusted_clock(self):
        self.assertEqual(
            self.verify(now=datetime(2026,10,19,14,30))["reason"],"CLOCK_NOT_TRUSTED"
        )

    def test_wrong_nonce_format(self):
        bad=dict(self.challenge,nonce="INVALID")
        self.assertEqual(self.verify(proof=self.signed(bad),expected=bad)["reason"],
                         "CHALLENGE_INVALID")

    def test_invalid_algorithm(self):
        p=self.signed()
        p["algorithm"]="RSA"
        self.assertEqual(self.verify(proof=p)["reason"],"UNSUPPORTED_SIGNATURE_ALGORITHM")


if __name__=="__main__":
    unittest.main(verbosity=2)
