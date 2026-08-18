import XCTest
@testable import CAPTCoreDesktop

final class CAPTRuntimeBootstrapperTests: XCTestCase {
    func testExplicitCAPTCLIWinsCandidateOrder() {
        let candidates = CAPTRuntimeBootstrapper.defaultCandidates(
            home: "/Users/tester",
            environment: ["CAPT_CLI": "/custom/capt"]
        )
        XCTAssertEqual(candidates.first, "/custom/capt")
        XCTAssertTrue(candidates.contains("/Users/tester/.capt/runtime-venv/bin/capt"))
    }

    func testPrivateRuntimeVenvIsDefaultFirstChoice() {
        let candidates = CAPTRuntimeBootstrapper.defaultCandidates(
            home: "/Users/tester", environment: [:]
        )
        XCTAssertEqual(candidates.first, "/Users/tester/.capt/runtime-venv/bin/capt")
    }
}
