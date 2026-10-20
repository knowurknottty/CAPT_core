import Foundation
import LocalAuthentication
import Security

/// UPG-041: a non-exportable, user-presence-gated signing key.
/// No key is generated or used until the operator explicitly invokes enroll or sign.
/// This library does not enroll a public key into CAPT's governed trust registry.
public enum CAPTSecureEnclavePresence {
    public static let algorithm = "ECDSA_P256_SHA256"
    public static let schema = "capt.decision-offering-issuer-proof.v1"
    private static let domain = Data("CAPT:DecisionOfferingIssuerProof:v1".utf8) + Data([0])
    private static let fields: Set<String> = [
        "schemaVersion", "requestId", "issuerId", "keyId", "issuedAt",
        "expiresAt", "nonce", "commandFingerprint", "toolRequestDigest",
        "mainLedgerDigest", "offeringLedgerDigest", "action"
    ]

    public enum Failure: Error, Equatable {
        case malformedChallenge
        case unsupportedPurpose
        case expiredChallenge
        case unavailableBiometrics
        case enrollmentAlreadyExists
        case keyNotFound
        case insecureKeyStorage
        case operationFailed
        case publicKeyEncoding
    }

    public struct Enrollment {
        public let keyId: String
        public let publicKeyPEM: String
        public let algorithm: String
        public let secureEnclaveRequested: Bool
        // The caller must separately authenticate and pin this key in CAPT.
        public let runtimeEnrollmentVerified = false
    }

    public struct SignedProof {
        public let challenge: [String: String]
        public let algorithm: String
        public let signatureBase64: String
        // A valid signature alone never establishes CAPT authority.
        public let authorizationGranted = false
    }

    private static func safeIdentifier(_ id: String) -> Bool {
        id.range(of: "^[A-Za-z0-9_.:-]{1,128}$", options: .regularExpression) != nil
    }

    private static func canonicalDate(_ input: String) -> Date? {
        guard input.range(
            of: "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$",
            options: .regularExpression
        ) != nil else { return nil }
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.timeZone = TimeZone(secondsFromGMT: 0)
        df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss'Z'"
        df.isLenient = false
        return df.date(from: input)
    }

    public static func canonicalSigningBytes(challenge: [String: String]) throws -> Data {
        guard Set(challenge.keys) == fields,
              challenge["schemaVersion"] == schema,
              challenge["action"] == "issue_decision_offering"
        else { throw Failure.unsupportedPurpose }

        for name in ["requestId", "issuerId", "keyId"] {
            guard let value = challenge[name], safeIdentifier(value) else {
                throw Failure.malformedChallenge
            }
        }
        let hex = "^[a-f0-9]{64}$"
        guard let nonce = challenge["nonce"],
              nonce.range(of: hex, options: .regularExpression) != nil
        else { throw Failure.malformedChallenge }
        for name in [
            "commandFingerprint", "toolRequestDigest",
            "mainLedgerDigest", "offeringLedgerDigest"
        ] {
            guard let value = challenge[name],
                  value.range(of: "^sha256:[0-9a-f]{64}$", options: .regularExpression) != nil
            else { throw Failure.malformedChallenge }
        }
        guard let issued = challenge["issuedAt"].flatMap(canonicalDate),
              let expires = challenge["expiresAt"].flatMap(canonicalDate),
              expires > issued, expires.timeIntervalSince(issued) <= 60
        else { throw Failure.expiredChallenge }

        let body = try JSONSerialization.data(
            withJSONObject: challenge, options: [.sortedKeys, .withoutEscapingSlashes]
        )
        return domain + body
    }

    /// The tag is scoped to this app and key ID; never reuse the runtime's AES key.
    private static func tag(for keyId: String) throws -> Data {
        guard safeIdentifier(keyId) else { throw Failure.malformedChallenge }
        return Data("ai.inversionlabs.capt.upg041.presence.v1.\(keyId)".utf8)
    }

    private static func biometricContext() throws -> LAContext {
        let context = LAContext()
        context.touchIDAuthenticationAllowableReuseDuration = 0
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
        else { throw Failure.unavailableBiometrics }
        return context
    }

    private static func privateKey(keyId: String, context: LAContext) throws -> SecKey {
        let keyTag = try tag(for: keyId)
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: keyTag,
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecUseAuthenticationContext as String: context,
            kSecReturnRef as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { throw Failure.keyNotFound }
        guard status == errSecSuccess, let key = item else { throw Failure.operationFailed }
        return (key as! SecKey)
    }

    static func publicKeyPEM(for privateKey: SecKey) throws -> String {
        guard let publicKey = SecKeyCopyPublicKey(privateKey),
              let raw = SecKeyCopyExternalRepresentation(publicKey, nil) as Data?
        else { throw Failure.publicKeyEncoding }
        // SEC1 uncompressed P-256 public point (04 || X32 || Y32).
        guard raw.count == 65, raw.first == 0x04 else {
            throw Failure.publicKeyEncoding
        }
        // RFC 5480 SubjectPublicKeyInfo DER for id-ecPublicKey + prime256v1.
        let spkiHeader: [UInt8] = [
            0x30,0x59,0x30,0x13,0x06,0x07,0x2a,0x86,0x48,0xce,0x3d,
            0x02,0x01,0x06,0x08,0x2a,0x86,0x48,0xce,0x3d,0x03,
            0x01,0x07,0x03,0x42,0x00
        ]
        let encoded = (Data(spkiHeader) + raw).base64EncodedString()
        let lines = stride(from: 0, to: encoded.count, by: 64).map { offset in
            let start = encoded.index(encoded.startIndex, offsetBy: offset)
            let end = encoded.index(start, offsetBy: min(64, encoded.count-offset))
            return String(encoded[start..<end])
        }
        return "-----BEGIN PUBLIC KEY-----\n" + lines.joined(separator: "\n")
            + "\n-----END PUBLIC KEY-----\n"
    }

    /// Explicit operator enrollment entrypoint. NEVER call from application startup.
    /// Key uses Secure Enclave and must be unlocked with the current biometry set.
    public static func enrollExplicitly(keyId: String) throws -> Enrollment {
        let context = try biometricContext()
        let keyTag = try tag(for: keyId)
        do {
            _ = try privateKey(keyId: keyId, context: context)
            throw Failure.enrollmentAlreadyExists
        } catch Failure.keyNotFound {
            // New key only. An existing or inaccessible key must not be overwritten.
        }
        var accessError: Unmanaged<CFError>?
        guard let access = SecAccessControlCreateWithFlags(
            kCFAllocatorDefault, kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            [.privateKeyUsage, .biometryCurrentSet], &accessError
        ) else { throw Failure.operationFailed }
        let parameters: [String: Any] = [
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecAttrKeySizeInBits as String: 256,
            kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave,
            kSecPrivateKeyAttrs as String: [
                kSecAttrIsPermanent as String: true,
                kSecAttrApplicationTag as String: keyTag,
                kSecAttrAccessControl as String: access
            ]
        ]
        var error: Unmanaged<CFError>?
        guard let key = SecKeyCreateRandomKey(parameters as CFDictionary, &error)
        else { throw Failure.operationFailed }
        let attrs = SecKeyCopyAttributes(key) as? [String: Any]
        guard (attrs?[kSecAttrTokenID as String] as? String)
                == (kSecAttrTokenIDSecureEnclave as String)
        else { throw Failure.insecureKeyStorage }
        return Enrollment(keyId: keyId, publicKeyPEM: try publicKeyPEM(for: key),
                          algorithm: algorithm, secureEnclaveRequested: true)
    }

    /// Only call after a separate authenticated RuntimeService challenge read.
    /// The caller MUST NOT construct its own challenge or infer consent from this result.
    public static func signWithBiometry(
        challenge: [String: String], expectedKeyId: String
    ) throws -> SignedProof {
        let bytes = try canonicalSigningBytes(challenge: challenge)
        guard challenge["keyId"] == expectedKeyId else { throw Failure.malformedChallenge }
        // Refuse stale challenges locally, but runtime must independently check time.
        guard let nowExpiry = challenge["expiresAt"].flatMap(canonicalDate),
              Date() < nowExpiry,
              let start = challenge["issuedAt"].flatMap(canonicalDate),
              Date() >= start
        else { throw Failure.expiredChallenge }

        let context = try biometricContext()
        let key = try privateKey(keyId: expectedKeyId, context: context)
        var error: Unmanaged<CFError>?
        guard let signature = SecKeyCreateSignature(
            key, .ecdsaSignatureMessageX962SHA256, bytes as CFData, &error
        ) as Data? else { throw Failure.operationFailed }
        return SignedProof(challenge: challenge, algorithm: algorithm,
                           signatureBase64: signature.base64EncodedString())
    }
}
