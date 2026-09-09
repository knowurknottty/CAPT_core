import Foundation

public enum CAPTFilesystemScopeMode: String, Codable, CaseIterable, Sendable {
    case project
    case custom
    case full
}

public enum CAPTProviderNetworkPolicy: String, Codable, CaseIterable, Sendable {
    case localOnly = "local_only"
    case remoteAllowed = "remote_allowed"
}

public struct CAPTExecutionAuthoritySettings: Codable, Equatable, Sendable {
    public var filesystemScope: CAPTFilesystemScopeMode
    public var customFilesystemRoot: String
    public var fileMutationAllowed: Bool
    public var shellAccessAllowed: Bool
    public var providerNetwork: CAPTProviderNetworkPolicy
    public var remotePromptCompilationAllowed: Bool

    public init(
        filesystemScope: CAPTFilesystemScopeMode,
        customFilesystemRoot: String,
        fileMutationAllowed: Bool,
        shellAccessAllowed: Bool,
        providerNetwork: CAPTProviderNetworkPolicy,
        remotePromptCompilationAllowed: Bool
    ) {
        self.filesystemScope = filesystemScope
        self.customFilesystemRoot = customFilesystemRoot
        self.fileMutationAllowed = fileMutationAllowed
        self.shellAccessAllowed = shellAccessAllowed
        self.providerNetwork = providerNetwork
        self.remotePromptCompilationAllowed = remotePromptCompilationAllowed
    }

    public static let `default` = CAPTExecutionAuthoritySettings(
        filesystemScope: .project,
        customFilesystemRoot: "",
        fileMutationAllowed: false,
        shellAccessAllowed: false,
        providerNetwork: .localOnly,
        remotePromptCompilationAllowed: false
    )

    public func effectiveFilesystemRoot(projectRoot: String) -> String? {
        switch filesystemScope {
        case .project:
            let root = projectRoot.trimmingCharacters(in: .whitespacesAndNewlines)
            return root.isEmpty ? nil : root
        case .custom:
            let root = customFilesystemRoot.trimmingCharacters(in: .whitespacesAndNewlines)
            return root.isEmpty ? nil : root
        case .full:
            return "/"
        }
    }

    public var isHighRisk: Bool {
        filesystemScope == .full ||
            fileMutationAllowed ||
            shellAccessAllowed ||
            providerNetwork == .remoteAllowed
    }
}
