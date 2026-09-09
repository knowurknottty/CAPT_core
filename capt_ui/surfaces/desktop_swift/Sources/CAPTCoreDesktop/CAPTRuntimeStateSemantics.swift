import Foundation

public enum CAPTRuntimeStateTone: String, Equatable, Sendable {
    case neutral
    case success
    case danger
    case warning
    case active
    case violet
}

public enum CAPTRuntimeStateSemantics {
    public static func tone(for raw: String) -> CAPTRuntimeStateTone {
        switch raw.lowercased() {
        case "completed", "verified", "accepted", "succeeded", "ready":
            return .success
        case "failed", "rejected", "denied", "lost", "revoked", "timed_out", "expired":
            return .danger
        case "running", "executing", "submitted", "assigned", "active":
            return .active
        case "indeterminate", "suspended", "cancelled", "pending", "draft", "awaiting_verification", "awaiting_approval":
            return .warning
        case "proposal_compiling", "proposal_review", "reviewing_proposal", "approval_preparing":
            return .violet
        default:
            return .neutral
        }
    }
}
