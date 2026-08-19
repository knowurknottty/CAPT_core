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
            targetRoot: "/repo", pendingApproval: pending, taskState: "approval_required"
        )

        try store.save([session])
        let raw = try Data(contentsOf: file)
        XCTAssertFalse(String(data: raw, encoding: .utf8)?.contains("private invention prompt") ?? false)
        let restored = try store.load()
        XCTAssertEqual(restored, [session])
        XCTAssertEqual(restored.first?.pendingApproval?.requestID, "approval-1")
        XCTAssertEqual(restored.first?.taskState, "approval_required")
    }

    func testApprovalExpiryClassifierRecognizesRuntimeCode() {
        XCTAssertTrue(CAPTApprovalPresentation.isExpiredMessage(
            "AUTHORITYVIOLATION: MODEL_PROMPT_APPROVAL_EXPIRED"
        ))
        XCTAssertFalse(CAPTApprovalPresentation.isExpiredMessage("socket disconnected"))
    }

    func testApprovalReconciliationRequiresLiveUndecidedAuthority() {
        let pending = CAPTPendingApproval(
            requestID: "approval-1", missionID: "mission-1", taskID: "task-1",
            driverRunID: "driver-1", objective: "continue", targetRoot: "/repo",
            provider: "ollama", model: "qwen",
            promptAssemblyDigest: "sha256:base"
        )
        let future = ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: 2_000_000_000))
        let requested = CAPTApprovalSummary(
            id: "approval-1", missionID: "mission-1", taskID: "task-1",
            operation: "model_prompt", capability: "provider.invoke", risk: "medium",
            state: "requested", decision: nil, remainingUses: 1, expiresAt: future,
            provider: "ollama", model: "qwen", targetRoot: "/repo"
        )
        XCTAssertTrue(CAPTApprovalPresentation.isActionable(
            pending, authoritative: [requested], now: Date(timeIntervalSince1970: 1_900_000_000)
        ))
        let consumed = CAPTApprovalSummary(
            id: requested.id, missionID: requested.missionID, taskID: requested.taskID,
            operation: requested.operation, capability: requested.capability, risk: requested.risk,
            state: "consumed", decision: "approve", remainingUses: 0, expiresAt: requested.expiresAt,
            provider: requested.provider, model: requested.model, targetRoot: requested.targetRoot
        )
        XCTAssertFalse(CAPTApprovalPresentation.isActionable(
            pending, authoritative: [consumed], now: Date(timeIntervalSince1970: 1_900_000_000)
        ))
        XCTAssertFalse(CAPTApprovalPresentation.isActionable(
            pending, authoritative: [], now: Date(timeIntervalSince1970: 1_900_000_000)
        ))
        XCTAssertFalse(CAPTApprovalPresentation.isActionable(
            pending, authoritative: [requested], now: Date(timeIntervalSince1970: 2_100_000_000)
        ))
    }


    func testTamperedCiphertextFailsClosed() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let file = root.appendingPathComponent("native_sessions.enc")
        let key = StaticSessionKeyProvider(bytes: Data(repeating: 0x31, count: 32))
        let store = CAPTEncryptedSessionStore(fileURL: file, keyProvider: key)
        let session = CAPTNativeSession(
            title: "tamper probe", provider: "ollama", model: "qwen", targetRoot: "/repo"
        )
        try store.save([session])
        var raw = try Data(contentsOf: file)
        raw[raw.index(before: raw.endIndex)] ^= 0x01
        try raw.write(to: file, options: .atomic)
        XCTAssertThrowsError(try store.load()) { error in
            guard case CAPTSessionStoreError.malformedCiphertext = error else {
                return XCTFail("expected malformedCiphertext, got \(error)")
            }
        }
    }

    func testWrongSessionKeyFailsClosed() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let file = root.appendingPathComponent("native_sessions.enc")
        let writer = CAPTEncryptedSessionStore(
            fileURL: file,
            keyProvider: StaticSessionKeyProvider(bytes: Data(repeating: 0x41, count: 32))
        )
        try writer.save([CAPTNativeSession(
            title: "wrong key probe", provider: "ollama", model: "qwen", targetRoot: "/repo"
        )])
        let reader = CAPTEncryptedSessionStore(
            fileURL: file,
            keyProvider: StaticSessionKeyProvider(bytes: Data(repeating: 0x42, count: 32))
        )
        XCTAssertThrowsError(try reader.load()) { error in
            guard case CAPTSessionStoreError.malformedCiphertext = error else {
                return XCTFail("expected malformedCiphertext, got \(error)")
            }
        }
    }

    func testEncryptedSessionStoreUsesPrivateFilesystemPermissions() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let file = root.appendingPathComponent("ui/native_sessions.enc")
        let store = CAPTEncryptedSessionStore(
            fileURL: file,
            keyProvider: StaticSessionKeyProvider(bytes: Data(repeating: 0x51, count: 32))
        )
        try store.save([CAPTNativeSession(
            title: "permission probe", provider: "ollama", model: "qwen", targetRoot: "/repo"
        )])
        let dirAttributes = try FileManager.default.attributesOfItem(
            atPath: file.deletingLastPathComponent().path
        )
        let fileAttributes = try FileManager.default.attributesOfItem(atPath: file.path)
        XCTAssertEqual((dirAttributes[.posixPermissions] as? NSNumber)?.intValue, 0o700)
        XCTAssertEqual((fileAttributes[.posixPermissions] as? NSNumber)?.intValue, 0o600)
    }

    func testMissingSessionCacheLoadsEmpty() throws {
        let file = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("native_sessions.enc")
        let key = StaticSessionKeyProvider(bytes: Data(repeating: 0x24, count: 32))
        XCTAssertEqual(try CAPTEncryptedSessionStore(fileURL: file, keyProvider: key).load(), [])
    }
}
