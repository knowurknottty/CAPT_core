import Foundation

public struct CAPTProviderSnapshot: Codable, Identifiable, Hashable {
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
public struct CAPTModelSelectionSnapshot: Codable, Hashable {
    public struct Selection: Codable, Hashable {
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

    public init(executablePath: String? = nil) {
        if let executablePath {
            self.executablePath = executablePath
        } else {
            self.executablePath = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent(".capt/runtime-venv/bin/capt-ui").path
        }
    }

    public static func decodeProviders(_ data: Data) throws -> [CAPTProviderSnapshot] {
        do { return try JSONDecoder().decode([CAPTProviderSnapshot].self, from: data) }
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
