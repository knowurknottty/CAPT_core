import Foundation

public struct CAPTRuntimeProfile: Equatable, Sendable {
    public static let labsBundleIdentifier = "com.inversionlabs.capt.lab"

    public let stateDirectory: String
    public let executableCandidates: [String]
    public let operatorExecutableCandidates: [String]

    public static func resolve(
        home: String,
        environment: [String: String],
        bundleIdentifier: String?
    ) -> CAPTRuntimeProfile {
        let isLabs = bundleIdentifier == labsBundleIdentifier
        let productState = URL(fileURLWithPath: home)
            .appendingPathComponent(isLabs ? ".capt-inversion-labs" : ".capt", isDirectory: true).path
        let stateDirectory: String
        if let override = environment["CAPT_STATE_DIR"], !override.isEmpty {
            stateDirectory = NSString(string: override).expandingTildeInPath
        } else {
            stateDirectory = productState
        }

        var runtimeCandidates: [String] = []
        if let explicit = environment["CAPT_CLI"], !explicit.isEmpty {
            runtimeCandidates.append(NSString(string: explicit).expandingTildeInPath)
        }
        runtimeCandidates.append(
            URL(fileURLWithPath: stateDirectory).appendingPathComponent("runtime-venv/bin/capt").path
        )
        runtimeCandidates.append(
            URL(fileURLWithPath: productState).appendingPathComponent("runtime-venv/bin/capt").path
        )
        runtimeCandidates.append(
            URL(fileURLWithPath: home).appendingPathComponent(".capt/runtime-venv/bin/capt").path
        )
        runtimeCandidates.append(contentsOf: [
            "/opt/homebrew/bin/capt",
            "/usr/local/bin/capt",
            URL(fileURLWithPath: home).appendingPathComponent(".local/bin/capt").path,
        ])

        var operatorCandidates: [String] = []
        if let explicit = environment["CAPT_UI"], !explicit.isEmpty {
            operatorCandidates.append(NSString(string: explicit).expandingTildeInPath)
        }
        if let explicitCLI = environment["CAPT_CLI"], !explicitCLI.isEmpty {
            operatorCandidates.append(
                URL(fileURLWithPath: NSString(string: explicitCLI).expandingTildeInPath)
                    .deletingLastPathComponent().appendingPathComponent("capt-ui").path
            )
        }
        operatorCandidates.append(
            URL(fileURLWithPath: stateDirectory).appendingPathComponent("runtime-venv/bin/capt-ui").path
        )
        operatorCandidates.append(
            URL(fileURLWithPath: productState).appendingPathComponent("runtime-venv/bin/capt-ui").path
        )
        operatorCandidates.append(
            URL(fileURLWithPath: home).appendingPathComponent(".capt/runtime-venv/bin/capt-ui").path
        )
        operatorCandidates.append(contentsOf: [
            "/opt/homebrew/bin/capt-ui",
            "/usr/local/bin/capt-ui",
            URL(fileURLWithPath: home).appendingPathComponent(".local/bin/capt-ui").path,
        ])

        return CAPTRuntimeProfile(
            stateDirectory: stateDirectory,
            executableCandidates: unique(runtimeCandidates),
            operatorExecutableCandidates: unique(operatorCandidates)
        )
    }

    public static func current(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        bundleIdentifier: String? = Bundle.main.bundleIdentifier
    ) -> CAPTRuntimeProfile {
        resolve(
            home: FileManager.default.homeDirectoryForCurrentUser.path,
            environment: environment,
            bundleIdentifier: bundleIdentifier
        )
    }

    public static func resolveExecutable(
        candidates: [String],
        fileExists: (String) -> Bool = { FileManager.default.isExecutableFile(atPath: $0) }
    ) -> String? {
        candidates.first(where: fileExists)
    }

    private static func unique(_ paths: [String]) -> [String] {
        var seen = Set<String>()
        return paths.filter { seen.insert($0).inserted }
    }
}
