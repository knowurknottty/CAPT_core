import XCTest
@testable import CAPTCoreDesktop

final class CAPTPIRestorationTests: XCTestCase {
    func testStableAttemptIdentitySurvivesSessionSerialization() throws {
        var workspace = CAPTNativeChatWorkspace()
        let sid = workspace.newChat(provider: "openrouter",
                                    model: "z-ai/glm-5.3-flash",
                                    targetRoot: "/tmp/repo")
        let requestID = "pp-native-11111111-2222-3333-4444-555555555555"
        XCTAssertEqual(workspace.beginPrompt("Review source", provider: "openrouter",
                                            model: "z-ai/glm-5.3-flash",
                                            targetRoot: "/tmp/repo",
                                            piRequestID: requestID), sid)
        let original = try XCTUnwrap(workspace.session(sid))
        XCTAssertEqual(original.piRequestID, requestID)
        let restored = try JSONDecoder().decode(CAPTNativeSession.self,
                                from: JSONEncoder().encode(original))
        XCTAssertEqual(restored.piRequestID, requestID)
        XCTAssertNil(restored.promptProposal)
        let restarted = CAPTNativeChatWorkspace(sessions: [restored], activeSessionID: sid)
        XCTAssertEqual(restarted.activeSession?.piRequestID, requestID)
        XCTAssertNil(restarted.activePromptProposal)
    }

    func testLegacySessionDecodesWithoutAttemptIdentity() throws {
        let session = CAPTNativeSession(
            title: "Legacy chat", provider: "local", model: "qwen", targetRoot: "/tmp"
        )
        var json = try XCTUnwrap(JSONSerialization.jsonObject(
            with: JSONEncoder().encode(session)) as? [String: Any])
        json.removeValue(forKey: "piRequestID")
        let data = try JSONSerialization.data(withJSONObject: json)
        let decoded = try JSONDecoder().decode(CAPTNativeSession.self, from: data)
        XCTAssertNil(decoded.piRequestID)
    }
}
