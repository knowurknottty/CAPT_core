import XCTest
@testable import CAPTCoreDesktop

final class CAPTChatMessagePresentationTests: XCTestCase {
    func testLongMessagesUseBoundedCollapsedPresentation() {
        let text = String(repeating: "abcdef", count: 900)
        let presentation = CAPTChatMessagePresentation(
            text: text,
            collapsedCharacterLimit: 1_600
        )

        XCTAssertTrue(presentation.requiresExpansion)
        XCTAssertEqual(presentation.fullText, text)
        XCTAssertEqual(presentation.characterCount, text.count)
        XCTAssertLessThanOrEqual(presentation.collapsedText.count, 1_700)
        XCTAssertTrue(presentation.collapsedText.hasSuffix("…"))
    }

    func testShortMessagesRemainUnchanged() {
        let text = "short operator message"
        let presentation = CAPTChatMessagePresentation(
            text: text,
            collapsedCharacterLimit: 1_600
        )

        XCTAssertFalse(presentation.requiresExpansion)
        XCTAssertEqual(presentation.collapsedText, text)
    }
}
