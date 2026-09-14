import XCTest
@testable import CAPTCoreDesktop

final class CAPTRuntimeProfileTests: XCTestCase {
    private let home = "/Users/tester"

    func testBundleIdentitySelectsDistinctDefaultStateRoots() {
        let standard = CAPTRuntimeProfile.resolve(
            home: home, environment: [:], bundleIdentifier: "com.inversionlabs.capt"
        )
        let labs = CAPTRuntimeProfile.resolve(
            home: home, environment: [:], bundleIdentifier: CAPTRuntimeProfile.labsBundleIdentifier
        )
        XCTAssertEqual(standard.stateDirectory, "/Users/tester/.capt")
        XCTAssertEqual(labs.stateDirectory, "/Users/tester/.capt-inversion-labs")
        XCTAssertNotEqual(standard.stateDirectory, labs.stateDirectory)
    }

    func testExplicitStateOverrideWinsForEitherProduct() {
        let profile = CAPTRuntimeProfile.resolve(
            home: home,
            environment: ["CAPT_STATE_DIR": "/tmp/capt-explicit"],
            bundleIdentifier: CAPTRuntimeProfile.labsBundleIdentifier
        )
        XCTAssertEqual(profile.stateDirectory, "/tmp/capt-explicit")
        XCTAssertEqual(profile.runtimeExecutableCandidates.first, "/tmp/capt-explicit/runtime-venv/bin/capt")
        XCTAssertEqual(profile.operatorExecutableCandidates.first, "/tmp/capt-explicit/runtime-venv/bin/capt-ui")
    }

    func testProfileBindsClientBootstrapOperatorAndSessionState() {
        let profile = CAPTRuntimeProfile.resolve(
            home: home, environment: [:], bundleIdentifier: CAPTRuntimeProfile.labsBundleIdentifier
        )
        let client = CAPTRuntimeClient(profile: profile)
        let bootstrapper = CAPTRuntimeBootstrapper(profile: profile)
        let operatorCLI = CAPTOperatorCLI(profile: profile)
        let sessionURL = CAPTEncryptedSessionStore.defaultFileURL(profile: profile)

        XCTAssertEqual(client.socketPath, "/Users/tester/.capt-inversion-labs/runtime.sock")
        XCTAssertEqual(client.tokenPath, "/Users/tester/.capt-inversion-labs/runtime.token")
        XCTAssertEqual(bootstrapper.stateDirectory, profile.stateDirectory)
        XCTAssertEqual(bootstrapper.executableCandidates.first, "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt")
        XCTAssertEqual(operatorCLI.executablePath, "/Users/tester/.capt-inversion-labs/runtime-venv/bin/capt-ui")
        XCTAssertEqual(sessionURL.path, "/Users/tester/.capt-inversion-labs/ui/classic_native_sessions.enc")
    }
}
