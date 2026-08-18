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
        environment: [String: String] = ProcessInfo.processInfo.environment
    ) {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        if let stateDirectory {
            self.stateDirectory = NSString(string: stateDirectory).expandingTildeInPath
        } else if let override = environment["CAPT_STATE_DIR"], !override.isEmpty {
            self.stateDirectory = NSString(string: override).expandingTildeInPath
        } else {
            self.stateDirectory = URL(fileURLWithPath: home)
                .appendingPathComponent(".capt", isDirectory: true).path
        }
        self.executableCandidates = Self.defaultCandidates(
            home: home, environment: environment
        )
    }

    public static func defaultCandidates(
        home: String,
        environment: [String: String]
    ) -> [String] {
        var paths: [String] = []
        if let explicit = environment["CAPT_CLI"], !explicit.isEmpty {
            paths.append(NSString(string: explicit).expandingTildeInPath)
        }
        paths.append(URL(fileURLWithPath: home)
            .appendingPathComponent(".capt/runtime-venv/bin/capt").path)
        paths.append(contentsOf: [
            "/opt/homebrew/bin/capt",
            "/usr/local/bin/capt",
            URL(fileURLWithPath: home).appendingPathComponent(".local/bin/capt").path,
        ])
        var seen = Set<String>()
        return paths.filter { seen.insert($0).inserted }
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
