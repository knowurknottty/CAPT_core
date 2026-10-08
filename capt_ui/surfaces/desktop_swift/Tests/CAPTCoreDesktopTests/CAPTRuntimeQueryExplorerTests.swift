import Foundation
import XCTest
@testable import CAPTCoreDesktop

private final class QueryRuntimeStub: CAPTRuntimeCommanding {
    var calls: [(String, [String: Any])] = []
    func connect() throws -> [String: Any] { [:] }
    func disconnect() {}
    func query(op: String, payload: [String: Any]) throws -> [String: Any] {
        calls.append((op, payload))
        if op == "capabilities" {
            return ["ok": true, "result": [
                "queryOperations": ["identity", "capabilities", "get_state"]
            ]]
        }
        return ["ok": true, "result": [
            "runtimeVersion": "test-runtime", "payload": payload
        ]]
    }
    func command(op: String, payload: [String: Any], idempotencyKey: String?) throws -> [String: Any] {
        XCTFail("Read inspector MUST NOT submit a command")
        return ["status": "rejected"]
    }
}

final class CAPTRuntimeQueryExplorerTests: XCTestCase {
    func testPerformsOnlyAdvertisedQueryWithExactArguments() throws {
        let stub = QueryRuntimeStub()
        let result = try CAPTRuntimeQueryExplorer(client: stub).perform(
            operation: "get_state", payloadJSON: #"{"streamId":"mission-x"}"#
        )
        XCTAssertTrue(result.contains("test-runtime"))
        XCTAssertEqual(stub.calls.map(\.0), ["capabilities", "get_state"])
        XCTAssertEqual(stub.calls[1].1["streamId"] as? String, "mission-x")
    }

    func testRejectsCommandsAndUnknownRuntimeOperations() throws {
        let stub = QueryRuntimeStub()
        let explorer = CAPTRuntimeQueryExplorer(client: stub)
        XCTAssertThrowsError(try explorer.perform(operation: "run_tool", payloadJSON: "{}"))
        XCTAssertThrowsError(try explorer.perform(operation: "shutdown", payloadJSON: "{}"))
        XCTAssertEqual(stub.calls.map(\.0), ["capabilities", "capabilities"])
    }

    func testRejectsPayloadOperationAndAuthenticationOverrides() throws {
        let stub = QueryRuntimeStub()
        let explorer = CAPTRuntimeQueryExplorer(client: stub)
        for text in [
            #"{"op":"shutdown"}"#,
            #"{"token":"injected"}"#,
            #"{"command":{"op":"shutdown"}}"#,
            "[]",
        ] {
            XCTAssertThrowsError(try explorer.perform(operation: "identity", payloadJSON: text))
        }
        XCTAssertTrue(stub.calls.isEmpty)
    }

    func testRejectsOversizedQuery() throws {
        let stub = QueryRuntimeStub()
        XCTAssertThrowsError(try CAPTRuntimeQueryExplorer(client: stub).perform(
            operation: "identity", payloadJSON: "{\"x\":\"" + String(repeating: "x", count: 20_000) + "\"}"
        ))
        XCTAssertTrue(stub.calls.isEmpty)
    }
}
