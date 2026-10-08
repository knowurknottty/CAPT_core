import Foundation
import XCTest
@testable import CAPTCoreDesktop

final class CAPTMissionTriageTests: XCTestCase {
    private func task(_ state: String, id: String = "task-1") -> CAPTTaskSummary {
        CAPTTaskSummary(
            id: id, missionID: "m-test",
            title: "Review a source-backed mission result and provenance",
            state: state, assignedDriverID: nil,
            attempt: 1, maxAttempts: 2,
            dependencies: [], consequential: true
        )
    }

    private func mission(_ states: [String], storedState: String = "executing") -> CAPTMissionSummary {
        CAPTMissionSummary(
            id: "m-test", title: "A detailed test mission from the operator",
            missionState: storedState,
            tasks: states.enumerated().map { index, state in
                task(state, id: "t-\(index)")
            }
        )
    }

    func testSuspendedIsNotActuallyRunning() {
        let item = mission(["suspended", "awaiting_verification"])
        XCTAssertFalse(item.hasActiveExecution)
        XCTAssertEqual(CAPTMissionTriage.classify(item), .interrupted)
        XCTAssertTrue(CAPTMissionTriage.classify(item).needsHumanAttention)
    }

    func testCompletedOutputStillNeedsVerification() {
        let item = mission(["awaiting_verification"], storedState: "authorized")
        XCTAssertEqual(CAPTMissionTriage.classify(item), .awaitingReview)
        XCTAssertFalse(item.hasActiveExecution)
        XCTAssertTrue(CAPTMissionTriage.classify(item).nextStep.contains("human"))
    }

    func testStoredExecutingDoesNotInventActiveExecution() {
        let item = mission(["failed"], storedState: "executing")
        XCTAssertEqual(CAPTMissionTriage.classify(item), .failed)
        XCTAssertFalse(item.hasActiveExecution)
    }

    func testOnlyRunningTaskGetsUnconfirmedRunningBadge() {
        let item = mission(["running", "pending"])
        XCTAssertTrue(item.hasActiveExecution)
        XCTAssertEqual(CAPTMissionTriage.classify(item), .markedRunning)
        XCTAssertTrue(CAPTMissionTriage.classify(item).explanation.contains("does not prove"))
    }

    func testSuccessfulTasksDoNotInventMissionClosure() {
        let item = mission(["succeeded", "succeeded"], storedState: "authorized")
        XCTAssertEqual(CAPTMissionTriage.classify(item), .completed)
        XCTAssertEqual(item.missionState, "authorized")
        XCTAssertTrue(CAPTMissionTriage.classify(item).nextStep.contains("do not invent"))
    }

    func testTaskSummaryAndTitleAreReadable() {
        let item = mission(["suspended", "awaiting_verification", "succeeded"])
        let counts = CAPTMissionTriage.counts(item)
        XCTAssertTrue(counts.contains("interrupted"))
        XCTAssertTrue(counts.contains("need review"))
        XCTAssertEqual(CAPTMissionTriage.readableTitle(" a\n\t b  c ", maxLength: 20), "a b c")
        XCTAssertLessThanOrEqual(CAPTMissionTriage.readableTitle(String(repeating: "x", count: 300)).count, 126)
    }
}
