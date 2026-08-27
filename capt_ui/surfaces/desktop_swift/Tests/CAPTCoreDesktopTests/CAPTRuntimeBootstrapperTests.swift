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

extension CAPTRuntimeBootstrapperTests {
    func testLabsProfileDefaultsStateToLabsRoot() {
        let profile = CAPTRuntimeProfile.resolve(
            home: "/Users/tester",
            environment: [:],
            bundleIdentifier: "com.inversionlabs.capt.lab"
        )
        XCTAssertEqual(profile.stateDirectory, "/Users/tester/.capt-inversion-labs")
        XCTAssertEqual(profile.executableCandidates.first, "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt")
        XCTAssertEqual(profile.operatorExecutableCandidates.first, "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt-ui")
    }

    func testExplicitDogfoodStateDoesNotOwnOperatorExecutableWhenStableCLIIsProvided() {
        let profile = CAPTRuntimeProfile.resolve(
            home: "/Users/tester",
            environment: [
                "CAPT_STATE_DIR": "/tmp/labs-dogfood-state",
                "CAPT_CLI": "/Users/tester/.capt/runtime-venv/bin/capt",
            ],
            bundleIdentifier: "com.inversionlabs.capt.lab"
        )
        XCTAssertEqual(profile.stateDirectory, "/tmp/labs-dogfood-state")
        XCTAssertEqual(profile.executableCandidates.first, "/Users/tester/.capt/runtime-venv/bin/capt")
        XCTAssertEqual(profile.operatorExecutableCandidates.first, "/Users/tester/.capt/runtime-venv/bin/capt-ui")
        XCTAssertTrue(profile.operatorExecutableCandidates.contains("/tmp/labs-dogfood-state/runtime-venv/bin/capt-ui"))
        XCTAssertTrue(profile.operatorExecutableCandidates.contains("/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt-ui"))
    }

    func testOperatorExecutableResolutionSkipsMissingDogfoodBinary() {
        let candidates = [
            "/tmp/labs-dogfood-state/runtime-venv/bin/capt-ui",
            "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt-ui",
        ]
        let resolved = CAPTRuntimeProfile.resolveExecutable(
            candidates: candidates,
            fileExists: { $0 == "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt-ui" }
        )
        XCTAssertEqual(resolved, "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt-ui")
    }

    func testExplicitStateDirectoryWinsForLabsBootstrapper() {
        let bootstrapper = CAPTRuntimeBootstrapper(
            stateDirectory: "/tmp/labs-dogfood-state",
            environment: ["CAPT_CLI": "/Users/tester/.capt/runtime-venv/bin/capt"],
            bundleIdentifier: "com.inversionlabs.capt.lab"
        )
        XCTAssertEqual(bootstrapper.stateDirectory, "/tmp/labs-dogfood-state")
        XCTAssertEqual(bootstrapper.executableCandidates.first, "/Users/tester/.capt/runtime-venv/bin/capt")
    }
}
