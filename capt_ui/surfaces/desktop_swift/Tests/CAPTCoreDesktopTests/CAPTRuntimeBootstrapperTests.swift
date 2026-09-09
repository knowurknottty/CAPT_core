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
    func testChildEnvironmentScrubsCallerPythonImportOverrides() {
        let sanitized = CAPTRuntimeBootstrapper.sanitizedChildEnvironment([
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": "/tmp/stale-core",
            "PYTHONHOME": "/tmp/stale-python",
            "CAPT_CLI": "/custom/stale/capt",
            "CAPT_UI": "/custom/stale/capt-ui",
        ])
        XCTAssertNil(sanitized["PYTHONPATH"])
        XCTAssertNil(sanitized["PYTHONHOME"])
        XCTAssertNil(sanitized["CAPT_CLI"])
        XCTAssertNil(sanitized["CAPT_UI"])
        XCTAssertEqual(sanitized["PATH"], "/usr/bin:/bin")
    }

    func testOperatorCLIUsesSanitizedChildEnvironment() {
        let cli = CAPTOperatorCLI(
            executablePath: "/tmp/capt-ui",
            environment: [
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": "/tmp/stale-core",
                "PYTHONHOME": "/tmp/stale-python",
            ]
        )
        XCTAssertNil(cli.processEnvironment["PYTHONPATH"])
        XCTAssertNil(cli.processEnvironment["PYTHONHOME"])
        XCTAssertEqual(cli.processEnvironment["PATH"], "/usr/bin:/bin")
    }
    func testExplicitStateDirectoryOwnsRuntimeDespiteAmbientCLIOverride() {
        let bootstrapper = CAPTRuntimeBootstrapper(
            stateDirectory: "/tmp/capt-isolated",
            environment: ["CAPT_CLI": "/custom/stale/capt"]
        )
        XCTAssertEqual(
            bootstrapper.executableCandidates.first,
            "/tmp/capt-isolated/runtime-venv/bin/capt"
        )
        XCTAssertFalse(bootstrapper.executableCandidates.contains("/custom/stale/capt"))
    }

}
