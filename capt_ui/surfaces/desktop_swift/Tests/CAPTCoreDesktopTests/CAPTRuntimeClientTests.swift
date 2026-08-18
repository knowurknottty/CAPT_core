import XCTest
@testable import CAPTCoreDesktop

final class CAPTRuntimeClientTests: XCTestCase {
    func testFrameUsesFourByteBigEndianLengthPrefix() throws {
        let payload: [String: Any] = ["op": "identity"]
        let frame = try CAPTRuntimeClient.makeFrame(payload)
        XCTAssertEqual(Array(frame.prefix(4)), [0, 0, 0, 17])
        let body = try XCTUnwrap(String(data: frame.dropFirst(4), encoding: .utf8))
        XCTAssertEqual(body, "{\"op\":\"identity\"}")
    }

    func testOversizedFrameLengthFailsClosed() {
        XCTAssertThrowsError(
            try CAPTRuntimeClient.validateFrameLength(CAPTRuntimeClient.maximumFrameBytes + 1)
        )
    }

    func testCommandEnvelopeBindsAuthenticatedIdentity() throws {
        let envelope = try CAPTRuntimeClient.makeCommandEnvelope(
            op: "shutdown", payload: [:], operatorID: "operator-1",
            sessionID: "session-1", idempotencyKey: "idem-1",
            correlationID: "corr-1", timestamp: "2026-08-18T00:00:00Z"
        )
        XCTAssertEqual(envelope["operatorId"] as? String, "operator-1")
        XCTAssertEqual(envelope["sessionId"] as? String, "session-1")
        XCTAssertEqual(envelope["op"] as? String, "shutdown")
    }
}
