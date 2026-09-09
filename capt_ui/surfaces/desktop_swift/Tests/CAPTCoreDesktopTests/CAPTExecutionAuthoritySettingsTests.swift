import XCTest
@testable import CAPTCoreDesktop

final class CAPTExecutionAuthoritySettingsTests: XCTestCase {
    func testDefaultProfileIsProjectScopedReadOnlyLocalProvider() {
        let settings = CAPTExecutionAuthoritySettings.default
        XCTAssertEqual(settings.filesystemScope, .project)
        XCTAssertFalse(settings.fileMutationAllowed)
        XCTAssertFalse(settings.shellAccessAllowed)
        XCTAssertEqual(settings.providerNetwork, .localOnly)
        XCTAssertFalse(settings.remotePromptCompilationAllowed)
        XCTAssertEqual(settings.effectiveFilesystemRoot(projectRoot: "/repo"), "/repo")
        XCTAssertFalse(settings.isHighRisk)
    }

    func testCustomAndFullFilesystemRootsAreExplicit() {
        var settings = CAPTExecutionAuthoritySettings.default
        settings.filesystemScope = .custom
        settings.customFilesystemRoot = " /workspace/selected "
        XCTAssertEqual(
            settings.effectiveFilesystemRoot(projectRoot: "/repo"),
            "/workspace/selected"
        )

        settings.filesystemScope = .full
        XCTAssertEqual(settings.effectiveFilesystemRoot(projectRoot: "/repo"), "/")
        XCTAssertTrue(settings.isHighRisk)
    }

    func testCustomScopeWithoutRootIsIncompleteInsteadOfWidening() {
        var settings = CAPTExecutionAuthoritySettings.default
        settings.filesystemScope = .custom
        settings.customFilesystemRoot = "   "
        XCTAssertNil(settings.effectiveFilesystemRoot(projectRoot: "/repo"))
    }

    func testRiskReflectsMutationShellOrRemoteProvider() {
        var settings = CAPTExecutionAuthoritySettings.default
        settings.fileMutationAllowed = true
        XCTAssertTrue(settings.isHighRisk)

        settings = .default
        settings.shellAccessAllowed = true
        XCTAssertTrue(settings.isHighRisk)

        settings = .default
        settings.providerNetwork = .remoteAllowed
        XCTAssertTrue(settings.isHighRisk)
    }

    func testProfileCodableRoundTripPreservesAuthorityIntent() throws {
        let settings = CAPTExecutionAuthoritySettings(
            filesystemScope: .custom,
            customFilesystemRoot: "/workspace",
            fileMutationAllowed: true,
            shellAccessAllowed: true,
            providerNetwork: .remoteAllowed,
            remotePromptCompilationAllowed: true
        )
        let data = try JSONEncoder().encode(settings)
        XCTAssertEqual(try JSONDecoder().decode(CAPTExecutionAuthoritySettings.self, from: data), settings)
    }
}
