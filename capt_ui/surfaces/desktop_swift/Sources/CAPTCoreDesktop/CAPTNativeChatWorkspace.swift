import Foundation

public struct CAPTNativeChatWorkspace: Equatable, Sendable {
    public private(set) var sessions: [CAPTNativeSession]
    public private(set) var activeSessionID: UUID?
    private var flows: [UUID: CAPTChatFlow]

    public init(
        sessions: [CAPTNativeSession] = [],
        activeSessionID: UUID? = nil,
        now: Date = Date()
    ) {
        self.sessions = sessions.sorted { $0.updatedAt > $1.updatedAt }
        self.activeSessionID = activeSessionID
        self.flows = Dictionary(uniqueKeysWithValues: sessions.map {
            ($0.id, CAPTChatFlow(pending: $0.pendingApproval, now: now))
        })
    }

    public var activeSession: CAPTNativeSession? {
        guard let activeSessionID else { return nil }
        return session(activeSessionID)
    }

    public var activePendingApproval: CAPTPendingApproval? {
        activeSession?.pendingApproval
    }

    public var activeFlow: CAPTChatFlow {
        guard let activeSessionID else { return CAPTChatFlow() }
        return flow(for: activeSessionID)
    }

    public func session(_ id: UUID) -> CAPTNativeSession? {
        sessions.first(where: { $0.id == id })
    }

    public func flow(for id: UUID) -> CAPTChatFlow {
        flows[id] ?? CAPTChatFlow(pending: session(id)?.pendingApproval)
    }

    @discardableResult
    public mutating func newChat(
        id: UUID = UUID(),
        provider: String,
        model: String,
        targetRoot: String
    ) -> UUID {
        let welcome = CAPTChatMessage(
            role: .system,
            text: "New governed CAPT chat ready."
        )
        let chat = CAPTNativeSession(
            id: id,
            title: "New Chat",
            messages: [welcome],
            provider: provider,
            model: model,
            targetRoot: targetRoot,
            pendingApproval: nil
        )
        sessions.insert(chat, at: 0)
        activeSessionID = id
        flows[id] = CAPTChatFlow()
        return id
    }

    @discardableResult
    public mutating func activate(
        _ id: UUID,
        now: Date = Date()
    ) -> Bool {
        guard session(id) != nil else { return false }
        activeSessionID = id
        if flows[id] == nil {
            flows[id] = CAPTChatFlow(pending: session(id)?.pendingApproval, now: now)
        }
        expireApprovalIfNeeded(for: id, now: now)
        return true
    }

    @discardableResult
    public mutating func beginPrompt(
        _ objective: String,
        provider: String,
        model: String,
        targetRoot: String
    ) -> UUID? {
        let trimmed = objective.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty,
              let id = activeSessionID,
              let index = index(of: id),
              sessions[index].pendingApproval == nil else { return nil }

        var currentFlow = flow(for: id)
        guard currentFlow.canCompose else { return nil }

        if sessions[index].title == "New Chat" {
            sessions[index].title = String(trimmed.prefix(72))
        }
        sessions[index].provider = provider
        sessions[index].model = model
        sessions[index].targetRoot = targetRoot
        sessions[index].messages.append(CAPTChatMessage(role: .user, text: trimmed))
        sessions[index].updatedAt = Date()
        currentFlow.beginApprovalRequest()
        flows[id] = currentFlow
        return id
    }

    public mutating func receiveApproval(
        _ pending: CAPTPendingApproval,
        for id: UUID
    ) {
        guard let index = index(of: id) else { return }
        sessions[index].pendingApproval = pending
        if sessions[index].missionID == nil {
            sessions[index].missionID = pending.missionID
        }
        sessions[index].messages.append(CAPTChatMessage(
            role: .system,
            text: "CAPT prepared a bound execution. Review and approve before dispatch.",
            authorityState: "approval_required"
        ))
        sessions[index].updatedAt = Date()
        var currentFlow = flow(for: id)
        currentFlow.approvalPrepared(pending)
        flows[id] = currentFlow
    }

    public mutating func failApprovalRequest(
        message: String,
        for id: UUID
    ) {
        guard let index = index(of: id) else { return }
        var currentFlow = flow(for: id)
        _ = currentFlow.executionFailed(message: message, pending: nil)
        flows[id] = currentFlow
        sessions[index].messages.append(CAPTChatMessage(
            role: .system,
            text: message,
            authorityState: "error"
        ))
        sessions[index].updatedAt = Date()
    }

    public mutating func beginExecution(
        for id: UUID,
        now: Date = Date()
    ) -> CAPTPendingApproval? {
        guard let index = index(of: id),
              let pending = sessions[index].pendingApproval else { return nil }
        if pending.isExpired(at: now) {
            expireApproval(for: id, pending: pending)
            return nil
        }
        var currentFlow = flow(for: id)
        guard !currentFlow.isBusy else { return nil }
        currentFlow.beginExecution(pending)
        flows[id] = currentFlow
        return pending
    }

    public mutating func completeExecution(
        text: String,
        taskState: String,
        for id: UUID
    ) {
        guard let index = index(of: id) else { return }
        sessions[index].pendingApproval = nil
        sessions[index].messages.append(CAPTChatMessage(
            role: .assistant,
            text: text,
            authorityState: taskState
        ))
        sessions[index].updatedAt = Date()
        var currentFlow = flow(for: id)
        currentFlow.executionCompleted(taskState: taskState)
        flows[id] = currentFlow
    }

    @discardableResult
    public mutating func failExecution(
        message: String,
        for id: UUID
    ) -> CAPTApprovalFailureDisposition {
        guard let index = index(of: id) else { return .retryable }
        let pending = sessions[index].pendingApproval
        var currentFlow = flow(for: id)
        let disposition = currentFlow.executionFailed(
            message: message,
            pending: pending
        )
        flows[id] = currentFlow

        if disposition.isTerminalForLocalActionCursor {
            sessions[index].pendingApproval = nil
        }

        let rendered = Self.failurePresentation(
            disposition: disposition,
            runtimeMessage: message
        )
        sessions[index].messages.append(CAPTChatMessage(
            role: .system,
            text: rendered.text,
            authorityState: rendered.authorityState
        ))
        sessions[index].updatedAt = Date()
        return disposition
    }

    public mutating func completeDenial(for id: UUID) {
        guard let index = index(of: id) else { return }
        sessions[index].pendingApproval = nil
        sessions[index].messages.append(CAPTChatMessage(
            role: .system,
            text: "Execution denied. No model dispatch was authorized.",
            authorityState: "denied"
        ))
        sessions[index].updatedAt = Date()
        var currentFlow = flow(for: id)
        currentFlow.reset()
        flows[id] = currentFlow
    }

    public mutating func updateActiveConfiguration(
        provider: String,
        model: String,
        targetRoot: String
    ) {
        guard let id = activeSessionID, let index = index(of: id) else { return }
        sessions[index].provider = provider
        sessions[index].model = model
        sessions[index].targetRoot = targetRoot
        sessions[index].updatedAt = Date()
    }

    private mutating func expireApprovalIfNeeded(
        for id: UUID,
        now: Date
    ) {
        guard let pending = session(id)?.pendingApproval,
              pending.isExpired(at: now) else { return }
        expireApproval(for: id, pending: pending)
    }

    private mutating func expireApproval(
        for id: UUID,
        pending: CAPTPendingApproval
    ) {
        guard let index = index(of: id) else { return }
        sessions[index].pendingApproval = nil
        let message = "Prompt approval expired. Submit the prompt again to mint a fresh approval."
        sessions[index].messages.append(CAPTChatMessage(
            role: .system,
            text: message,
            authorityState: "approval_expired"
        ))
        sessions[index].updatedAt = Date()
        var currentFlow = flow(for: id)
        _ = currentFlow.executionFailed(
            message: "PROMPT_APPROVAL_EXPIRED: \(message)",
            pending: pending
        )
        flows[id] = currentFlow
    }

    private func index(of id: UUID) -> Int? {
        sessions.firstIndex(where: { $0.id == id })
    }

    private static func failurePresentation(
        disposition: CAPTApprovalFailureDisposition,
        runtimeMessage: String
    ) -> (text: String, authorityState: String) {
        switch disposition {
        case .expired:
            return (
                "Prompt approval expired. Submit the prompt again to mint a fresh approval. Runtime detail: \(runtimeMessage)",
                "approval_expired"
            )
        case .consumed:
            return (
                "This approval was already consumed and cannot be reused. Submit the prompt again for a fresh governed execution. Runtime detail: \(runtimeMessage)",
                "approval_consumed"
            )
        case .denied:
            return (
                "This approval is no longer actionable because it was denied. Submit the prompt again if you want a new execution. Runtime detail: \(runtimeMessage)",
                "denied"
            )
        case .retryable:
            return (runtimeMessage, "error")
        }
    }
}
