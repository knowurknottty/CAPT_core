import XCTest
@testable import CAPTCoreDesktop

final class CAPTLedgerSemanticsTests: XCTestCase {
    private func item(_ type: String) -> CAPTEventSummary {
        CAPTEventSummary(
            sequence: 100, type: type, occurredAt: "2026-10-08T06:00:00Z",
            streamID: "task-t1", missionID: "m1", taskID: "t1",
            actorKind: "execution_plane"
        )
    }

    func testRoutineTransportFilteringNeverChangesStoredEvents() {
        let events = [
            item("ToolExecutionPrepared"), item("TaskTransitioned"),
            item("ToolExecutionDispatching"), item("HumanApprovalDecided")
        ]
        let visible = events.filter {
            !CAPTLedgerSemantics.transportNoise.contains($0.type)
        }
        XCTAssertEqual(visible.map(\.type), ["TaskTransitioned", "HumanApprovalDecided"])
        XCTAssertEqual(events.count, 4)
    }

    func testDecisionFilterIsExplicitDerivedReadOnlyView() {
        XCTAssertTrue(CAPTLedgerSemantics.isDecisionOrResult(item("TaskTransitioned")))
        XCTAssertTrue(CAPTLedgerSemantics.isDecisionOrResult(item("HumanApprovalDecided")))
        XCTAssertFalse(CAPTLedgerSemantics.isDecisionOrResult(item("ToolExecutionPrepared")))
        XCTAssertEqual(CAPTLedgerSemantics.readableName("ClaimCreated"), "Claim recorded (not verified)")
        XCTAssertEqual(CAPTLedgerSemantics.readableName("CustomFutureEvent"), "CustomFutureEvent")
    }
}
