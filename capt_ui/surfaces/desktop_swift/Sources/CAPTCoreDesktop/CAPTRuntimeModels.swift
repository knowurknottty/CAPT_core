import Foundation

public protocol CAPTRuntimeCommanding: AnyObject {
    func connect() throws -> [String: Any]
    func disconnect()
    func query(op: String, payload: [String: Any]) throws -> [String: Any]
    func command(
        op: String,
        payload: [String: Any],
        idempotencyKey: String?
    ) throws -> [String: Any]
}

public enum CAPTRuntimeConnectionState: Equatable {
    case disconnected
    case connecting
    case connected
    case failed(String)
}

public enum CAPTMessageRole: String, Codable, Sendable {
    case user
    case assistant
    case system
}

public struct CAPTChatMessage: Identifiable, Codable, Equatable, Sendable {
    public let id: UUID
    public let role: CAPTMessageRole
    public let text: String
    public let timestamp: Date
    public let authorityState: String?

    public init(
        id: UUID = UUID(),
        role: CAPTMessageRole,
        text: String,
        timestamp: Date = Date(),
        authorityState: String? = nil
    ) {
        self.id = id
        self.role = role
        self.text = text
        self.timestamp = timestamp
        self.authorityState = authorityState
    }
}

public enum CAPTApprovalValidity: String, Equatable, Sendable {
    case valid
    case expired
    case unknown
}

public struct CAPTPendingApproval: Codable, Equatable, Sendable {
    public let requestID: String
    public let missionID: String
    public let taskID: String
    public let driverRunID: String
    public let objective: String
    public let targetRoot: String
    public let provider: String
    public let model: String
    public let promptAssemblyDigest: String
    public let skillNames: [String]
    public let expiresAt: Date?

    public init(
        requestID: String,
        missionID: String,
        taskID: String,
        driverRunID: String,
        objective: String,
        targetRoot: String,
        provider: String,
        model: String,
        promptAssemblyDigest: String,
        skillNames: [String] = [],
        expiresAt: Date? = nil
    ) {
        self.requestID = requestID
        self.missionID = missionID
        self.taskID = taskID
        self.driverRunID = driverRunID
        self.objective = objective
        self.targetRoot = targetRoot
        self.provider = provider
        self.model = model
        self.promptAssemblyDigest = promptAssemblyDigest
        self.skillNames = skillNames
        self.expiresAt = expiresAt
    }

    private enum CodingKeys: String, CodingKey {
        case requestID, missionID, taskID, driverRunID, objective, targetRoot
        case provider, model, promptAssemblyDigest, skillNames, expiresAt
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        requestID = try c.decode(String.self, forKey: .requestID)
        missionID = try c.decode(String.self, forKey: .missionID)
        taskID = try c.decode(String.self, forKey: .taskID)
        driverRunID = try c.decode(String.self, forKey: .driverRunID)
        objective = try c.decode(String.self, forKey: .objective)
        targetRoot = try c.decode(String.self, forKey: .targetRoot)
        provider = try c.decode(String.self, forKey: .provider)
        model = try c.decode(String.self, forKey: .model)
        promptAssemblyDigest = try c.decode(String.self, forKey: .promptAssemblyDigest)
        skillNames = try c.decodeIfPresent([String].self, forKey: .skillNames) ?? []
        expiresAt = try c.decodeIfPresent(Date.self, forKey: .expiresAt)
    }

    public func validity(at date: Date = Date()) -> CAPTApprovalValidity {
        guard let expiresAt else { return .unknown }
        return expiresAt <= date ? .expired : .valid
    }

    public func isExpired(at date: Date = Date()) -> Bool {
        validity(at: date) == .expired
    }

    public func isActionable(at date: Date = Date()) -> Bool {
        validity(at: date) == .valid
    }
}
