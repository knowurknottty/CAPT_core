import Foundation

public enum CAPTChatFlowPhase: String, Equatable, Sendable {
    case idle
    case compilingProposal
    case reviewingProposal
    case requestingApproval
    case awaitingApproval
    case executing
    case awaitingVerification
    case recoverableFailure
}

public enum CAPTApprovalFailureDisposition: String, Equatable, Sendable {
    case retryable
    case expired
    case consumed
    case denied

    public var isTerminalForLocalActionCursor: Bool {
        self != .retryable
    }
}

public enum CAPTApprovalRecoveryPolicy {
    public static func classify(_ message: String) -> CAPTApprovalFailureDisposition {
        let value = message.lowercased()
        if value.contains("prompt_approval_expired") ||
            value.contains("prompt approval expired") ||
            value.contains("approval expired") {
            return .expired
        }
        if value.contains("approval_consumed") ||
            value.contains("approval already consumed") ||
            value.contains("already consumed") {
            return .consumed
        }
        if value.contains("approval_denied") ||
            value.contains("approval denied") {
            return .denied
        }
        return .retryable
    }
}

public struct CAPTChatFlow: Equatable, Sendable {
    public private(set) var phase: CAPTChatFlowPhase
    public private(set) var requestID: String?
    public private(set) var proposalID: String?
    public private(set) var failureMessage: String?

    public init(
        pending: CAPTPendingApproval? = nil,
        proposal: CAPTPromptProposal? = nil,
        now: Date = Date()
    ) {
        if pending == nil, let proposal, proposal.isActive {
            phase = .reviewingProposal
            requestID = nil
            proposalID = proposal.proposalID
            failureMessage = nil
            return
        }
        guard let pending else {
            phase = .idle
            requestID = nil
            proposalID = nil
            failureMessage = nil
            return
        }

        switch pending.validity(at: now) {
        case .valid:
            phase = .awaitingApproval
            requestID = pending.requestID
            proposalID = pending.proposalID
            failureMessage = nil
        case .expired:
            phase = .recoverableFailure
            requestID = nil
            proposalID = nil
            failureMessage = "Prompt approval expired"
        case .unknown:
            phase = .recoverableFailure
            requestID = nil
            proposalID = nil
            failureMessage = "Prompt approval validity unavailable"
        }
    }

    public var isBusy: Bool {
        phase == .compilingProposal || phase == .requestingApproval || phase == .executing
    }

    public var canCompose: Bool {
        !isBusy && phase != .reviewingProposal && requestID == nil
    }

    public mutating func beginCompilation() {
        phase = .compilingProposal
        requestID = nil
        proposalID = nil
        failureMessage = nil
    }

    public mutating func proposalPrepared(_ proposal: CAPTPromptProposal) {
        phase = .reviewingProposal
        requestID = nil
        proposalID = proposal.proposalID
        failureMessage = nil
    }

    public mutating func beginApprovalRequest() {
        phase = .requestingApproval
        requestID = nil
        failureMessage = nil
    }

    public mutating func proposalFailed(message: String) {
        phase = .recoverableFailure
        requestID = nil
        proposalID = nil
        failureMessage = message
    }

    public mutating func approvalRequestFailed(message: String) {
        requestID = nil
        failureMessage = message
        phase = proposalID == nil ? .recoverableFailure : .reviewingProposal
    }

    public mutating func approvalPrepared(
        _ pending: CAPTPendingApproval,
        now: Date = Date()
    ) {
        switch pending.validity(at: now) {
        case .valid:
            phase = .awaitingApproval
            requestID = pending.requestID
            proposalID = pending.proposalID ?? proposalID
            failureMessage = nil
        case .expired:
            phase = .recoverableFailure
            requestID = nil
            proposalID = nil
            failureMessage = "Prompt approval expired"
        case .unknown:
            phase = .recoverableFailure
            requestID = nil
            proposalID = nil
            failureMessage = "Prompt approval validity unavailable"
        }
    }

    public mutating func beginExecution(_ pending: CAPTPendingApproval) {
        phase = .executing
        requestID = pending.requestID
        failureMessage = nil
    }

    public mutating func executionCompleted(taskState: String) {
        phase = taskState == "awaiting_verification" ? .awaitingVerification : .idle
        requestID = nil
        proposalID = nil
        failureMessage = nil
    }

    @discardableResult
    public mutating func executionFailed(
        message: String,
        pending: CAPTPendingApproval?
    ) -> CAPTApprovalFailureDisposition {
        let disposition = CAPTApprovalRecoveryPolicy.classify(message)
        phase = .recoverableFailure
        requestID = disposition.isTerminalForLocalActionCursor ? nil : pending?.requestID
        proposalID = disposition.isTerminalForLocalActionCursor ? nil : (pending?.proposalID ?? proposalID)
        failureMessage = message
        return disposition
    }

    public mutating func approvalSuperseded(message: String) {
        phase = .recoverableFailure
        requestID = nil
        proposalID = nil
        failureMessage = message
    }

    public mutating func reset() {
        phase = .idle
        requestID = nil
        proposalID = nil
        failureMessage = nil
    }
}
