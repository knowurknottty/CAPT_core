import Foundation

public enum CAPTChatFlowPhase: String, Equatable, Sendable {
    case idle
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
    public private(set) var failureMessage: String?

    public init(
        pending: CAPTPendingApproval? = nil,
        now: Date = Date()
    ) {
        if let pending {
            if pending.isExpired(at: now) {
                phase = .recoverableFailure
                requestID = nil
                failureMessage = "Prompt approval expired"
            } else {
                phase = .awaitingApproval
                requestID = pending.requestID
                failureMessage = nil
            }
        } else {
            phase = .idle
            requestID = nil
            failureMessage = nil
        }
    }

    public var isBusy: Bool {
        phase == .requestingApproval || phase == .executing
    }

    public var canCompose: Bool {
        !isBusy && requestID == nil
    }

    public mutating func beginApprovalRequest() {
        phase = .requestingApproval
        requestID = nil
        failureMessage = nil
    }

    public mutating func approvalPrepared(_ pending: CAPTPendingApproval) {
        phase = .awaitingApproval
        requestID = pending.requestID
        failureMessage = nil
    }

    public mutating func beginExecution(_ pending: CAPTPendingApproval) {
        phase = .executing
        requestID = pending.requestID
        failureMessage = nil
    }

    public mutating func executionCompleted(taskState: String) {
        phase = taskState == "awaiting_verification" ? .awaitingVerification : .idle
        requestID = nil
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
        failureMessage = message
        return disposition
    }

    public mutating func reset() {
        phase = .idle
        requestID = nil
        failureMessage = nil
    }
}
