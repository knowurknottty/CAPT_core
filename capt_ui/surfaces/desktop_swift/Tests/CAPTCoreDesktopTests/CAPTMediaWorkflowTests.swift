import XCTest
@testable import CAPTCoreDesktop

final class CAPTMediaWorkflowTests: XCTestCase {
    private func route(_ operation: String) throws -> CAPTMediaRouteDescriptor {
        try CAPTMediaRouteDescriptor(dictionary: [
            "adapterId": "media-" + operation,
            "provider": "mock", "model": "model",
            "operation": operation, "transport": "json",
            "mediaTypes": [operation == "video_generate" ? "video/mp4" : "image/png"],
            "maximumPriceUSD": 0.50
        ])
    }

    private func attachment(kind: CAPTNativeAttachment.Kind) -> CAPTNativeAttachment {
        CAPTNativeAttachment(
            id: UUID(), originalName: "fixture", stagedPath: "/tmp/no-network",
            sizeBytes: 10, sha256: "sha256:" + String(repeating: "0", count: 64),
            mediaType: "image/png", kind: kind, admittedAt: Date()
        )
    }

    func testGeminiInlineDocumentAndVideoNeedMatchingAttachment() throws {
        let pdf = try route("document_input")
        let video = try route("video_input")
        let file = CAPTNativeAttachment(
            id: UUID(), originalName: "readme.pdf", stagedPath: "/tmp/pdf",
            sizeBytes: 100, sha256: "sha256:" + String(repeating: "0", count: 64),
            mediaType: "application/pdf", kind: .document, admittedAt: Date())
        let clip = CAPTNativeAttachment(
            id: UUID(), originalName: "clip.mp4", stagedPath: "/tmp/video",
            sizeBytes: 100, sha256: "sha256:" + String(repeating: "0", count: 64),
            mediaType: "video/mp4", kind: .video, admittedAt: Date())
        XCTAssertTrue(pdf.supports([file]))
        XCTAssertTrue(video.supports([clip]))
        XCTAssertFalse(pdf.supports([clip]))
        XCTAssertFalse(video.supports([file]))
        XCTAssertFalse(pdf.supports([]))
        XCTAssertFalse(video.supports([clip, file]))
    }

    func testCapabilitiesRequireExactFileModality() throws {
        let vision = try route("image_input")
        let generate = try route("image_generate")
        let image = attachment(kind: .image)
        XCTAssertTrue(vision.supports([image]))
        XCTAssertFalse(vision.supports([]))
        XCTAssertFalse(vision.supports([attachment(kind: .audio)]))
        XCTAssertFalse(generate.supports([image]))
        XCTAssertTrue(generate.supports([]))
    }

    func testBoundMediaApprovalSurvivesEncryptedSessionSerialization() throws {
        var workspace = CAPTNativeChatWorkspace()
        let sessionID = workspace.newChat(
            provider: "mock", model: "model", targetRoot: "/tmp/project"
        )
        XCTAssertTrue(workspace.bindMediaApproval(
            requestID: "approval-media-0123456789abcdef",
            driverRunID: "dr-media-0123456789abcdef", for: sessionID
        ))
        XCTAssertFalse(workspace.bindMediaApproval(
            requestID: "approval-media-second",
            driverRunID: "dr-media-second", for: sessionID
        ))
        let saved = try XCTUnwrap(workspace.session(sessionID))
        let restored = try JSONDecoder().decode(
            CAPTNativeSession.self, from: JSONEncoder().encode(saved)
        )
        XCTAssertEqual(restored.mediaApprovalRequestID, "approval-media-0123456789abcdef")
        XCTAssertEqual(restored.mediaDriverRunID, "dr-media-0123456789abcdef")
    }

    func testMediaArtifactCandidateDoesNotClaimVerificationAndDoesNotDuplicate() {
        var workspace = CAPTNativeChatWorkspace()
        let sessionID = workspace.newChat(
            provider: "mock", model: "model", targetRoot: "/tmp/project"
        )
        let receipt: [String: Any] = [
            "driverRunId": "dr-media-0123456789abcdef",
            "state": "completed",
            "artifactCandidate": [
                "artifactPath": "/tmp/fake.png",
                "artifactDigest": "sha256:" + String(repeating: "0", count: 64),
                "mediaType": "image/png"
            ]
        ]
        workspace.addMediaResult(receipt, for: sessionID)
        workspace.addMediaResult(receipt, for: sessionID)
        let session = workspace.session(sessionID)!
        let mediaMessages = session.messages.filter { $0.authorityState?.hasPrefix("unverified_media_") == true }
        XCTAssertEqual(mediaMessages.count, 1)
        XCTAssertTrue(mediaMessages[0].text.contains("independent verification"))
    }

    func testTextMediaResultIsVisibleButNotCertified() {
        var workspace = CAPTNativeChatWorkspace()
        let sessionID = workspace.newChat(
            provider: "mock", model: "model", targetRoot: "/tmp/project"
        )
        workspace.addMediaResult([
            "driverRunId": "dr-media-text-12345678",
            "state": "completed",
            "resultText": "The photograph shows a mountain",
            "artifactCandidate": [:]
        ], for: sessionID)
        XCTAssertEqual(workspace.session(sessionID)?.messages.last?.text,
                       "The photograph shows a mountain")
        XCTAssertEqual(workspace.session(sessionID)?.messages.last?.authorityState,
                       "unverified_media_dr-media-text-12345678")
    }
}
