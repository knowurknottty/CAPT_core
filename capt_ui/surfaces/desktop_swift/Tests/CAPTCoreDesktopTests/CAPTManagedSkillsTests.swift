import XCTest
@testable import CAPTCoreDesktop

final class CAPTManagedSkillsTests: XCTestCase {
    func testSnapshotDecodesMetadataWithoutInstructionBodies() throws {
        let snapshot = try CAPTManagedSkillSnapshot(dictionary: [
            "installed": true,
            "packRoot": "/state/skills/ultimate",
            "packName": "ultimate",
            "packVersion": "managed-1",
            "manifestDigest": "sha256:manifest",
            "trust": "managed_local",
            "skills": [[
                "name": "reviewer",
                "description": "Review code carefully",
                "version": "1.2.3",
                "contentDigest": "sha256:skill",
                "triggers": ["review code"],
            ]],
        ])
        XCTAssertTrue(snapshot.installed)
        XCTAssertEqual(snapshot.skills.count, 1)
        XCTAssertEqual(snapshot.skills[0].name, "reviewer")
        XCTAssertEqual(snapshot.skills[0].triggers, ["review code"])
    }

    func testSnapshotRequiresPackIdentity() {
        XCTAssertThrowsError(try CAPTManagedSkillSnapshot(dictionary: ["installed": false]))
    }
    func testMutationResultDecodesAuthoritativePackReceipt() throws {
        let result = try CAPTManagedSkillMutationResult(dictionary: [
            "installed": true,
            "packRoot": "/state/skills/ultimate",
            "packName": "ultimate",
            "packVersion": "managed-1",
            "manifestDigest": "sha256:manifest",
            "skillNames": ["capt-ui-review", "reviewer"],
        ])
        XCTAssertTrue(result.installed)
        XCTAssertEqual(result.packName, "ultimate")
        XCTAssertEqual(result.skillNames, ["capt-ui-review", "reviewer"])
    }

}
