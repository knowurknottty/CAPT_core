import Foundation

/// Pure bounded presentation, independent of durable encrypted session history.
/// A SwiftUI VStack with a limited slice avoids LazyVStack's repeated
/// variable-height placement churn observed on macOS 26 in PI chat.
public enum CAPTTranscriptWindow {
    public static func visible(
        _ messages: [CAPTChatMessage], limit: Int = 40
    ) -> [CAPTChatMessage] {
        Array(messages.suffix(max(1, min(limit, 500))))
    }
}
