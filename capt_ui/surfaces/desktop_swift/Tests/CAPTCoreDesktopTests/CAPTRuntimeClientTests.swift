import XCTest
import Darwin
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

    func testSocketConfiguratorSuppressesSIGPIPE() throws {
        var pair: [Int32] = [-1, -1]
        XCTAssertEqual(Darwin.socketpair(AF_UNIX, SOCK_STREAM, 0, &pair), 0)
        defer {
            if pair[0] >= 0 { Darwin.close(pair[0]) }
            if pair[1] >= 0 { Darwin.close(pair[1]) }
        }
        try CAPTRuntimeClient.configureNoSigPipe(fd: pair[0])
        var value: Int32 = 0
        var length = socklen_t(MemoryLayout<Int32>.size)
        XCTAssertEqual(
            Darwin.getsockopt(pair[0], SOL_SOCKET, SO_NOSIGPIPE, &value, &length),
            0
        )
        XCTAssertEqual(value, 1)
    }

    func testExplicitRetryKeyChangesCommandIDForSamePayload() throws {
        let common: [String: Any] = ["originalPrompt": "same", "model": "tencent/hy3"]
        let first = try CAPTRuntimeClient.makeCommandEnvelope(
            op: "compile_prompt_proposal", payload: common, operatorID: "operator-1",
            sessionID: "session-1", idempotencyKey: "retry-a",
            correlationID: "corr-1", timestamp: "2026-08-27T00:00:00Z"
        )
        let second = try CAPTRuntimeClient.makeCommandEnvelope(
            op: "compile_prompt_proposal", payload: common, operatorID: "operator-1",
            sessionID: "session-1", idempotencyKey: "retry-b",
            correlationID: "corr-2", timestamp: "2026-08-27T00:00:01Z"
        )
        XCTAssertNotEqual(first["commandId"] as? String, second["commandId"] as? String)
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
