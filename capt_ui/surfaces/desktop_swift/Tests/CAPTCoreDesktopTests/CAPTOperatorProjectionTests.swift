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
