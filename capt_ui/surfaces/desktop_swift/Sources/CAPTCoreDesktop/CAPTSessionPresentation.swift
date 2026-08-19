import Foundation

public enum CAPTApprovalPresentation {
    public static func isExpiredError(_ error: Error) -> Bool {
        isExpiredMessage(error.localizedDescription)
    }

    public static func isExpiredMessage(_ message: String) -> Bool {
        let upper = message.uppercased()
        return upper.contains("MODEL_PROMPT_APPROVAL_EXPIRED")
            || upper.contains("APPROVAL_EXPIRED")
    }

    public static func isActionable(
        _ pending: CAPTPendingApproval,
        authoritative approvals: [CAPTApprovalSummary],
        now: Date = Date()
    ) -> Bool {
        guard let approval = approvals.first(where: { $0.id == pending.requestID }),
              approval.state == "requested", approval.decision == nil,
              approval.remainingUses > 0 else { return false }
        guard !approval.expiresAt.isEmpty else { return true }
        guard let expiry = parseISO8601(approval.expiresAt) else { return false }
        return expiry > now
    }

    public static let expiredMessage =
        "Approval expired before execution. No model request was sent. Request a new approval to continue."

    public static let unavailableMessage =
        "This saved approval is no longer actionable in RuntimeService. No model request was sent. Request a new approval to continue."

    private static func parseISO8601(_ value: String) -> Date? {
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = fractional.date(from: value) { return date }
        return ISO8601DateFormatter().date(from: value)
    }
}
