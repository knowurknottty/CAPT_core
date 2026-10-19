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

    func testPartialHeaderStallHasBoundedReceiveDeadline() throws {
        var pair: [Int32] = [-1, -1]
        XCTAssertEqual(Darwin.socketpair(AF_UNIX, SOCK_STREAM, 0, &pair), 0)
        defer { Darwin.close(pair[0]); Darwin.close(pair[1]) }
        try CAPTRuntimeClient.configureIOTimeout(fd: pair[0])
        var byte: UInt8 = 19
        XCTAssertEqual(Darwin.send(pair[1], &byte, 1, 0), 1)
        let started = ProcessInfo.processInfo.systemUptime
        XCTAssertThrowsError(try CAPTRuntimeClient.readExactFromSocket(
            fd: pair[0], count: 4,
            deadline: started + 0.2
        )) { error in
            guard case CAPTRuntimeClientError.socketFailure(let message) = error else {
                XCTFail("Unexpected error: \(error)"); return
            }
            XCTAssertTrue(message.contains("deadline"))
        }
        XCTAssertLessThan(ProcessInfo.processInfo.systemUptime - started, 2)
    }

    func testPartialBodyStallHasBoundedReceiveDeadline() throws {
        var pair: [Int32] = [-1, -1]
        XCTAssertEqual(Darwin.socketpair(AF_UNIX, SOCK_STREAM, 0, &pair), 0)
        defer { Darwin.close(pair[0]); Darwin.close(pair[1]) }
        try CAPTRuntimeClient.configureIOTimeout(fd: pair[0])
        var bytes: [UInt8] = [65, 66]
        XCTAssertEqual(Darwin.send(pair[1], &bytes, 2, 0), 2)
        XCTAssertThrowsError(try CAPTRuntimeClient.readExactFromSocket(
            fd: pair[0], count: 9,
            deadline: ProcessInfo.processInfo.systemUptime + 0.2
        ))
    }

    func testSocketIOTimeoutAppliesToSendAndReceive() throws {
        var pair: [Int32] = [-1, -1]
        XCTAssertEqual(Darwin.socketpair(AF_UNIX, SOCK_STREAM, 0, &pair), 0)
        defer { Darwin.close(pair[0]); Darwin.close(pair[1]) }
        try CAPTRuntimeClient.configureIOTimeout(fd: pair[0])
        var receive = timeval()
        var length = socklen_t(MemoryLayout<timeval>.size)
        XCTAssertEqual(Darwin.getsockopt(pair[0], SOL_SOCKET, SO_RCVTIMEO, &receive, &length), 0)
        XCTAssertEqual(receive.tv_sec, 1)
        var send = timeval()
        length = socklen_t(MemoryLayout<timeval>.size)
        XCTAssertEqual(Darwin.getsockopt(pair[0], SOL_SOCKET, SO_SNDTIMEO, &send, &length), 0)
        XCTAssertEqual(send.tv_sec, 1)
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
