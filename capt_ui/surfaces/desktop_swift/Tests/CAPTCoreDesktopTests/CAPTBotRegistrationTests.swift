import XCTest
@testable import CAPTCoreDesktop

private final class BotClientStub: CAPTRuntimeCommanding {
    var invoked: [(String, [String: Any], String?)] = []
    func connect() throws -> [String: Any] { [:] }
    func disconnect() {}
    func query(op: String, payload: [String: Any]) throws -> [String: Any] { [:] }
    func command(op: String, payload: [String: Any], idempotencyKey: String?) throws -> [String: Any] {
        invoked.append((op,payload,idempotencyKey))
        let bot = (payload["bot"] as? [String:Any]) ?? [:]
        return ["status":"accepted","result":["botId":bot["botId"] ?? "",
                                              "identityOnly":true]]
    }
}

final class CAPTBotRegistrationTests: XCTestCase {
    func testBotRegistrationExcludesCredentialsAndForgedActor() throws {
        let client = BotClientStub()
        let draft = CAPTBotDraft(
            identifier: "issue-steward",
            displayName: "Issue Steward",
            role: "Audit and resolve issues sequentially",
            model: "deepseek/deepseek-v4.1-flash")
        let id = try CAPTBotRegistration(client: client).register(draft)
        XCTAssertEqual(id, "issue-steward")
        XCTAssertEqual(client.invoked.map(\.0), ["register_bot"])
        XCTAssertEqual(client.invoked[0].2, "native-create-bot:issue-steward")
        let bot = try XCTUnwrap(client.invoked[0].1["bot"] as? [String:Any])
        XCTAssertNil(bot["apiKey"])
        XCTAssertNil(bot["createdBy"])
        XCTAssertNil(bot["createdAt"])
        let locality = try XCTUnwrap(bot["localityPolicy"] as? [String:Any])
        XCTAssertEqual(locality["privateData"] as? String, "local_only")
        let collab = try XCTUnwrap(bot["collaboration"] as? [String:Any])
        XCTAssertEqual(collab["mayDelegate"] as? Bool, false)
    }

    func testInvalidBotIDRefusedBeforeRuntimeCall() {
        let client = BotClientStub()
        XCTAssertThrowsError(try CAPTBotRegistration(client: client).register(
            CAPTBotDraft(identifier: "bot/../../../other", displayName: "No", role: "bad")
        ))
        XCTAssertEqual(client.invoked.count, 0)
    }
}
