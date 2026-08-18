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

public enum CAPTMessageRole: String, Codable {
    case user
    case assistant
    case system
}

public struct CAPTChatMessage: Identifiable, Equatable {
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

public struct CAPTPendingApproval: Equatable {
    public let requestID: String
    public let missionID: String
    public let taskID: String
    public let driverRunID: String
    public let objective: String
    public let targetRoot: String
    public let provider: String
    public let model: String
    public let promptAssemblyDigest: String

    public init(
        requestID: String,
        missionID: String,
        taskID: String,
        driverRunID: String,
        objective: String,
        targetRoot: String,
        provider: String,
        model: String,
        promptAssemblyDigest: String
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
    }
}
