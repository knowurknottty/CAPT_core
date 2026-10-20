import XCTest
import CryptoKit
import Security
@testable import CAPTCoreDesktop

final class CAPTSecureEnclavePresenceTests: XCTestCase {
    private let fixture: [String: String] = [
        "schemaVersion": "capt.decision-offering-issuer-proof.v1",
        "requestId": "request-1",
        "issuerId": "operator-1",
        "keyId": "enrolled-1",
        "issuedAt": "2026-10-19T14:29:50Z",
        "expiresAt": "2026-10-19T14:30:20Z",
        "nonce": String(repeating: "1", count: 64),
        "commandFingerprint": "sha256:" + String(repeating: "2", count: 64),
        "toolRequestDigest": "sha256:" + String(repeating: "3", count: 64),
        "mainLedgerDigest": "sha256:" + String(repeating: "4", count: 64),
        "offeringLedgerDigest": "sha256:" + String(repeating: "5", count: 64),
        "action": "issue_decision_offering"
    ]

    private func assertRefused(_ challenge: [String: String]) {
        XCTAssertThrowsError(
            try CAPTSecureEnclavePresence.canonicalSigningBytes(challenge: challenge)
        )
    }

    func testCanonicalMatchesPinnedPythonVerifierBytes() throws {
        let result = try CAPTSecureEnclavePresence.canonicalSigningBytes(challenge: fixture)
        XCTAssertEqual(result.count, 721)
        XCTAssertEqual(
            SHA256.hash(data: result).compactMap { String(format: "%02x", $0) }.joined(),
            "5c68a6b429a533c978632f68d6348d6290f0189861290e222e2ac4c7244bc4ad"
        )
        XCTAssertEqual(
            result.prefix(36),
            Data("CAPT:DecisionOfferingIssuerProof:v1".utf8) + Data([0])
        )
    }

    func testWrongPurposeRefused() {
        var challenge = fixture
        challenge["action"] = "authorize_tool_dispatch"
        assertRefused(challenge)
    }

    func testMissingFieldRefused() {
        var challenge = fixture
        challenge.removeValue(forKey: "nonce")
        assertRefused(challenge)
    }

    func testExtraFieldRefused() {
        var challenge = fixture
        challenge["permission"] = "approved"
        assertRefused(challenge)
    }

    func testInvalidRequestIdentityRefused() {
        var challenge = fixture
        challenge["requestId"] = "request with spaces"
        assertRefused(challenge)
    }

    func testInvalidNonceRefused() {
        var challenge = fixture
        challenge["nonce"] = String(repeating: "z", count: 64)
        assertRefused(challenge)
    }

    func testWrongDigestRefused() {
        var challenge = fixture
        challenge["toolRequestDigest"] = "no digest"
        assertRefused(challenge)
    }

    func testOverlongValidityRefused() {
        var challenge = fixture
        challenge["expiresAt"] = "2026-10-19T14:31:20Z"
        assertRefused(challenge)
    }

    func testNonCanonicalTimestampRefused() {
        var challenge = fixture
        challenge["issuedAt"] = "2026-10-19T14:29:50+00:00"
        assertRefused(challenge)
    }

    func testExpiredOrderRefused() {
        var challenge = fixture
        challenge["expiresAt"] = "2026-10-19T14:29:49Z"
        assertRefused(challenge)
    }

    func testSPKIPEMEncodesSoftwareTestPublicPoint() throws {
        // Ephemeral software key ONLY for checking serialization.
        // This test never creates or claims a Secure Enclave credential.
        let params: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeySizeInBits as String: 256
        ]
        guard let privateKey = SecKeyCreateRandomKey(params as CFDictionary, nil),
              let pub = SecKeyCopyPublicKey(privateKey),
              let point = SecKeyCopyExternalRepresentation(pub, nil) as Data?
        else { return XCTFail("Ephemeral P-256 fixture unavailable") }
        let pem = try CAPTSecureEnclavePresence.publicKeyPEM(for: privateKey)
        let rawBase64 = pem
            .replacingOccurrences(of: "-----BEGIN PUBLIC KEY-----", with: "")
            .replacingOccurrences(of: "-----END PUBLIC KEY-----", with: "")
            .replacingOccurrences(of: "\n", with: "")
        guard let spki = Data(base64Encoded: rawBase64) else {
            return XCTFail("SPKI base64 must decode")
        }
        XCTAssertEqual(spki.count, 91)
        XCTAssertEqual(Data(spki.suffix(65)), point)
        XCTAssertEqual(Array(spki.prefix(2)), [0x30, 0x59])
    }
}
