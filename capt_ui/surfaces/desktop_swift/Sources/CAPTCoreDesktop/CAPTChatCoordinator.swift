import Foundation

public struct CAPTExecutionResult: Equatable, Sendable {
    public let text: String
    public let taskState: String
    public let driverRunID: String
    public let executionDetailsJSON: String?

    public init(
        text: String, taskState: String, driverRunID: String,
        executionDetailsJSON: String? = nil
    ) {
        self.text = text
        self.taskState = taskState
        self.driverRunID = driverRunID
        self.executionDetailsJSON = executionDetailsJSON
    }
}

public final class CAPTChatCoordinator {
    private let client: CAPTRuntimeCommanding

    public init(client: CAPTRuntimeCommanding) {
        self.client = client
    }

    public func compileProposal(
        original: String,
        targetRoot: String,
        provider: String,
        model: String,
        promptIntelligence: String = "AUTO",
        reasoningEffort: String = "",
        remoteCompilationAuthorized: Bool = false,
        piRequestID: String? = nil
    ) throws -> CAPTPromptProposal {
        let attemptID = piRequestID ?? ("pp-" + UUID().uuidString.lowercased())
        let response = try client.command(
            op: "compile_prompt_proposal",
            payload: [
                "originalPrompt": original,
                "targetRoot": targetRoot,
                "promptIntelligence": promptIntelligence,
                "mode": "normal",
                "provider": provider,
                "model": model,
                "reasoningEffort": reasoningEffort,
                "requestedContextBudget": 32_000,
                "requestedCapabilities": [],
                "remoteCompilationAuthorized": remoteCompilationAuthorized,
                "proposalId": attemptID,
            ],
            idempotencyKey: "native-proposal-" + attemptID
        )
        try Self.ensureAcceptedOrApplied(response)
        guard let result = response["result"] as? [String: Any] else {
            throw CAPTRuntimeClientError.malformedResponse("prompt proposal result missing")
        }
        return try CAPTPromptProposal(dictionary: result)
    }

    public func cancelProposal(_ proposal: CAPTPromptProposal) throws {
        let response = try client.command(
            op: "cancel_prompt_proposal",
            payload: [
                "proposalId": proposal.proposalID,
                "reason": "Cancelled from CAPT native macOS surface",
            ],
            idempotencyKey: "native-cancel-proposal-" + proposal.proposalID + "-r" + String(proposal.revision)
        )
        try Self.ensureAcceptedOrApplied(response)
    }

    public func requestApproval(
        proposal: CAPTPromptProposal,
        selection: CAPTPromptSelection,
        editedPrompt: String = "",
        missionID: String? = nil,
        managedSkillNames: [String]? = nil,
        autoSelectSkills: Bool = true,
        cohortSpec: [String: Any]? = nil,
        authoritySettings: CAPTExecutionAuthoritySettings = .default
    ) throws -> CAPTPendingApproval {
        let selected = proposal.selectedPrompt(selection, edited: editedPrompt)
        guard !selected.isEmpty else {
            throw CAPTRuntimeClientError.malformedResponse("selected prompt is empty")
        }
        var payload: [String: Any] = [
            "proposalId": proposal.proposalID,
            "proposalRevision": proposal.revision,
            "selection": selection.rawValue,
            "responseMode": "SPOCK",
            "humanVerificationRequired": true,
        ]
        if selection == .edited { payload["editedPrompt"] = selected }
        if let cohortSpec { payload["cohortSpec"] = cohortSpec }
        if let missionID, !missionID.isEmpty { payload["missionId"] = missionID }
        guard let filesystemRoot = authoritySettings.effectiveFilesystemRoot(
            projectRoot: proposal.targetRoot
        ) else {
            throw CAPTRuntimeClientError.malformedResponse(
                "custom filesystem scope requires a selected root"
            )
        }
        payload["authorityProfile"] = [
            "filesystemScope": authoritySettings.filesystemScope.rawValue,
            "filesystemRoot": filesystemRoot,
            "fileMutationAllowed": authoritySettings.fileMutationAllowed,
            "shellAccessAllowed": authoritySettings.shellAccessAllowed,
            "providerNetworkPolicy": authoritySettings.providerNetwork.rawValue,
        ]
        if let managedSkillNames, !managedSkillNames.isEmpty {
            payload["managedSkillNames"] = managedSkillNames
        } else {
            payload["autoSelectSkills"] = autoSelectSkills
        }
        let response = try client.command(
            op: "request_prompt_proposal_approval",
            payload: payload,
            idempotencyKey: "native-proposal-approval-" + UUID().uuidString.lowercased()
        )
        try Self.ensureAcceptedOrApplied(response)
        guard let result = response["result"] as? [String: Any] else {
            throw CAPTRuntimeClientError.malformedResponse("proposal approval result missing")
        }
        return try Self.pendingApproval(
            from: result, objective: selected, targetRoot: proposal.targetRoot,
            provider: proposal.provider ?? "", model: proposal.model ?? "",
            proposalID: proposal.proposalID, proposalRevision: proposal.revision,
            selectedPromptKind: selection.rawValue
        )
    }

    public func requestApproval(
        objective: String,
        targetRoot: String,
        provider: String,
        model: String,
        reasoningEffort: String = "",
        missionID: String? = nil,
        authoritySettings: CAPTExecutionAuthoritySettings = .default
    ) throws -> CAPTPendingApproval {
        var payload: [String: Any] = [
            "objective": objective,
            "targetRoot": targetRoot,
            "provider": provider,
            "model": model,
            "reasoningEffort": reasoningEffort,
            "requestedContextBudget": 32_000,
            "responseMode": "SPOCK",
            "promptEnhancement": "OFF",
            "humanVerificationRequired": true,
        ]
        if let missionID, !missionID.isEmpty { payload["missionId"] = missionID }
        guard let filesystemRoot = authoritySettings.effectiveFilesystemRoot(projectRoot: targetRoot) else {
            throw CAPTRuntimeClientError.malformedResponse(
                "custom filesystem scope requires a selected root"
            )
        }
        payload["authorityProfile"] = [
            "filesystemScope": authoritySettings.filesystemScope.rawValue,
            "filesystemRoot": filesystemRoot,
            "fileMutationAllowed": authoritySettings.fileMutationAllowed,
            "shellAccessAllowed": authoritySettings.shellAccessAllowed,
            "providerNetworkPolicy": authoritySettings.providerNetwork.rawValue,
        ]
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
        let skillNames = result["skillNames"] as? [String] ?? []
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
            reasoningEffort: result["reasoningEffort"] as? String,
            promptAssemblyDigest: digest,
            skillNames: skillNames,
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
                "reasoningEffort": pending.reasoningEffort ?? "",
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

        let text = Self.extractAssistantText(run)
        let executionDetailsJSON = Self.prettyExecutionDetails(run)
        do {
            let taskResponse = try client.query(
                op: "get_state",
                payload: ["streamId": "task-" + pending.taskID]
            )
            return CAPTExecutionResult(
                text: text,
                taskState: Self.extractTaskState(taskResponse),
                driverRunID: pending.driverRunID,
                executionDetailsJSON: executionDetailsJSON
            )
        } catch {
            return CAPTExecutionResult(
                text: text,
                taskState: "indeterminate",
                driverRunID: pending.driverRunID,
                executionDetailsJSON: executionDetailsJSON
            )
        }
    }

    private static func pendingApproval(
        from result: [String: Any],
        objective: String,
        targetRoot: String,
        provider: String,
        model: String,
        proposalID: String? = nil,
        proposalRevision: Int? = nil,
        selectedPromptKind: String? = nil
    ) throws -> CAPTPendingApproval {
        let requestID = try requireString("requestId", from: result)
        let missionID = try requireString("missionId", from: result)
        let taskID = try requireString("taskId", from: result)
        let driverRunID = try requireString("driverRunId", from: result)
        let digest = try requireString("promptAssemblyDigest", from: result)
        let expiresAt = (result["expiresAt"] as? String).flatMap(parseTimestamp)
        let skillNames = result["skillNames"] as? [String] ?? []
        return CAPTPendingApproval(
            requestID: requestID, missionID: missionID, taskID: taskID,
            driverRunID: driverRunID, objective: objective, targetRoot: targetRoot,
            provider: provider, model: model,
            reasoningEffort: result["reasoningEffort"] as? String,
            promptAssemblyDigest: digest,
            skillNames: skillNames, expiresAt: expiresAt, proposalID: proposalID,
            proposalRevision: proposalRevision, selectedPromptKind: selectedPromptKind
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
        func observationText(_ observation: [String: Any]?) -> String? {
            guard let observation else { return nil }
            for key in ["content", "summary"] {
                if let value = observation[key] as? String {
                    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !trimmed.isEmpty { return trimmed }
                }
            }
            return nil
        }

        if let observations = response["observations"] as? [[String: Any]],
           let text = observationText(observations.first) {
            return text
        }
        if let result = response["result"] as? [String: Any] {
            if let text = result["text"] as? String, !text.isEmpty { return text }
            if let content = result["content"] as? String, !content.isEmpty { return content }
            if let observations = result["observations"] as? [[String: Any]],
               let text = observationText(observations.first) {
                return text
            }
        }
        return "CAPT returned a result without renderable text."
    }

    private static func prettyExecutionDetails(_ response: [String: Any]) -> String? {
        guard JSONSerialization.isValidJSONObject(response),
              let data = try? JSONSerialization.data(
                withJSONObject: response, options: [.prettyPrinted, .sortedKeys]
              ) else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
