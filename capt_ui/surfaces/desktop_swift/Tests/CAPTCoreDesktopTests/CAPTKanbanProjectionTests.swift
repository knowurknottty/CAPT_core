import XCTest
@testable import CAPTCoreDesktop

final class CAPTKanbanProjectionTests: XCTestCase {
    private func task(_ id: String, _ state: String,
                      driver: String? = nil) -> CAPTTaskSummary {
        CAPTTaskSummary(
            id: id, missionID: "m-project",
            title: "Review fix for " + id,
            state: state, assignedDriverID: driver,
            attempt: 1, maxAttempts: 2,
            dependencies: id == "task-2" ? ["task-1"] : [],
            consequential: true
        )
    }
    private func mission(_ tasks: [CAPTTaskSummary]) -> CAPTMissionSummary {
        CAPTMissionSummary(id: "m-project", title: "CAPT launch readiness",
                           missionState: "executing", tasks: tasks)
    }
    private func run(_ id: String, taskID: String, state: String = "completed") -> CAPTDriverRunSummary {
        CAPTDriverRunSummary(
            id: id, missionID: "m-project", taskID: taskID,
            driverID: "hermes", state: state,
            reconciliationStatus: "settled", externalRunID: nil
        )
    }

    func testMappingDoesNotInventRunningOrCompletion() {
        let states = ["pending", "ready", "assigned", "running",
                      "awaiting_verification", "suspended",
                      "failed", "succeeded", "cancelled"]
        let expected: [CAPTKanbanLane] = [
            .planned, .ready, .ready, .markedRunning, .verification,
            .blocked, .blocked, .resolved, .resolved
        ]
        XCTAssertEqual(states.map { CAPTKanbanLane.lane(for: $0) }, expected)
        XCTAssertTrue(CAPTKanbanLane.markedRunning.explanation.contains("not attested"))
        let items = CAPTKanbanProjection.cards(
            missions: [mission([task("running", "running", driver: "capt-node")])],
            runs: [], approvals: [])
        XCTAssertEqual(items[0].lane, .markedRunning)
        XCTAssertTrue(items[0].nextAction.contains("heartbeat"))
        XCTAssertNil(items[0].run)
    }

    func testBlockedDependencyAndExplicitParticipantArePreserved() {
        let items = CAPTKanbanProjection.cards(
            missions: [mission([task("task-1", "suspended"),
                                task("task-2", "awaiting_verification",
                                     driver: "capt-node")])],
            runs: [run("dr-1", taskID: "task-2")],
            approvals: []
        )
        XCTAssertEqual(items.count, 2)
        let blocked = try! XCTUnwrap(items.first { $0.id == "task-1" })
        XCTAssertEqual(blocked.lane, .blocked)
        XCTAssertTrue(blocked.needsAttention)
        let review = try! XCTUnwrap(items.first { $0.id == "task-2" })
        XCTAssertEqual(review.task.dependencies, ["task-1"])
        XCTAssertEqual(review.lane, .verification)
        XCTAssertEqual(review.run?.id, "dr-1")
        XCTAssertTrue(review.participants.contains("Driver: capt-node"))
        XCTAssertTrue(review.participants.contains("Human decision required"))
        XCTAssertFalse(review.participants.contains(where: { $0.hasPrefix("Cohort:") }))
    }

    func testVesselLabelIsDeclaredOnlyWhenBoundToCouncilTask() throws {
        var cohort = CAPTCouncilCohort(
            id: "cohort-a", provider: "openrouter",
            model: "z-ai/glm-5.3-flash", vessels: 22
        )
        cohort.taskID = "task-c"
        let council = try CAPTCouncilReview(
            id: "council-1", missionID: "m-project",
            objective: "Review release", targetRoot: "/tmp/project",
            maxConcurrentCohorts: 1, cohorts: [cohort]
        )
        let cards = CAPTKanbanProjection.cards(
            missions: [mission([task("task-c", "awaiting_verification")])],
            runs: [], approvals: [], council: council
        )
        XCTAssertTrue(cards[0].participants.contains("Cohort: cohort-a"))
        XCTAssertTrue(cards[0].participants.contains("Declared vessels: 22"))
        XCTAssertNil(cards[0].run)
    }
}
