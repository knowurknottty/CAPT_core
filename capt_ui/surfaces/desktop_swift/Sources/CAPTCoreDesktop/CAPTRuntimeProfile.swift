import Foundation

public struct CAPTRuntimeProfile: Equatable, Sendable {
    public static let standardBundleIdentifier = "com.inversionlabs.capt"
    public static let labsBundleIdentifier = "com.inversionlabs.capt.lab"

    public let stateDirectory: String
    public let runtimeExecutableCandidates: [String]
    public let operatorExecutableCandidates: [String]

    public static func resolve(
        home: String,
        environment: [String: String],
        bundleIdentifier: String?
    ) -> CAPTRuntimeProfile {
        let productDirectory = bundleIdentifier == labsBundleIdentifier
            ? ".capt-inversion-labs" : ".capt"
        let productState = URL(fileURLWithPath: home)
            .appendingPathComponent(productDirectory, isDirectory: true).path
        let rawOverride = environment["CAPT_STATE_DIR"] ?? environment["CAPT_SOLO_HOME"]
        let stateDirectory = rawOverride.flatMap { $0.isEmpty ? nil : $0 }
            .map { NSString(string: $0).expandingTildeInPath } ?? productState

        var runtime: [String] = []
        if rawOverride?.isEmpty == false {
            runtime.append(URL(fileURLWithPath: stateDirectory)
                .appendingPathComponent("runtime-venv/bin/capt").path)
        } else if let explicit = environment["CAPT_CLI"], !explicit.isEmpty {
            runtime.append(NSString(string: explicit).expandingTildeInPath)
            runtime.append(URL(fileURLWithPath: productState)
                .appendingPathComponent("runtime-venv/bin/capt").path)
        } else {
            runtime.append(URL(fileURLWithPath: stateDirectory)
                .appendingPathComponent("runtime-venv/bin/capt").path)
        }
        runtime.append(contentsOf: [
            "/opt/homebrew/bin/capt",
            "/usr/local/bin/capt",
            URL(fileURLWithPath: home).appendingPathComponent(".local/bin/capt").path,
        ])

        var operatorCandidates: [String] = []
        if rawOverride?.isEmpty == false {
            operatorCandidates.append(URL(fileURLWithPath: stateDirectory)
                .appendingPathComponent("runtime-venv/bin/capt-ui").path)
        } else if let explicit = environment["CAPT_UI"], !explicit.isEmpty {
            operatorCandidates.append(NSString(string: explicit).expandingTildeInPath)
            operatorCandidates.append(URL(fileURLWithPath: productState)
                .appendingPathComponent("runtime-venv/bin/capt-ui").path)
        } else if let explicitCLI = environment["CAPT_CLI"], !explicitCLI.isEmpty {
            operatorCandidates.append(URL(fileURLWithPath: NSString(string: explicitCLI).expandingTildeInPath)
                .deletingLastPathComponent().appendingPathComponent("capt-ui").path)
            operatorCandidates.append(URL(fileURLWithPath: productState)
                .appendingPathComponent("runtime-venv/bin/capt-ui").path)
        } else {
            operatorCandidates.append(URL(fileURLWithPath: stateDirectory)
                .appendingPathComponent("runtime-venv/bin/capt-ui").path)
        }
        operatorCandidates.append(contentsOf: [
            "/opt/homebrew/bin/capt-ui",
            "/usr/local/bin/capt-ui",
            URL(fileURLWithPath: home).appendingPathComponent(".local/bin/capt-ui").path,
        ])

        return CAPTRuntimeProfile(
            stateDirectory: stateDirectory,
            runtimeExecutableCandidates: unique(runtime),
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

    private static func unique(_ paths: [String]) -> [String] {
        var seen = Set<String>()
        return paths.filter { seen.insert($0).inserted }
    }
}
