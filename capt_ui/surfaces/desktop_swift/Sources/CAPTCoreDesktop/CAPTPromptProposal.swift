import Foundation

public enum CAPTPromptSelection: String, Codable, CaseIterable, Sendable {
    case original
    case upgrade
    case edited
}

public struct CAPTPromptStageSummary: Codable, Equatable, Sendable {
    public let stage: String
    public let executionEnabled: Bool
    public let provider: String?
    public let model: String?
    public let endpointClass: String?
    public let rationale: String

    public init(
        stage: String, executionEnabled: Bool,
        provider: String? = nil, model: String? = nil,
        endpointClass: String? = nil, rationale: String = ""
    ) {
        self.stage = stage
        self.executionEnabled = executionEnabled
        self.provider = provider
        self.model = model
        self.endpointClass = endpointClass
        self.rationale = rationale
    }
}

public struct CAPTPromptProposal: Codable, Equatable, Sendable {
    public let proposalID: String
    public let revision: Int
    public let state: String
    public let status: String
    public let originalPrompt: String
    public let proposedPrompt: String
    public let originalPromptDigest: String
    public let proposedPromptDigest: String
    public let stageChain: [String]
    public let stageRecords: [CAPTPromptStageSummary]
    public let verificationCriteria: [String]
    public let unresolvedQuestions: [String]
    public let targetRoot: String
    public let provider: String?
    public let model: String?
    public let rationale: String

    public var isActive: Bool { state == "active" }
    public var isApprovalSelectable: Bool {
        if status == "ready_for_approval" { return true }
        if status == "clarification_required" {
            return stageRecords.contains(where: { $0.executionEnabled })
        }
        return false
    }
    public var hasMaterialUpgrade: Bool {
        originalPromptDigest != proposedPromptDigest
    }

    public func selectedPrompt(_ selection: CAPTPromptSelection, edited: String = "") -> String {
        switch selection {
        case .original: return originalPrompt
        case .upgrade: return proposedPrompt
        case .edited: return edited.trimmingCharacters(in: .whitespacesAndNewlines)
        }
    }

    public init(dictionary: [String: Any]) throws {
        func string(_ key: String) throws -> String {
            guard let value = dictionary[key] as? String, !value.isEmpty else {
                throw CAPTRuntimeClientError.malformedResponse("prompt proposal missing \(key)")
            }
            return value
        }
        proposalID = try string("proposalId")
        revision = dictionary["revision"] as? Int ?? 0
        state = try string("state")
        status = (dictionary["status"] as? String) ?? "ready_for_approval"
        originalPrompt = try string("originalPrompt")
        proposedPrompt = try string("proposedPrompt")
        originalPromptDigest = try string("originalPromptDigest")
        proposedPromptDigest = try string("proposedPromptDigest")
        stageChain = dictionary["stageChain"] as? [String] ?? []
        targetRoot = try string("targetRoot")
        provider = dictionary["provider"] as? String
        model = dictionary["model"] as? String
        rationale = dictionary["rationale"] as? String ?? ""

        let verification = dictionary["verificationContract"] as? [String: Any]
        verificationCriteria = verification?["acceptanceCriteria"] as? [String] ?? []
        unresolvedQuestions = dictionary["unresolvedQuestions"] as? [String] ?? []
        let rawStages = dictionary["stageRecords"] as? [[String: Any]] ?? []
        stageRecords = rawStages.compactMap { item in
            guard let stage = item["stage"] as? String else { return nil }
            return CAPTPromptStageSummary(
                stage: stage,
                executionEnabled: item["executionEnabled"] as? Bool ?? false,
                provider: item["provider"] as? String,
                model: item["model"] as? String,
                endpointClass: item["endpointClass"] as? String,
                rationale: item["rationale"] as? String ?? ""
            )
        }
    }
}
