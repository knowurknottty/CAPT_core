import XCTest
@testable import CAPTCoreDesktop

final class CAPTOperatorProjectionTests: XCTestCase {
    func testMissionProjectionUsesTaskTitleAndState() {
        let mission: [String: Any] = [
            "missionId": "m-1", "state": "draft"
        ]
        let task: [String: Any] = [
            "taskId": "t-1", "missionId": "m-1",
            "title": "Inspect CAPT", "state": "awaiting_verification"
        ]
        let summary = CAPTOperatorProjection.mission(
            mission, tasks: [task]
        )
        XCTAssertEqual(summary.id, "m-1")
        XCTAssertEqual(summary.title, "Inspect CAPT")
        XCTAssertEqual(summary.taskState, "awaiting_verification")
    }

    func testEvidenceProjectionPreservesEpistemicState() {
        let claim: [String: Any] = [
            "claimId": "cl-1", "missionId": "m-1",
            "statement": "Repository inspected.",
            "promotionState": "proposed",
            "verificationStatus": NSNull(), "guardVerdict": NSNull(),
            "evidenceIds": ["ev-1"]
        ]
        let summary = CAPTOperatorProjection.evidence(claim)
        XCTAssertEqual(summary.promotionState, "proposed")
        XCTAssertNil(summary.verificationStatus)
        XCTAssertNil(summary.guardVerdict)
        XCTAssertEqual(summary.evidenceCount, 1)
    }

    func testEventProjectionKeepsSequenceAndAuthorityActor() {
        let raw: [String: Any] = [
            "globalSequence": 162, "eventType": "TaskTransitioned",
            "occurredAt": "2026-08-18T07:06:21Z",
            "streamId": "task-t-1", "missionId": "m-1",
            "actor": ["kind": "execution_plane"]
        ]
        let summary = CAPTOperatorProjection.event(raw)
        XCTAssertEqual(summary.sequence, 162)
        XCTAssertEqual(summary.type, "TaskTransitioned")
        XCTAssertEqual(summary.actorKind, "execution_plane")
        XCTAssertEqual(summary.missionID, "m-1")
    }
}

extension CAPTOperatorProjectionTests {
    func testApprovalProjectionPreservesDecisionAndBinding() {
        let raw: [String: Any] = [
            "requestId": "approval-1", "missionId": "m-1", "taskId": "t-1",
            "operation": "ModelOperatorInspection", "requestedCapability": "cap.fs.read",
            "riskClassification": "low", "state": "requested", "remainingUses": 1,
            "expiresAt": "2026-08-18T14:00:00Z",
            "scope": ["approvalBinding": ["provider": "ollama", "model": "qwen", "targetRoot": "/repo"]]
        ]
        let item = CAPTOperatorProjection.approval(raw)
        let formatter = ISO8601DateFormatter()
        let beforeExpiry = formatter.date(from: "2026-08-18T13:59:59Z")!
        let atExpiry = formatter.date(from: "2026-08-18T14:00:00Z")!

        XCTAssertEqual(item.id, "approval-1")
        XCTAssertEqual(item.provider, "ollama")
        XCTAssertEqual(item.model, "qwen")
        XCTAssertEqual(item.state, "requested")
        XCTAssertEqual(item.remainingUses, 1)
        XCTAssertTrue(item.isActionable(at: beforeExpiry))
        XCTAssertFalse(item.isActionable(at: atExpiry))
    }

    func testApprovalWithMalformedExpiryFailsClosed() {
        let raw: [String: Any] = [
            "requestId": "approval-2", "missionId": "m-1", "taskId": "t-2",
            "operation": "ModelOperatorInspection", "requestedCapability": "cap.fs.read",
            "riskClassification": "low", "state": "requested", "remainingUses": 1,
            "expiresAt": "not-a-time"
        ]
        let item = CAPTOperatorProjection.approval(raw)
        XCTAssertFalse(item.isActionable())
    }
}

extension CAPTOperatorProjectionTests {
    func testDriverRunProjectionPreservesTaskAndRecoveryState() {
        let raw: [String: Any] = [
            "driverRunId": "dr-1", "driverId": "provider",
            "missionId": "m-1", "taskId": "t-1",
            "state": "running", "reconciliationStatus": "not_required"
        ]
        let item = CAPTOperatorProjection.driverRun(raw)
        XCTAssertEqual(item.id, "dr-1")
        XCTAssertEqual(item.taskID, "t-1")
        XCTAssertEqual(item.driverID, "provider")
        XCTAssertEqual(item.state, "running")
        XCTAssertEqual(item.reconciliationStatus, "not_required")
    }
}
