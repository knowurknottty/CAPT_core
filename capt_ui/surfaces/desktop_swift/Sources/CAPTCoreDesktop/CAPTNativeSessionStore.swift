import Foundation
import CryptoKit
import Security

public struct CAPTNativeSession: Identifiable, Codable, Equatable, Sendable {
    public let id: UUID
    public var missionID: String?
    public var title: String
    public let createdAt: Date
    public var updatedAt: Date
    public var messages: [CAPTChatMessage]
    public var provider: String
    public var model: String
    public var targetRoot: String
    public var pendingApproval: CAPTPendingApproval?

    public init(
        id: UUID = UUID(), missionID: String? = nil, title: String,
        createdAt: Date = Date(), updatedAt: Date = Date(),
        messages: [CAPTChatMessage] = [], provider: String,
        model: String, targetRoot: String, pendingApproval: CAPTPendingApproval? = nil
    ) {
        self.id = id
        self.missionID = missionID
        self.title = title
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.messages = messages
        self.provider = provider
        self.model = model
        self.targetRoot = targetRoot
        self.pendingApproval = pendingApproval
    }
}

public protocol CAPTSessionKeyProviding: Sendable {
    func keyData() throws -> Data
}

public enum CAPTSessionStoreError: Error {
    case keychain(OSStatus)
    case invalidKey
    case malformedCiphertext
}

public struct CAPTKeychainSessionKeyProvider: CAPTSessionKeyProviding {
    private let service: String
    private let account: String

    public init(
        service: String = "com.inversionlabs.capt.native-session-cache",
        account: String = "session-key-v1"
    ) {
        self.service = service
        self.account = account
    }

    public func keyData() throws -> Data {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecSuccess, let data = item as? Data {
            guard data.count == 32 else { throw CAPTSessionStoreError.invalidKey }
            return data
        }
        guard status == errSecItemNotFound else {
            throw CAPTSessionStoreError.keychain(status)
        }
        return try createKey()
    }

    private func createKey() throws -> Data {
        var bytes = [UInt8](repeating: 0, count: 32)
        let randomStatus = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        guard randomStatus == errSecSuccess else {
            throw CAPTSessionStoreError.keychain(randomStatus)
        }
        let data = Data(bytes)
        let add: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
            kSecValueData as String: data,
        ]
        let status = SecItemAdd(add as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw CAPTSessionStoreError.keychain(status)
        }
        return data
    }
}

public final class CAPTEncryptedSessionStore: @unchecked Sendable {
    public let fileURL: URL
    private let keyProvider: any CAPTSessionKeyProviding

    public init(
        fileURL: URL = CAPTEncryptedSessionStore.defaultFileURL(),
        keyProvider: any CAPTSessionKeyProviding = CAPTKeychainSessionKeyProvider()
    ) {
        self.fileURL = fileURL
        self.keyProvider = keyProvider
    }

    public static func defaultFileURL() -> URL {
        let env = ProcessInfo.processInfo.environment
        let root: URL
        if let override = env["CAPT_STATE_DIR"] ?? env["CAPT_SOLO_HOME"], !override.isEmpty {
            root = URL(fileURLWithPath: NSString(string: override).expandingTildeInPath)
        } else {
            root = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".capt", isDirectory: true)
        }
        return root.appendingPathComponent("ui", isDirectory: true)
            .appendingPathComponent("native_sessions.enc")
    }

    public func load() throws -> [CAPTNativeSession] {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return [] }
        let combined = try Data(contentsOf: fileURL)
        let keyData = try keyProvider.keyData()
        guard keyData.count == 32 else { throw CAPTSessionStoreError.invalidKey }
        do {
            let box = try AES.GCM.SealedBox(combined: combined)
            let clear = try AES.GCM.open(box, using: SymmetricKey(data: keyData))
            return try JSONDecoder().decode([CAPTNativeSession].self, from: clear)
        } catch let error as CAPTSessionStoreError {
            throw error
        } catch {
            throw CAPTSessionStoreError.malformedCiphertext
        }
    }

    public func save(_ sessions: [CAPTNativeSession]) throws {
        let directory = fileURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        let clear = try JSONEncoder().encode(sessions)
        let keyData = try keyProvider.keyData()
        guard keyData.count == 32 else { throw CAPTSessionStoreError.invalidKey }
        let sealed = try AES.GCM.seal(clear, using: SymmetricKey(data: keyData))
        guard let combined = sealed.combined else {
            throw CAPTSessionStoreError.malformedCiphertext
        }
        try combined.write(to: fileURL, options: .atomic)
        try FileManager.default.setAttributes(
            [.posixPermissions: 0o600], ofItemAtPath: fileURL.path
        )
    }
}
