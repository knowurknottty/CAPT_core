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
            role: .user,
            text: "private invention prompt",
            timestamp: Date(timeIntervalSince1970: 1_700_000_000)
        )
        let expiresAt = Date(timeIntervalSince1970: 1_700_000_120)
        let pending = CAPTPendingApproval(
            requestID: "approval-1",
            missionID: "m-native-1",
            taskID: "task-2",
            driverRunID: "dr-2",
            objective: "continue",
            targetRoot: "/repo",
            provider: "ollama",
            model: "qwen",
            promptAssemblyDigest: "sha256:" + String(repeating: "a", count: 64),
            expiresAt: expiresAt
        )
        let session = CAPTNativeSession(
            id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
            missionID: "m-native-1",
            title: "Private invention",
            createdAt: Date(timeIntervalSince1970: 1_700_000_000),
            updatedAt: Date(timeIntervalSince1970: 1_700_000_001),
            messages: [message],
            provider: "ollama",
            model: "qwen",
            targetRoot: "/repo",
            pendingApproval: pending
        )

        try store.save([session])
        let raw = try Data(contentsOf: file)
        XCTAssertFalse(
            String(data: raw, encoding: .utf8)?.contains("private invention prompt") ?? false
        )
        let restored = try store.load()
        XCTAssertEqual(restored, [session])
        XCTAssertEqual(restored.first?.pendingApproval?.requestID, "approval-1")
        XCTAssertEqual(restored.first?.pendingApproval?.expiresAt, expiresAt)
    }

    func testDefaultClassicSessionCacheDoesNotUseLegacySharedFilename() {
        XCTAssertEqual(
            CAPTEncryptedSessionStore.defaultFileURL().lastPathComponent,
            "classic_native_sessions.enc"
        )
    }

    func testClassicCacheMigratesLegacySessionsAndQuarantinesUnknownApproval() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let ui = root.appendingPathComponent("ui", isDirectory: true)
        let legacyFile = ui.appendingPathComponent("native_sessions.enc")
        let classicFile = ui.appendingPathComponent("classic_native_sessions.enc")
        let key = StaticSessionKeyProvider(bytes: Data(repeating: 0x33, count: 32))
        let pending = CAPTPendingApproval(
            requestID: "approval-legacy",
            missionID: "mission-legacy",
            taskID: "task-legacy",
            driverRunID: "driver-legacy",
            objective: "legacy request",
            targetRoot: "/repo",
            provider: "openrouter",
            model: "model",
            promptAssemblyDigest: "sha256:" + String(repeating: "b", count: 64),
            expiresAt: nil
        )
        let historical = CAPTNativeSession(
            title: "Historical",
            messages: [CAPTChatMessage(role: .user, text: "keep this transcript")],
            provider: "openrouter",
            model: "model",
            targetRoot: "/repo",
            pendingApproval: pending
        )
        try CAPTEncryptedSessionStore(fileURL: legacyFile, keyProvider: key).save([historical])

        let classic = CAPTEncryptedSessionStore(fileURL: classicFile, keyProvider: key)
        let restored = try classic.load()

        XCTAssertEqual(restored.count, 1)
        XCTAssertEqual(restored.first?.messages.first?.text, "keep this transcript")
        XCTAssertNil(restored.first?.pendingApproval)
        XCTAssertTrue(FileManager.default.fileExists(atPath: classicFile.path))
    }

    func testClassicCacheMigrationPreservesStillValidBoundApproval() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let ui = root.appendingPathComponent("ui", isDirectory: true)
        let legacyFile = ui.appendingPathComponent("native_sessions.enc")
        let classicFile = ui.appendingPathComponent("classic_native_sessions.enc")
        let key = StaticSessionKeyProvider(bytes: Data(repeating: 0x44, count: 32))
        let expiresAt = Date().addingTimeInterval(3_600)
        let pending = CAPTPendingApproval(
            requestID: "approval-valid",
            missionID: "mission-valid",
            taskID: "task-valid",
            driverRunID: "driver-valid",
            objective: "recover valid approval",
            targetRoot: "/repo",
            provider: "openrouter",
            model: "model",
            promptAssemblyDigest: "sha256:" + String(repeating: "c", count: 64),
            expiresAt: expiresAt
        )
        let historical = CAPTNativeSession(
            title: "Recoverable", provider: "openrouter", model: "model",
            targetRoot: "/repo", pendingApproval: pending
        )
        try CAPTEncryptedSessionStore(fileURL: legacyFile, keyProvider: key).save([historical])

        let restored = try CAPTEncryptedSessionStore(
            fileURL: classicFile, keyProvider: key
        ).load()

        XCTAssertEqual(restored.first?.pendingApproval?.requestID, "approval-valid")
        XCTAssertEqual(restored.first?.pendingApproval?.expiresAt, expiresAt)
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

    func testEncryptedSessionStoreRepairsExistingDirectoryPermissions() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let directory = root.appendingPathComponent("ui", isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o755]
        )
        let file = directory.appendingPathComponent("native_sessions.enc")
        let store = CAPTEncryptedSessionStore(
            fileURL: file,
            keyProvider: StaticSessionKeyProvider(bytes: Data(repeating: 0x52, count: 32))
        )
        try store.save([CAPTNativeSession(
            title: "permission repair", provider: "ollama", model: "qwen", targetRoot: "/repo"
        )])
        let attributes = try FileManager.default.attributesOfItem(atPath: directory.path)
        XCTAssertEqual((attributes[.posixPermissions] as? NSNumber)?.intValue, 0o700)
    }

    func testPendingApprovalDecodesLegacyPayloadWithoutSkillNames() throws {
        let data = try JSONSerialization.data(withJSONObject: [
            "requestID": "approval-legacy-shape",
            "missionID": "mission-legacy-shape",
            "taskID": "task-legacy-shape",
            "driverRunID": "run-legacy-shape",
            "objective": "legacy",
            "targetRoot": "/repo",
            "provider": "ollama",
            "model": "qwen",
            "promptAssemblyDigest": "sha256:" + String(repeating: "d", count: 64),
        ])
        let decoded = try JSONDecoder().decode(CAPTPendingApproval.self, from: data)
        XCTAssertEqual(decoded.requestID, "approval-legacy-shape")
        XCTAssertEqual(decoded.skillNames, [])
    }

    func testMissingSessionCacheLoadsEmpty() throws {
        let file = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathComponent("native_sessions.enc")
        let key = StaticSessionKeyProvider(bytes: Data(repeating: 0x24, count: 32))
        XCTAssertEqual(
            try CAPTEncryptedSessionStore(fileURL: file, keyProvider: key).load(),
            []
        )
    }
}

extension CAPTNativeSessionStoreTests {
    func testEncryptedSessionStoreRoundTripsPromptProposal() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let file = root.appendingPathComponent("native_sessions.enc")
        let key = StaticSessionKeyProvider(bytes: Data(repeating: 0x61, count: 32))
        let proposal = try CAPTPromptProposal(dictionary: [
            "proposalId": "pp-cache", "revision": 1, "state": "active",
            "status": "ready_for_approval", "originalPrompt": "private prompt",
            "proposedPrompt": "compiled private prompt", "originalPromptDigest": "sha256:o",
            "proposedPromptDigest": "sha256:p", "stageChain": ["OMNI", "META"],
            "stageRecords": [], "verificationContract": ["acceptanceCriteria": ["proof"]],
            "unresolvedQuestions": [], "targetRoot": "/repo", "rationale": "route"
        ])
        let session = CAPTNativeSession(
            title: "Proposal", provider: "mtplx", model: "qwen", targetRoot: "/repo",
            promptProposal: proposal
        )
        let store = CAPTEncryptedSessionStore(fileURL: file, keyProvider: key)
        try store.save([session])
        let restored = try store.load()
        XCTAssertEqual(restored.first?.promptProposal?.proposalID, "pp-cache")
        XCTAssertFalse(String(data: try Data(contentsOf: file), encoding: .utf8)?.contains("private prompt") ?? false)
    }
}
