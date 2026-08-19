import XCTest
@testable import CAPTCoreDesktop

final class CAPTRuntimeControlProjectionTests: XCTestCase {
    func testIdentityProjectionPreservesRuntimeSurface() {
        let response: [String: Any] = [
            "result": [
                "runtimeVersion": "0.1.0",
                "integrity": "ok",
                "headSequence": 937
            ]
        ]
        let identity = CAPTRuntimeControlProjection.identity(response)
        XCTAssertEqual(identity.runtimeVersion, "0.1.0")
        XCTAssertEqual(identity.integrity, "ok")
        XCTAssertEqual(identity.headSequence, 937)
    }

    func testMemoryProjectionPreservesPolicyAndContextState() {
        let policy: [String: Any] = [
            "policyVersion": 1,
            "policyDigest": "sha256:mem",
            "triggerIntervalTokens": 32768,
            "retrievalTriggerSteps": 8, "compressionTriggerSteps": 7,
            "checkpointTriggerSteps": 6, "consolidationTriggerSteps": 5,
            "hardStopTriggerSteps": 4, "modelSafeLimitSteps": 3
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
        XCTAssertEqual(result.retrievalTriggerSteps, 8)
        XCTAssertEqual(result.compressionTriggerSteps, 7)
        XCTAssertEqual(result.checkpointTriggerSteps, 6)
        XCTAssertEqual(result.consolidationTriggerSteps, 5)
        XCTAssertEqual(result.hardStopTriggerSteps, 4)
        XCTAssertEqual(result.modelSafeLimitSteps, 3)
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

extension CAPTRuntimeControlProjectionTests {
    func testCapabilitiesProjectionPreservesRuntimeSurface() {
        let result: [String: Any] = [
            "queryOperations": ["identity", "verification"],
            "commandOperations": ["cancel_task", "shutdown"],
            "runtimeComponents": ["eventStore": true, "memory": true, "ctp": false],
            "lifecycleOperations": ["checkpoint": true, "shutdown": true]
        ]
        let caps = CAPTRuntimeControlProjection.capabilities(result)
        XCTAssertEqual(caps.queryOperations, ["identity", "verification"])
        XCTAssertEqual(caps.commandOperations, ["cancel_task", "shutdown"])
        XCTAssertEqual(caps.activeComponents, ["eventStore", "memory"])
        XCTAssertEqual(caps.lifecycleOperations, ["checkpoint", "shutdown"])
    }
}

extension CAPTRuntimeControlProjectionTests {
    func testClaimReviewProjectionKeepsAdvisorySeparateFromVerification() {
        let guardResult: [String: Any] = [
            "statement": "Repository inspected.", "verdict": "accepted",
            "committed": false, "advisory": true
        ]
        let verification: [String: Any] = [
            "status": ["kind": "not_tested"], "trust": "capt_authoritative"
        ]
        let review = CAPTRuntimeControlProjection.claimReview(
            claimID: "cl-1", guardResult: guardResult, verification: verification
        )
        XCTAssertEqual(review.guardVerdict, "accepted")
        XCTAssertTrue(review.guardAdvisory)
        XCTAssertFalse(review.guardCommitted)
        XCTAssertEqual(review.verificationStatus, "not_tested")
        XCTAssertEqual(review.verificationTrust, "capt_authoritative")
    }
}
