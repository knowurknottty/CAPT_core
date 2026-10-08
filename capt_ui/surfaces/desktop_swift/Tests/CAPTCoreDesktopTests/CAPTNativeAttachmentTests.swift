import XCTest
@testable import CAPTCoreDesktop

final class CAPTNativeAttachmentTests: XCTestCase {
    private func sandbox() throws -> URL {
        let folder = FileManager.default.temporaryDirectory
            .appendingPathComponent("capt-native-media-test-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        return folder
    }

    func testArbitraryBinaryFileIsStagedAndDigestBound() throws {
        let folder = try sandbox()
        defer { try? FileManager.default.removeItem(at: folder) }
        let source = folder.appendingPathComponent("unknown.oddextension")
        let input = Data((0..<2048).map { UInt8($0 % 251) })
        try input.write(to: source)
        let sessionID = UUID()
        let staged = try CAPTNativeAttachmentStager.stage(
            source: source, sessionID: sessionID,
            root: folder.appendingPathComponent("private")
        )
        XCTAssertEqual(staged.originalName, "unknown.oddextension")
        XCTAssertEqual(staged.kind, .binary)
        XCTAssertEqual(staged.sizeBytes, 2048)
        XCTAssertEqual(try Data(contentsOf: URL(fileURLWithPath: staged.stagedPath)), input)
        let atStaging = try FileManager.default.attributesOfItem(atPath: staged.stagedPath)
        XCTAssertEqual((atStaging[.posixPermissions] as? NSNumber)?.intValue, 0o600)
        try Data(repeating: 0, count: 2048).write(to: source)
        XCTAssertEqual(try Data(contentsOf: URL(fileURLWithPath: staged.stagedPath)), input)
        let decoded = try JSONDecoder().decode(
            CAPTNativeAttachment.self, from: JSONEncoder().encode(staged)
        )
        XCTAssertEqual(decoded, staged)
        try CAPTNativeAttachmentStager.discard(
            staged, sessionID: sessionID, root: folder.appendingPathComponent("private")
        )
        XCTAssertFalse(FileManager.default.fileExists(atPath: staged.stagedPath))
    }

    func testKindsAndSafetyGuards() throws {
        let folder = try sandbox()
        defer { try? FileManager.default.removeItem(at: folder) }
        let samples: [(String, CAPTNativeAttachment.Kind)] = [
            ("photo.jpg", .image),
            ("video.mp4", .video),
            ("sound.wav", .audio),
            ("document.pdf", .document),
            ("payload.xyznotreal", .binary),
        ]
        for (name, kind) in samples {
            let file = folder.appendingPathComponent(name)
            try Data("dummy".utf8).write(to: file)
            XCTAssertEqual(CAPTNativeAttachmentStager.kind(for: file), kind)
        }
        let real = folder.appendingPathComponent("real.bin")
        try Data(repeating: 7, count: 10).write(to: real)
        let link = folder.appendingPathComponent("symbolic.bin")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: real)
        XCTAssertThrowsError(try CAPTNativeAttachmentStager.stage(
            source: link, sessionID: UUID(), root: folder.appendingPathComponent("private")))
        XCTAssertThrowsError(try CAPTNativeAttachmentStager.stage(
            source: real, sessionID: UUID(), root: folder.appendingPathComponent("private"),
            maxBytes: 3))
    }

    func testCannotDeleteOutsidePrivateSession() throws {
        let folder = try sandbox()
        defer { try? FileManager.default.removeItem(at: folder) }
        let original = folder.appendingPathComponent("keep.bin")
        try Data("keep".utf8).write(to: original)
        let id = UUID()
        let forged = CAPTNativeAttachment(
            id: id, originalName: "keep.bin", stagedPath: original.path,
            sizeBytes: 4, sha256: "sha256:00", mediaType: "application/octet-stream",
            kind: .binary, admittedAt: Date()
        )
        XCTAssertThrowsError(try CAPTNativeAttachmentStager.discard(
            forged, sessionID: UUID(), root: folder.appendingPathComponent("private")))
        XCTAssertTrue(FileManager.default.fileExists(atPath: original.path))
    }
}


extension CAPTNativeAttachmentTests {
    func testChatCanPersistLocalAttachmentsButCannotPretendTheyWereSubmitted() throws {
        let sandbox = try sandbox()
        defer { try? FileManager.default.removeItem(at: sandbox) }
        let source = sandbox.appendingPathComponent("voice.m4a")
        try Data("sample audio bytes".utf8).write(to: source)
        var workspace = CAPTNativeChatWorkspace()
        let sid = workspace.newChat(provider: "openrouter", model: "any",
                                    targetRoot: "/tmp/repo")
        let attachment = try CAPTNativeAttachmentStager.stage(
            source: source, sessionID: sid,
            root: sandbox.appendingPathComponent("private")
        )
        XCTAssertTrue(workspace.addLocalAttachment(attachment, for: sid))
        XCTAssertNil(workspace.beginPrompt(
            "Analyze the audio now", provider: "openrouter", model: "any",
            targetRoot: "/tmp/repo", piRequestID: "pp-test-not-admitted"
        ), "Cannot silently omit selected local attachments from provider input")
        let original = try XCTUnwrap(workspace.session(sid))
        let restored = try JSONDecoder().decode(CAPTNativeSession.self,
                                 from: JSONEncoder().encode(original))
        XCTAssertEqual(restored.attachments, [attachment])
        XCTAssertEqual(workspace.removeLocalAttachment(attachment.id, from: sid), attachment)
        XCTAssertNotNil(workspace.beginPrompt(
            "Text-only prompt", provider: "openrouter", model: "any",
            targetRoot: "/tmp/repo", piRequestID: "pp-test-allowed"
        ))
        try CAPTNativeAttachmentStager.discard(
            attachment, sessionID: sid, root: sandbox.appendingPathComponent("private")
        )
    }
}
