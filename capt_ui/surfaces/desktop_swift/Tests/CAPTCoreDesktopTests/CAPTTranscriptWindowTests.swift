import XCTest
@testable import CAPTCoreDesktop

final class CAPTTranscriptWindowTests: XCTestCase {
    func testWindowKeepsNewestStableIdsWithoutDeletingHistory() {
        let messages = (0..<900).map {
            CAPTChatMessage(role: .user, text: "message-\($0)")
        }
        let first = CAPTTranscriptWindow.visible(messages)
        XCTAssertEqual(first.count, 40)
        XCTAssertEqual(first.first?.id, messages[860].id)
        XCTAssertEqual(first.last?.id, messages[899].id)
        XCTAssertEqual(CAPTTranscriptWindow.visible(messages, limit: 80).first?.id,
                       messages[820].id)
        XCTAssertEqual(messages.count, 900, "Underlying transcript must not be pruned")
    }

    func testLimitsAreClampedAndEmptySafe() {
        XCTAssertTrue(CAPTTranscriptWindow.visible([]).isEmpty)
        let messages = (0..<600).map {
            CAPTChatMessage(role: .system, text: "\($0)")
        }
        XCTAssertEqual(CAPTTranscriptWindow.visible(messages, limit: 0).count, 1)
        XCTAssertEqual(CAPTTranscriptWindow.visible(messages, limit: 9_999).count, 500)
    }
}
