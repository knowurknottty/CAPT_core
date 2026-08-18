import XCTest
@testable import CAPTCoreDesktop

final class CAPTLabProjectionTests: XCTestCase {
    func testEngineProjectionPreservesEpistemicAndDonorProvenance() throws {
        let raw: [String: Any] = [
            "engineId": "lab.math",
            "engineVersion": "0.1.0",
            "displayName": "CAPTLang Math",
            "description": "Bounded math instruments",
            "available": true,
            "requiresFilesystem": false,
            "requiresNetwork": false,
            "operations": [
                ["name": "cyclotomic_summary", "epistemicClass": "calculation", "description": "Summarize field"]
            ],
            "provenance": [
                "donorRepository": "https://github.com/knowurknottty/biocapt-ecosystem.git",
                "donorCommit": "28e7834982c859731636e733c53df9f84893f897",
                "sourceFiles": [["path": "math/cyclotomic.rs", "sha256": "sha256:abc"]],
                "limitations": ["placeholder routines excluded"]
            ]
        ]
        let item = CAPTLabProjection.engine(raw)
        XCTAssertEqual(item.id, "lab.math")
        XCTAssertEqual(item.operations.first?.epistemicClass, "calculation")
        XCTAssertEqual(item.donorCommit, "28e7834982c859731636e733c53df9f84893f897")
        XCTAssertEqual(item.sourceFiles.first?.sha256, "sha256:abc")
        XCTAssertEqual(item.limitations, ["placeholder routines excluded"])
        XCTAssertTrue(item.available)
        XCTAssertFalse(item.requiresNetwork)
    }

    func testRunReceiptRemainsUnverifiedWhenClaimIsOnlyProposed() {
        let raw: [String: Any] = [
            "missionId": "m-1", "taskId": "t-1", "driverRunId": "dr-1",
            "claimId": "cl-1", "evidenceId": "ev-1", "verificationId": NSNull(),
            "promotionState": "proposed", "artifactPath": "/tmp/lab-result.json",
            "artifactDigest": "sha256:artifact", "requestDigest": "sha256:request",
            "engineId": "lab.math", "operation": "cyclotomic_summary",
            "epistemicClass": "calculation"
        ]
        let receipt = CAPTLabProjection.receipt(raw)
        XCTAssertEqual(receipt.authorityLabel, "UNVERIFIED")
        XCTAssertNil(receipt.verificationID)
        XCTAssertEqual(receipt.promotionState, "proposed")
        XCTAssertEqual(receipt.epistemicClass, "calculation")
    }

    func testRunReceiptOnlyLabelsVerifiedWithVerificationIdentity() {
        let raw: [String: Any] = [
            "missionId": "m-1", "taskId": "t-1", "driverRunId": "dr-1",
            "claimId": "cl-1", "evidenceId": "ev-1", "verificationId": "ver-1",
            "promotionState": "accepted", "artifactPath": "/tmp/lab-result.json",
            "artifactDigest": "sha256:artifact", "requestDigest": "sha256:request",
            "engineId": "lab.math", "operation": "cyclotomic_summary",
            "epistemicClass": "calculation"
        ]
        XCTAssertEqual(CAPTLabProjection.receipt(raw).authorityLabel, "VERIFIED")
    }

    func testInputJSONRequiresObjectRoot() throws {
        let input = try CAPTLabProjection.inputObject(from: "{\"conductor\":5}")
        XCTAssertEqual(input["conductor"] as? Int, 5)
        XCTAssertThrowsError(try CAPTLabProjection.inputObject(from: "[1,2,3]"))
        XCTAssertThrowsError(try CAPTLabProjection.inputObject(from: "not-json"))
    }
}
