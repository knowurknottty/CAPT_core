import XCTest
@testable import CAPTCoreDesktop

final class CAPTLiveRuntimeTests: XCTestCase {
    private func requireLive() throws {
        guard ProcessInfo.processInfo.environment["CAPT_LIVE_TEST"] == "1" else {
            throw XCTSkip("Set CAPT_LIVE_TEST=1 to exercise the real local runtime")
        }
    }

    func testRealRuntimeAuthApprovalDenialAndLocalInference() throws {
        try requireLive()
        let client = CAPTRuntimeClient()
        defer { client.disconnect() }

        let identity = try client.connect()
        let identityResult = identity["result"] as? [String: Any] ?? identity
        XCTAssertEqual(identityResult["integrity"] as? String, "ok")

        let capabilities = try client.query(op: "capabilities", payload: [:])
        let caps = capabilities["result"] as? [String: Any] ?? capabilities
        let commands = caps["commandOperations"] as? [String] ?? []
        XCTAssertTrue(commands.contains("request_model_prompt_approval"))
        XCTAssertTrue(commands.contains("run_approved_hermes_inspection"))

        let coordinator = CAPTChatCoordinator(client: client)
        let target = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("CAPT_core", isDirectory: true).path

        let denied = try coordinator.requestApproval(
            objective: "CAPT native denial probe. Do not execute.",
            targetRoot: target,
            provider: "ollama",
            model: "qwen3.5-defiant-fable:latest"
        )
        try coordinator.deny(denied)
        let deniedStateResponse = try client.query(
            op: "get_state",
            payload: ["streamId": "human_approval-" + denied.requestID]
        )
        let deniedState = deniedStateResponse["result"] as? [String: Any] ?? deniedStateResponse
        XCTAssertEqual(deniedState["decision"] as? String, "deny")
        XCTAssertNotEqual(deniedState["state"] as? String, "consumed")

        let nonce = UUID().uuidString.lowercased().replacingOccurrences(of: "-", with: "")
        let marker = "CAPT-NATIVE-" + String(nonce.prefix(8))
        let pending = try coordinator.requestApproval(
            objective: "Return token \(marker). READ-ONLY. Do not modify files.",
            targetRoot: target,
            provider: "ollama",
            model: "qwen3.5-defiant-fable:latest"
        )
        let result = try coordinator.approveAndRun(pending)

        XCTAssertFalse(result.text.isEmpty)
        XCTAssertEqual(result.taskState, "awaiting_verification")
    }
}
