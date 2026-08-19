import Foundation

public struct CAPTProviderSnapshot: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let name: String
    public let kind: String
    public let transport: String
    public let keyRef: String
    public let contextLimit: Int
    public let enabled: Bool
    public let selected: Bool
    public let health: String
    public let latencyMs: Int?
    public let models: [String]
    public let capabilities: [String]

    enum CodingKeys: String, CodingKey {
        case id, name, kind, transport, enabled, selected, health, models, capabilities
        case keyRef = "key_ref"
        case contextLimit = "context_limit"
        case latencyMs = "latency_ms"
    }
}
public struct CAPTProviderWarmupSnapshot: Codable, Hashable, Sendable {
    public let status: String
    public let provider: String
    public let model: String
    public let endpointClass: String
    public let latencyMs: Int

    enum CodingKeys: String, CodingKey {
        case status, provider, model
        case endpointClass = "endpoint_class"
        case latencyMs = "latency_ms"
    }
}

public struct CAPTModelSelectionSnapshot: Codable, Hashable, Sendable {
    public struct Selection: Codable, Hashable, Sendable {
        public let provider: String
        public let model: String
    }

    public let active: String
    public let provider: String
    public let kind: String
    public let defaultSelection: Selection?
    public let available: [String]
    public let favorites: [String]

    enum CodingKeys: String, CodingKey {
        case active, provider, kind, available, favorites
        case defaultSelection = "default"
    }
}

public struct CAPTOperatorStateSnapshot: Equatable, Sendable {
    public let providers: [CAPTProviderSnapshot]
    public let models: CAPTModelSelectionSnapshot
    public let verbosity: String

    public init(
        providers: [CAPTProviderSnapshot],
        models: CAPTModelSelectionSnapshot,
        verbosity: String
    ) {
        self.providers = providers
        self.models = models
        self.verbosity = verbosity
    }
}

public enum CAPTOperatorCLIError: Error, LocalizedError {
    case executableMissing(String)
    case commandFailed(String)
    case malformedJSON(String)

    public var errorDescription: String? {
        switch self {
        case .executableMissing(let path): return "CAPT operator CLI missing at \(path)"
        case .commandFailed(let message): return message
        case .malformedJSON(let message): return "Malformed CAPT operator JSON: \(message)"
        }
    }
}
public struct CAPTOperatorCLI {
    public let executablePath: String
    public let stateDirectory: String?

    public init(executablePath: String? = nil, stateDirectory: String? = nil) {
        self.stateDirectory = stateDirectory.map { NSString(string: $0).expandingTildeInPath }
        if let executablePath {
            self.executablePath = executablePath
        } else {
            self.executablePath = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".capt/runtime-venv/bin/capt-ui").path
        }
    }

    public static func isSafeSecretReference(_ value: String) -> Bool {
        value.hasPrefix("env:") || value.hasPrefix("keychain:")
    }

    public static func decodeProviders(_ data: Data) throws -> [CAPTProviderSnapshot] {
        do { return try JSONDecoder().decode([CAPTProviderSnapshot].self, from: data) }
        catch { throw CAPTOperatorCLIError.malformedJSON(error.localizedDescription) }
    }

    public static func requiresPrewarm(_ provider: CAPTProviderSnapshot, modelID: String) -> Bool {
        provider.kind.lowercased() == "local" &&
            provider.transport == "openai_compatible" &&
            provider.enabled && !modelID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    public static func newChatSelection(
        models: CAPTModelSelectionSnapshot, selectedProviderID: String?,
        fallbackProvider: String, fallbackModel: String
    ) -> CAPTModelSelectionSnapshot.Selection {
        if let configured = models.defaultSelection,
           !configured.provider.isEmpty, !configured.model.isEmpty {
            return configured
        }
        if let selectedProviderID, !selectedProviderID.isEmpty, !models.active.isEmpty {
            return .init(provider: selectedProviderID, model: models.active)
        }
        return .init(provider: fallbackProvider, model: fallbackModel)
    }

    public static func prewarmArguments(providerID: String, modelID: String) -> [String] {
        ["providers", "--prewarm", providerID, "--model", modelID, "--json"]
    }

    public static func decodeProviderWarmup(_ data: Data) throws -> CAPTProviderWarmupSnapshot {
        do { return try JSONDecoder().decode(CAPTProviderWarmupSnapshot.self, from: data) }
        catch { throw CAPTOperatorCLIError.malformedJSON(error.localizedDescription) }
    }

    public static func decodeModels(_ data: Data) throws -> CAPTModelSelectionSnapshot {
        do { return try JSONDecoder().decode(CAPTModelSelectionSnapshot.self, from: data) }
        catch { throw CAPTOperatorCLIError.malformedJSON(error.localizedDescription) }
    }

    public static func decodeVerbosity(_ data: Data) throws -> String {
        do {
            let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            guard let value = obj?["verbosity"] as? String else {
                throw CAPTOperatorCLIError.malformedJSON("missing verbosity")
            }
            return value
        } catch let error as CAPTOperatorCLIError { throw error }
        catch { throw CAPTOperatorCLIError.malformedJSON(error.localizedDescription) }
    }
    public func providers() throws -> [CAPTProviderSnapshot] {
        try Self.decodeProviders(run(["providers", "--json"]))
    }

    public func models() throws -> CAPTModelSelectionSnapshot {
        try Self.decodeModels(run(["models", "--json"]))
    }

    public func verbosity() throws -> String {
        try Self.decodeVerbosity(run(["verbosity", "--json"]))
    }

    public func activateProvider(_ providerID: String) throws -> [CAPTProviderSnapshot] {
        _ = try run(["providers", "--activate", providerID, "--json"])
        return try providers()
    }

    public func testProvider(_ providerID: String) throws -> [CAPTProviderSnapshot] {
        _ = try run(["providers", "--test", providerID, "--json"])
        return try providers()
    }

    public func prewarmProvider(providerID: String, modelID: String) throws -> CAPTProviderWarmupSnapshot {
        try Self.decodeProviderWarmup(run(Self.prewarmArguments(providerID: providerID, modelID: modelID)))
    }

    public func setProviderKeyReference(_ providerID: String, reference: String) throws -> [CAPTProviderSnapshot] {
        guard Self.isSafeSecretReference(reference) else {
            throw CAPTOperatorCLIError.commandFailed("Credential must be an env: or keychain: reference; raw secrets are rejected")
        }
        _ = try run(["providers", "--key-ref", providerID, reference, "--json"])
        return try providers()
    }

    public func setDefaultModel(providerID: String, modelID: String) throws -> CAPTModelSelectionSnapshot {
        _ = try run(["models", "--set", "\(providerID)/\(modelID)", "--json"])
        return try models()
    }

    public func setVerbosity(_ value: String) throws -> String {
        _ = try run(["verbosity", "--set", value, "--json"])
        return try verbosity()
    }
    @discardableResult
    private func run(_ arguments: [String]) throws -> Data {
        guard FileManager.default.isExecutableFile(atPath: executablePath) else {
            throw CAPTOperatorCLIError.executableMissing(executablePath)
        }
        let process = Process()
        let stdout = Pipe()
        let stderr = Pipe()
        process.executableURL = URL(fileURLWithPath: executablePath)
        process.arguments = arguments
        if let stateDirectory {
            var environment = ProcessInfo.processInfo.environment
            environment["CAPT_STATE_DIR"] = stateDirectory
            process.environment = environment
        }
        process.standardOutput = stdout
        process.standardError = stderr
        do { try process.run() }
        catch { throw CAPTOperatorCLIError.commandFailed(error.localizedDescription) }
        process.waitUntilExit()
        let out = stdout.fileHandleForReading.readDataToEndOfFile()
        let err = stderr.fileHandleForReading.readDataToEndOfFile()
        guard process.terminationStatus == 0 else {
            let text = String(data: err.isEmpty ? out : err, encoding: .utf8) ?? "operator command failed"
            throw CAPTOperatorCLIError.commandFailed(text.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return out
    }
}
