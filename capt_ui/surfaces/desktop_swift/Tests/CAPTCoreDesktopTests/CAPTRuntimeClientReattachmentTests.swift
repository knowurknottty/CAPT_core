import Foundation
import XCTest
@testable import CAPTCoreDesktop

final class CAPTRuntimeClientReattachmentTests: XCTestCase {
    func testUnauthenticatedCommandAttemptsPreflightInsteadOfSending() {
        let tokenPath = "/tmp/capt-rrds-absent-token-" + UUID().uuidString
        let client = CAPTRuntimeClient(
            socketPath: "/tmp/capt-rrds-unreachable-" + UUID().uuidString,
            tokenPath: tokenPath
        )
        XCTAssertThrowsError(try client.command(
            op: "create_mission", payload: [:],
            idempotencyKey: UUID().uuidString
        )) { error in
            guard case CAPTRuntimeClientError.tokenMissing(let path) = error else {
                return XCTFail("Expected tokenMissing from authentication preflight, got \(error)")
            }
            XCTAssertEqual(path, tokenPath)
        }
    }
}
