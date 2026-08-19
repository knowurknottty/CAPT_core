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
    func testRealOperatorPreferencesAndGovernedCheckpoint() throws {
        try requireLive()
        let operatorCLI = CAPTOperatorCLI()
        let providers = try operatorCLI.providers()
        let models = try operatorCLI.models()
        XCTAssertTrue(providers.contains(where: { $0.id == "ollama" }))
        XCTAssertFalse(models.active.isEmpty)
        let activatedProviders = try operatorCLI.activateProvider("ollama")
        XCTAssertTrue(activatedProviders.contains(where: { $0.id == "ollama" && $0.selected }))
        if let defaultModel = models.defaultSelection?.model {
            let after = try operatorCLI.setDefaultModel(providerID: "ollama", modelID: defaultModel)
            XCTAssertEqual(after.defaultSelection?.model, defaultModel)
        }

        let client = CAPTRuntimeClient()
        defer { client.disconnect() }
        _ = try client.connect()
        let receipt = try client.command(
            op: "checkpoint_runtime", payload: [:],
            idempotencyKey: "native-swift-checkpoint-" + UUID().uuidString.lowercased()
        )
        let checkpoint = try XCTUnwrap(CAPTRuntimeControlProjection.checkpoint(receipt))
        XCTAssertEqual(checkpoint.status, "accepted")
        XCTAssertTrue(checkpoint.checkpointID.hasPrefix("cp-"))
        XCTAssertFalse(checkpoint.integrityDigest.isEmpty)
    }

}

extension CAPTLiveRuntimeTests {
    func testRealNativeConversationUsesSameMissionDistinctSuccessorTasks() throws {
        try requireLive()
        let client = CAPTRuntimeClient()
        defer { client.disconnect() }
        _ = try client.connect()
        let coordinator = CAPTChatCoordinator(client: client)
        let target = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("CAPT_core", isDirectory: true).path

        let first = try coordinator.requestApproval(
            objective: "Native continuity turn A. READ-ONLY.",
            targetRoot: target, provider: "ollama",
            model: "qwen3.5-defiant-fable:latest"
        )
        let firstResult = try coordinator.approveAndRun(first)
        XCTAssertEqual(firstResult.taskState, "awaiting_verification")

        let second = try coordinator.requestApproval(
            objective: "Native continuity turn B. READ-ONLY.",
            targetRoot: target, provider: "ollama",
            model: "ornith-1.0-9b:latest", missionID: first.missionID
        )
        XCTAssertEqual(second.missionID, first.missionID)
        XCTAssertNotEqual(second.taskID, first.taskID)
        let secondResult = try coordinator.approveAndRun(second)
        XCTAssertEqual(secondResult.taskState, "awaiting_verification")

        let missionEvents = try client.query(
            op: "get_stream_events", payload: ["streamId": "mission-" + first.missionID]
        )["result"] as? [[String: Any]] ?? []
        XCTAssertEqual(missionEvents.filter { $0["eventType"] as? String == "MissionCreated" }.count, 1)
    }
}

extension CAPTLiveRuntimeTests {
    func testRealShutdownThenBootstrapReconnectsSameLedger() throws {
        try requireLive()
        let client = CAPTRuntimeClient()
        let identity = try client.connect()
        let before = (identity["result"] as? [String: Any] ?? identity)["headSequence"] as? Int ?? 0

        let receipt = try client.command(
            op: "shutdown", payload: [:],
            idempotencyKey: "native-live-shutdown-" + UUID().uuidString.lowercased()
        )
        XCTAssertEqual(receipt["status"] as? String, "accepted")
        client.disconnect()

        Thread.sleep(forTimeInterval: 0.5)
        let bootstrapper = CAPTRuntimeBootstrapper()
        try bootstrapper.start()
        let restarted = CAPTRuntimeClient()
        defer { restarted.disconnect() }
        let afterIdentity = try restarted.connect()
        let after = (afterIdentity["result"] as? [String: Any] ?? afterIdentity)
        XCTAssertEqual(after["integrity"] as? String, "ok")
        XCTAssertGreaterThanOrEqual(after["headSequence"] as? Int ?? 0, before)
    }
}
