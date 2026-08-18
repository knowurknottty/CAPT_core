import XCTest
@testable import CAPTCoreDesktop

final class MockRuntimeClient: CAPTRuntimeCommanding {
    var calls: [(String, [String: Any])] = []
    var responses: [String: [String: Any]] = [:]

    func connect() throws -> [String: Any] { [:] }
    func disconnect() {}
    func query(op: String, payload: [String: Any]) throws -> [String: Any] {
        calls.append((op, payload))
        return responses["query:" + op] ?? [:]
    }
    func command(op: String, payload: [String: Any], idempotencyKey: String?) throws -> [String: Any] {
        calls.append((op, payload))
        return responses[op] ?? [:]
    }
}

final class CAPTChatCoordinatorTests: XCTestCase {
    private func approvalResponse() -> [String: Any] {
        ["result": [
            "requestId": "approval-1", "missionId": "mission-1",
            "taskId": "task-1", "driverRunId": "run-1",
            "promptAssemblyDigest": "sha256:abc"
        ]]
    }

    func testRequestCreatesPendingApprovalWithoutDispatch() throws {
        let client = MockRuntimeClient()
        client.responses["request_model_prompt_approval"] = approvalResponse()
        let coordinator = CAPTChatCoordinator(client: client)

        let pending = try coordinator.requestApproval(
            objective: "inspect repo", targetRoot: "/repo",
            provider: "ollama", model: "model-a"
        )

        XCTAssertEqual(pending.requestID, "approval-1")
        XCTAssertEqual(client.calls.map(\.0), ["request_model_prompt_approval"])
        XCTAssertFalse(client.calls.map(\.0).contains("run_approved_hermes_inspection"))
    }

    func testDenyNeverDispatchesModel() throws {
        let client = MockRuntimeClient()
        client.responses["request_model_prompt_approval"] = approvalResponse()
        client.responses["submit_approval_decision"] = ["status": "accepted"]
        let coordinator = CAPTChatCoordinator(client: client)
        let pending = try coordinator.requestApproval(
            objective: "inspect repo", targetRoot: "/repo",
            provider: "ollama", model: "model-a"
        )
        try coordinator.deny(pending)
        XCTAssertEqual(client.calls.map(\.0), [
            "request_model_prompt_approval", "submit_approval_decision"
        ])
    }

    func testApproveRunsExactBoundExecutionAndExtractsObservation() throws {
        let client = MockRuntimeClient()
        client.responses["request_model_prompt_approval"] = approvalResponse()
        client.responses["submit_approval_decision"] = ["status": "accepted"]
        client.responses["run_approved_hermes_inspection"] = [
            "status": "accepted",
            "observations": [["content": "CAPT says hello"]]
        ]
        client.responses["query:get_state"] = [
            "ok": true, "result": ["state": "awaiting_verification"]
        ]
        let coordinator = CAPTChatCoordinator(client: client)
        let pending = try coordinator.requestApproval(
            objective: "inspect repo", targetRoot: "/repo",
            provider: "ollama", model: "model-a"
        )

        let result = try coordinator.approveAndRun(pending)

        XCTAssertEqual(result.text, "CAPT says hello")
        XCTAssertEqual(result.taskState, "awaiting_verification")
        XCTAssertEqual(client.calls.map(\.0), [
            "request_model_prompt_approval", "submit_approval_decision",
            "run_approved_hermes_inspection", "get_state"
        ])
        let runPayload = client.calls[2].1
        XCTAssertEqual(runPayload["approvalRequestId"] as? String, "approval-1")
        XCTAssertEqual(runPayload["driverRunId"] as? String, "run-1")
    }
}

extension CAPTChatCoordinatorTests {
    func testContinuationPassesMissionWithoutReusingTaskIdentity() throws {
        let client = MockRuntimeClient()
        client.responses["request_model_prompt_approval"] = approvalResponse()
        let coordinator = CAPTChatCoordinator(client: client)

        _ = try coordinator.requestApproval(
            objective: "continue", targetRoot: "/repo",
            provider: "ollama", model: "model-b",
            missionID: "mission-1"
        )

        let payload = client.calls[0].1
        XCTAssertEqual(payload["missionId"] as? String, "mission-1")
        XCTAssertNil(payload["taskId"])
    }
}

extension CAPTChatCoordinatorTests {
    func testStructuredRuntimeRejectionSurfacesCodeAndDetail() throws {
        let client = MockRuntimeClient()
        client.responses["request_model_prompt_approval"] = approvalResponse()
        client.responses["submit_approval_decision"] = ["status": "accepted"]
        client.responses["run_approved_hermes_inspection"] = [
            "status": "rejected", "classification": "authority",
            "error": ["code": "EXAMPLE_REJECTION", "message": "authority refused"],
            "detail": "specific deterministic reason"
        ]
        let coordinator = CAPTChatCoordinator(client: client)
        let pending = try coordinator.requestApproval(
            objective: "inspect", targetRoot: "/repo",
            provider: "ollama", model: "model-a"
        )

        XCTAssertThrowsError(try coordinator.approveAndRun(pending)) { error in
            let text = error.localizedDescription
            XCTAssertTrue(text.contains("EXAMPLE_REJECTION"))
            XCTAssertTrue(text.contains("specific deterministic reason"))
        }
    }
}
