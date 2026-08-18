import Foundation
import CAPTCoreDesktop

actor CAPTBackgroundRuntime {
    private let client: CAPTRuntimeClient
    private let coordinator: CAPTChatCoordinator

    init(client: CAPTRuntimeClient = CAPTRuntimeClient()) {
        self.client = client
        self.coordinator = CAPTChatCoordinator(client: client)
    }

    func connect() throws -> [String: Any] {
        try client.connect()
    }

    func disconnect() {
        client.disconnect()
    }

    func identity() throws -> [String: Any] {
        try client.query(op: "identity", payload: [:])
    }

    func capabilities() throws -> [String: Any] {
        try client.query(op: "capabilities", payload: [:])
    }

    func requestApproval(
        objective: String,
        targetRoot: String,
        provider: String,
        model: String
    ) throws -> CAPTPendingApproval {
        try coordinator.requestApproval(
            objective: objective,
            targetRoot: targetRoot,
            provider: provider,
            model: model
        )
    }

    func deny(_ pending: CAPTPendingApproval) throws {
        try coordinator.deny(pending)
    }

    func approveAndRun(_ pending: CAPTPendingApproval) throws -> CAPTExecutionResult {
        try coordinator.approveAndRun(pending)
    }
}
