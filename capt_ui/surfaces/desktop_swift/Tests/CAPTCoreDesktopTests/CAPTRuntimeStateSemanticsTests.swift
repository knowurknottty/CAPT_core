import XCTest
@testable import CAPTCoreDesktop

final class CAPTRuntimeStateSemanticsTests: XCTestCase {
    func testDangerousAndUncertainStatesNeverCollapseToNeutral() {
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "lost"), .danger)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "failed"), .danger)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "timed_out"), .danger)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "expired"), .danger)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "indeterminate"), .warning)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "suspended"), .warning)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "cancelled"), .warning)
    }

    func testActiveProposalAndExecutionStatesAreExplicit() {
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "proposal_compiling"), .violet)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "proposal_review"), .violet)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "executing"), .active)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "running"), .active)
        XCTAssertEqual(CAPTRuntimeStateSemantics.tone(for: "awaiting_verification"), .warning)
    }
}
