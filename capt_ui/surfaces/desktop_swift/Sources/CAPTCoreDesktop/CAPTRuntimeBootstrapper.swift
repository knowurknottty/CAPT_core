import Foundation

public enum CAPTRuntimeBootstrapError: Error, LocalizedError {
    case executableNotFound([String])
    case launchFailed(String)

    public var errorDescription: String? {
        switch self {
        case .executableNotFound(let paths):
            return "CAPT CLI not found. Checked: " + paths.joined(separator: ", ")
        case .launchFailed(let message):
            return "CAPT runtime launch failed: \(message)"
        }
    }
}

public struct CAPTRuntimeBootstrapper {
    public let stateDirectory: String
    public let executableCandidates: [String]

    public init(
        stateDirectory: String? = nil,
        environment: [String: String] = ProcessInfo.processInfo.environment,
        bundleIdentifier: String? = Bundle.main.bundleIdentifier
    ) {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        var effectiveEnvironment = environment
        if let stateDirectory {
            effectiveEnvironment["CAPT_STATE_DIR"] =
                NSString(string: stateDirectory).expandingTildeInPath
        }
        let profile = CAPTRuntimeProfile.resolve(
            home: home,
            environment: effectiveEnvironment,
            bundleIdentifier: bundleIdentifier
        )
        self.stateDirectory = profile.stateDirectory
        self.executableCandidates = profile.executableCandidates
    }

    public static func defaultCandidates(
        home: String,
        environment: [String: String],
        bundleIdentifier: String? = Bundle.main.bundleIdentifier
    ) -> [String] {
        CAPTRuntimeProfile.resolve(
            home: home, environment: environment, bundleIdentifier: bundleIdentifier
        ).executableCandidates
    }

    public func resolvedExecutable(
        fileExists: (String) -> Bool = { FileManager.default.isExecutableFile(atPath: $0) }
    ) -> String? {
        executableCandidates.first(where: fileExists)
    }

    public func start() throws {
        guard let executable = resolvedExecutable() else {
            throw CAPTRuntimeBootstrapError.executableNotFound(executableCandidates)
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = ["start", "--state-dir", stateDirectory]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            throw CAPTRuntimeBootstrapError.launchFailed(error.localizedDescription)
        }
        guard process.terminationStatus == 0 else {
            throw CAPTRuntimeBootstrapError.launchFailed(
                "capt start exited with status \(process.terminationStatus)"
            )
        }
    }
}
