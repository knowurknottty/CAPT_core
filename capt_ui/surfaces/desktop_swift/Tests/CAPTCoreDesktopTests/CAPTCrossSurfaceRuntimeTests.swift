import Foundation
import XCTest
@testable import CAPTCoreDesktop

final class CAPTCrossSurfaceRuntimeTests: XCTestCase {
    private func requireAcceptance(stage: String) throws {
        let env = ProcessInfo.processInfo.environment
        guard env["CAPT_CROSS_SURFACE_TEST"] == "1" else {
            throw XCTSkip("Set CAPT_CROSS_SURFACE_TEST=1 for macOS↔Runtime↔MCP acceptance")
        }
        guard env["CAPT_CROSS_SURFACE_STAGE"] == stage else {
            throw XCTSkip("Cross-surface stage \(stage) is not active")
        }
    }

    private func requireEnv(_ key: String) throws -> String {
        let value = ProcessInfo.processInfo.environment[key] ?? ""
        return try XCTUnwrap(value.isEmpty ? nil : value, "Missing \(key)")
    }

    private func state(_ client: CAPTRuntimeClient, streamID: String) throws -> [String: Any] {
        let response = try client.query(op: "get_state", payload: ["streamId": streamID])
        return response["result"] as? [String: Any] ?? response
    }

    private func writeJSON(_ payload: [String: Any], path: String) throws {
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        try data.write(to: URL(fileURLWithPath: path), options: .atomic)
    }

    func testNativeObservesAndDeniesMCPApproval() throws {
        try requireAcceptance(stage: "deny")
        let requestID = try requireEnv("CAPT_CROSS_SURFACE_REQUEST_ID")
        let missionID = try requireEnv("CAPT_CROSS_SURFACE_MISSION_ID")
        let taskID = try requireEnv("CAPT_CROSS_SURFACE_TASK_ID")
        let client = CAPTRuntimeClient()
        defer { client.disconnect() }
        _ = try client.connect()

        let pending = try state(client, streamID: "human_approval-" + requestID)
        XCTAssertEqual(pending["state"] as? String, "requested")
        XCTAssertEqual(pending["missionId"] as? String, missionID)
        XCTAssertEqual(pending["taskId"] as? String, taskID)

        let denial = try client.command(
            op: "submit_approval_decision",
            payload: ["requestId": requestID, "decision": "deny",
                      "note": "Denied by native cross-surface acceptance"],
            idempotencyKey: "cross-native-deny-" + requestID
        )
        XCTAssertEqual(denial["status"] as? String, "accepted")
        let denied = try state(client, streamID: "human_approval-" + requestID)
        XCTAssertEqual(denied["decision"] as? String, "deny")
        XCTAssertNotEqual(denied["state"] as? String, "consumed")
    }

    func testNativeCreatesFreshApprovalForMCPExecution() throws {
        try requireAcceptance(stage: "prepare")
        let targetRoot = try requireEnv("CAPT_CROSS_SURFACE_TARGET_ROOT")
        let provider = try requireEnv("CAPT_CROSS_SURFACE_PROVIDER")
        let model = try requireEnv("CAPT_CROSS_SURFACE_MODEL")
        let objective = try requireEnv("CAPT_CROSS_SURFACE_OBJECTIVE")
        let resultFile = try requireEnv("CAPT_CROSS_SURFACE_RESULT_FILE")
        let client = CAPTRuntimeClient()
        defer { client.disconnect() }
        _ = try client.connect()

        let pending = try CAPTChatCoordinator(client: client).requestApproval(
            objective: objective, targetRoot: targetRoot,
            provider: provider, model: model
        )
        try writeJSON([
            "requestId": pending.requestID,
            "missionId": pending.missionID,
            "taskId": pending.taskID,
            "driverRunId": pending.driverRunID,
            "promptAssemblyDigest": pending.promptAssemblyDigest,
        ], path: resultFile)

        let approval = try state(client, streamID: "human_approval-" + pending.requestID)
        XCTAssertEqual(approval["state"] as? String, "requested")
    }

    func testNativeObservesMCPExecutionAuthoritatively() throws {
        try requireAcceptance(stage: "observe")
        let requestID = try requireEnv("CAPT_CROSS_SURFACE_REQUEST_ID")
        let taskID = try requireEnv("CAPT_CROSS_SURFACE_TASK_ID")
        let driverRunID = try requireEnv("CAPT_CROSS_SURFACE_DRIVER_RUN_ID")
        let client = CAPTRuntimeClient()
        defer { client.disconnect() }
        let identity = try client.connect()
        let identityResult = identity["result"] as? [String: Any] ?? identity
        XCTAssertEqual(identityResult["integrity"] as? String, "ok")

        let approval = try state(client, streamID: "human_approval-" + requestID)
        let task = try state(client, streamID: "task-" + taskID)
        let driver = try state(client, streamID: "driverrun-" + driverRunID)
        XCTAssertEqual(approval["state"] as? String, "consumed")
        XCTAssertEqual(task["state"] as? String, "awaiting_verification")
        XCTAssertEqual(driver["state"] as? String, "completed")
        XCTAssertNil(task["verificationId"])
    }
}
