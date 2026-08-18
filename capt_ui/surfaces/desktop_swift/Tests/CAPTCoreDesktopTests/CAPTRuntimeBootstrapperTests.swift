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

extension CAPTRuntimeBootstrapperTests {
    func testCustomStateDirectoryOwnRuntimeVenvIsFirstCandidate() {
        let bootstrapper = CAPTRuntimeBootstrapper(
            stateDirectory: "/Users/tester/.capt-inversion-labs",
            environment: [:]
        )
        XCTAssertEqual(
            bootstrapper.executableCandidates.first,
            "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt"
        )
    }

    func testOperatorCLIStoresCustomStateDirectoryForChildEnvironment() {
        let cli = CAPTOperatorCLI(
            executablePath: "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt-ui",
            stateDirectory: "/Users/tester/.capt-inversion-labs"
        )
        XCTAssertEqual(cli.stateDirectory, "/Users/tester/.capt-inversion-labs")
    }
}
