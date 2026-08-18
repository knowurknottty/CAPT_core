import Foundation

public struct CAPTExecutionResult: Equatable {
    public let text: String
    public let taskState: String

    public init(text: String, taskState: String) {
        self.text = text
        self.taskState = taskState
    }
}

public final class CAPTChatCoordinator {
    private let client: CAPTRuntimeCommanding

    public init(client: CAPTRuntimeCommanding) {
        self.client = client
    }

    public func requestApproval(
        objective: String,
        targetRoot: String,
        provider: String,
        model: String,
        missionID: String? = nil
    ) throws -> CAPTPendingApproval {
        var payload: [String: Any] = [
            "objective": objective,
            "targetRoot": targetRoot,
            "provider": provider,
            "model": model,
            "requestedContextBudget": 32_000,
            "responseMode": "SPOCK",
            "promptEnhancement": "OFF",
            "humanVerificationRequired": true,
        ]
        if let missionID, !missionID.isEmpty { payload["missionId"] = missionID }
        let response = try client.command(
            op: "request_model_prompt_approval",
            payload: payload,
            idempotencyKey: "native-approval-" + UUID().uuidString.lowercased()
        )
        try Self.ensureAcceptedOrApplied(response)
        guard let result = response["result"] as? [String: Any] else {
            throw CAPTRuntimeClientError.malformedResponse("approval result missing")
        }
        let requestID = try Self.requireString("requestId", from: result)
        let missionID = try Self.requireString("missionId", from: result)
        let taskID = try Self.requireString("taskId", from: result)
        let driverRunID = try Self.requireString("driverRunId", from: result)
        let digest = try Self.requireString("promptAssemblyDigest", from: result)
        let expiresAt = (result["expiresAt"] as? String).flatMap(Self.parseTimestamp)
        return CAPTPendingApproval(
            requestID: requestID,
            missionID: missionID,
            taskID: taskID,
            driverRunID: driverRunID,
            objective: objective,
            targetRoot: targetRoot,
            provider: provider,
            model: model,
            promptAssemblyDigest: digest,
            expiresAt: expiresAt
        )
    }

    public func deny(_ pending: CAPTPendingApproval) throws {
        let response = try client.command(
            op: "submit_approval_decision",
            payload: [
                "requestId": pending.requestID,
                "decision": "deny",
                "note": "Denied from CAPT native macOS surface",
            ],
            idempotencyKey: "native-deny-" + pending.requestID
        )
        try Self.ensureAcceptedOrApplied(response)
    }

    public func approveAndRun(_ pending: CAPTPendingApproval) throws -> CAPTExecutionResult {
        let decision = try client.command(
            op: "submit_approval_decision",
            payload: [
                "requestId": pending.requestID,
                "decision": "approve",
                "note": "Approved from CAPT native macOS surface",
            ],
            idempotencyKey: "native-approve-" + pending.requestID
        )
        try Self.ensureAcceptedOrApplied(decision)

        let run = try client.command(
            op: "run_approved_hermes_inspection",
            payload: [
                "objective": pending.objective,
                "targetRoot": pending.targetRoot,
                "provider": pending.provider,
                "model": pending.model,
                "missionId": pending.missionID,
                "taskId": pending.taskID,
                "driverRunId": pending.driverRunID,
                "approvalRequestId": pending.requestID,
                "requestedContextBudget": 32_000,
                "responseMode": "SPOCK",
                "promptEnhancement": "OFF",
                "humanVerificationRequired": true,
            ],
            idempotencyKey: "native-run-" + pending.driverRunID
        )
        try Self.ensureAcceptedOrApplied(run)

        let taskResponse = try client.query(
            op: "get_state",
            payload: ["streamId": "task-" + pending.taskID]
        )
        let taskState = Self.extractTaskState(taskResponse)
        return CAPTExecutionResult(
            text: Self.extractAssistantText(run),
            taskState: taskState
        )
    }

    private static func requireString(
        _ key: String,
        from dictionary: [String: Any]
    ) throws -> String {
        guard let value = dictionary[key] as? String, !value.isEmpty else {
            throw CAPTRuntimeClientError.malformedResponse("missing \(key)")
        }
        return value
    }

    private static func ensureAcceptedOrApplied(_ response: [String: Any]) throws {
        if response["ok"] as? Bool == false {
            throw CAPTRuntimeClientError.malformedResponse(runtimeErrorMessage(response))
        }
        if let status = response["status"] as? String,
           ["rejected", "denied", "failed"].contains(status.lowercased()) {
            throw CAPTRuntimeClientError.malformedResponse(runtimeErrorMessage(response))
        }
    }

    private static func runtimeErrorMessage(_ response: [String: Any]) -> String {
        var parts: [String] = []
        if let error = response["error"] as? [String: Any] {
            if let code = error["code"] as? String, !code.isEmpty { parts.append(code) }
            if let message = error["message"] as? String, !message.isEmpty { parts.append(message) }
        } else if let error = response["error"] as? String, !error.isEmpty {
            parts.append(error)
        }
        if let detail = response["detail"] as? String, !detail.isEmpty { parts.append(detail) }
        if parts.isEmpty, let status = response["status"] as? String {
            parts.append("runtime status " + status)
        }
        return parts.isEmpty ? "runtime rejected command" : parts.joined(separator: ": ")
    }

    private static func parseTimestamp(_ value: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: value) { return date }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: value)
    }

    private static func extractTaskState(_ response: [String: Any]) -> String {
        if let result = response["result"] as? [String: Any],
           let state = result["state"] as? String {
            return state
        }
        return response["state"] as? String ?? "unknown"
    }

    private static func extractAssistantText(_ response: [String: Any]) -> String {
        if let observations = response["observations"] as? [[String: Any]],
           let first = observations.first,
           let content = first["content"] as? String,
           !content.isEmpty {
            return content
        }
        if let result = response["result"] as? [String: Any] {
            if let text = result["text"] as? String, !text.isEmpty { return text }
            if let content = result["content"] as? String, !content.isEmpty { return content }
            if let observations = result["observations"] as? [[String: Any]],
               let content = observations.first?["content"] as? String,
               !content.isEmpty {
                return content
            }
        }
        if let data = try? JSONSerialization.data(
            withJSONObject: response,
            options: [.prettyPrinted, .sortedKeys]
        ), let text = String(data: data, encoding: .utf8) {
            return text
        }
        return "CAPT returned a result without renderable text."
    }
}
