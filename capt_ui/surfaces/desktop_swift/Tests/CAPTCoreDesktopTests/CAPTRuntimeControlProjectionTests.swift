import XCTest
@testable import CAPTCoreDesktop

final class CAPTRuntimeControlProjectionTests: XCTestCase {
    func testMemoryProjectionPreservesPolicyAndContextState() {
        let policy: [String: Any] = [
            "policyVersion": 1,
            "policyDigest": "sha256:mem",
            "triggerIntervalTokens": 32768
        ]
        let state: [String: Any] = [
            "memoryPathActive": true,
            "lastContextPack": NSNull(),
            "triggerLog": [["reason": "threshold"]],
            "policyVersions": [1]
        ]
        let result = CAPTRuntimeControlProjection.memory(policy: policy, state: state)
        XCTAssertTrue(result.active)
        XCTAssertEqual(result.policyVersion, 1)
        XCTAssertEqual(result.triggerIntervalTokens, 32768)
        XCTAssertEqual(result.triggerCount, 1)
        XCTAssertNil(result.lastContextPackDigest)
    }
    func testCheckpointProjectionUsesGovernedReceiptFields() {
        let receipt: [String: Any] = [
            "status": "accepted",
            "ledgerHead": 184,
            "result": [
                "checkpointId": "cp-123",
                "createdAt": "2026-08-18T12:58:48Z",
                "ledgerDigest": "sha256:ledger",
                "ledgerPosition": ["globalSequence": 184],
                "integrityDigest": "sha256:integrity"
            ]
        ]
        let result = CAPTRuntimeControlProjection.checkpoint(receipt)
        XCTAssertEqual(result?.checkpointID, "cp-123")
        XCTAssertEqual(result?.ledgerSequence, 184)
        XCTAssertEqual(result?.status, "accepted")
        XCTAssertEqual(result?.integrityDigest, "sha256:integrity")
    }
}
