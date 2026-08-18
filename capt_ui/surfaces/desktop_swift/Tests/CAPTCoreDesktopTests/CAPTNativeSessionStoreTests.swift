import XCTest
@testable import CAPTCoreDesktop

private struct StaticSessionKeyProvider: CAPTSessionKeyProviding {
    let bytes: Data
    func keyData() throws -> Data { bytes }
}

final class CAPTNativeSessionStoreTests: XCTestCase {
    func testEncryptedSessionStoreRoundTripsWithoutPlaintext() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let file = root.appendingPathComponent("native_sessions.enc")
        let key = StaticSessionKeyProvider(bytes: Data(repeating: 0x42, count: 32))
        let store = CAPTEncryptedSessionStore(fileURL: file, keyProvider: key)
        let message = CAPTChatMessage(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            role: .user, text: "private invention prompt",
            timestamp: Date(timeIntervalSince1970: 1_700_000_000)
        )
        let pending = CAPTPendingApproval(
            requestID: "approval-1", missionID: "m-native-1", taskID: "task-2",
            driverRunID: "dr-2", objective: "continue", targetRoot: "/repo",
            provider: "ollama", model: "qwen",
            promptAssemblyDigest: "sha256:" + String(repeating: "a", count: 64)
        )
        let session = CAPTNativeSession(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            missionID: "m-native-1", title: "Private invention",
            createdAt: Date(timeIntervalSince1970: 1_700_000_000),
            updatedAt: Date(timeIntervalSince1970: 1_700_000_001),
            messages: [message], provider: "ollama", model: "qwen",
            targetRoot: "/repo", pendingApproval: pending
        )

        try store.save([session])
        let raw = try Data(contentsOf: file)
        XCTAssertFalse(String(data: raw, encoding: .utf8)?.contains("private invention prompt") ?? false)
        let restored = try store.load()
        XCTAssertEqual(restored, [session])
        XCTAssertEqual(restored.first?.pendingApproval?.requestID, "approval-1")
    }

    func testMissingSessionCacheLoadsEmpty() throws {
        let file = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("native_sessions.enc")
        let key = StaticSessionKeyProvider(bytes: Data(repeating: 0x24, count: 32))
        XCTAssertEqual(try CAPTEncryptedSessionStore(fileURL: file, keyProvider: key).load(), [])
    }
}
