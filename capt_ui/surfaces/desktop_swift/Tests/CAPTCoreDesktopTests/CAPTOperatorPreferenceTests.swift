@testable import CAPTCoreDesktop
import Foundation
import XCTest

final class CAPTOperatorPreferenceTests: XCTestCase {
    func testPreferenceResolverPrefersOperatorSelectionOverSessionFallback() throws {
        let providersJSON = """
        [
          {"id":"ollama","name":"Ollama","kind":"local","transport":"ollama","key_ref":"<none>","context_limit":8192,"enabled":true,"selected":false,"health":"green","latency_ms":19,"models":["old-model"],"capabilities":["chat"]},
          {"id":"openrouter","name":"OpenRouter","kind":"cloud","transport":"openai_compatible","key_ref":"keychain:openrouter","context_limit":1048576,"enabled":true,"selected":true,"health":"green","latency_ms":50,"models":["z-ai/glm-5.3-flash"],"capabilities":["chat"]}
        ]
        """
        let modelsJSON = """
        {"active":"z-ai/glm-5.3-flash","provider":"OpenRouter","kind":"REMOTE","default":{"provider":"openrouter","model":"z-ai/glm-5.3-flash"},"available":["z-ai/glm-5.3-flash"],"favorites":[]}
        """
        let providers = try CAPTOperatorCLI.decodeProviders(Data(providersJSON.utf8))
        let models = try CAPTOperatorCLI.decodeModels(Data(modelsJSON.utf8))
        let selection = CAPTOperatorPreferenceResolver.resolve(
            providers: providers,
            models: models,
            fallbackProvider: "ollama",
            fallbackModel: "old-model"
        )
        XCTAssertEqual(selection.providerID, "openrouter")
        XCTAssertEqual(selection.modelID, "z-ai/glm-5.3-flash")
    }

    func testOperatorStateLoaderDoesNotRequireRuntimeService() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("capt-operator-loader-" + UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let script = root.appendingPathComponent("capt-ui")
        let body = #"""
#!/bin/zsh
case "$1" in
  providers) print '[{"id":"openrouter","name":"OpenRouter","kind":"cloud","transport":"openai_compatible","key_ref":"keychain:openrouter","context_limit":1048576,"enabled":true,"selected":true,"health":"green","latency_ms":42,"models":["z-ai/glm-5.3-flash"],"capabilities":["chat"]}]' ;;
  models) print '{"active":"z-ai/glm-5.3-flash","provider":"OpenRouter","kind":"REMOTE","default":{"provider":"openrouter","model":"z-ai/glm-5.3-flash"},"available":["z-ai/glm-5.3-flash"],"favorites":[]}' ;;
  verbosity) print '{"verbosity":"detailed"}' ;;
  *) exit 9 ;;
esac
"""#
        try body.write(to: script, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: script.path)
        let cli = CAPTOperatorCLI(executablePath: script.path, stateDirectory: root.path)
        let snapshot = try CAPTOperatorStateLoader(cli: cli).load()
        XCTAssertEqual(snapshot.providers.map(\.id), ["openrouter"])
        XCTAssertEqual(snapshot.models.defaultSelection?.provider, "openrouter")
        XCTAssertEqual(snapshot.verbosity, "detailed")
    }
}
