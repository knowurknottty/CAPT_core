import XCTest
@testable import CAPTCoreDesktop

final class CAPTOperatorCLITests: XCTestCase {
    func testProviderSnapshotDecodesRedactedOperatorState() throws {
        let json = """
        [{"id":"ollama","name":"Ollama","kind":"local","transport":"ollama",
          "key_ref":"<none>","context_limit":8192,"enabled":true,
          "selected":true,"health":"green","latency_ms":19,
          "models":["qwen3.6-fable-fusion:latest"],"capabilities":["chat"]}]
        """
        let providers = try CAPTOperatorCLI.decodeProviders(Data(json.utf8))
        XCTAssertEqual(providers.count, 1)
        XCTAssertEqual(providers[0].id, "ollama")
        XCTAssertTrue(providers[0].selected)
        XCTAssertEqual(providers[0].health, "green")
        XCTAssertEqual(providers[0].models.first, "qwen3.6-fable-fusion:latest")
    }
    func testModelSnapshotDecodesDefaultAndAvailableModels() throws {
        let json = """
        {"active":"qwen3.6-fable-fusion:latest","provider":"Ollama","kind":"LOCAL",
         "default":{"provider":"ollama","model":"qwen3.6-fable-fusion:latest"},
         "available":["qwen3.6-fable-fusion:latest","ornith-1.0-9b:latest"],
         "favorites":[]}
        """
        let models = try CAPTOperatorCLI.decodeModels(Data(json.utf8))
        XCTAssertEqual(models.active, "qwen3.6-fable-fusion:latest")
        XCTAssertEqual(models.defaultSelection?.provider, "ollama")
        XCTAssertEqual(models.available.count, 2)
    }

    func testVerbositySnapshotDecodesPresentationPreference() throws {
        let json = #"{"verbosity":"detailed"}"#
        let value = try CAPTOperatorCLI.decodeVerbosity(Data(json.utf8))
        XCTAssertEqual(value, "detailed")
    }
}

extension CAPTOperatorCLITests {
    func testSecretReferenceValidationRejectsRawCredential() {
        XCTAssertTrue(CAPTOperatorCLI.isSafeSecretReference("env:OPENROUTER_API_KEY"))
        XCTAssertTrue(CAPTOperatorCLI.isSafeSecretReference("keychain:openrouter"))
        XCTAssertFalse(CAPTOperatorCLI.isSafeSecretReference("sk-raw-secret"))
        XCTAssertFalse(CAPTOperatorCLI.isSafeSecretReference("OPENROUTER_API_KEY"))
    }
    func testPrewarmProviderArgumentsAreBoundToProviderAndModel() {
        XCTAssertEqual(
            CAPTOperatorCLI.prewarmArguments(
                providerID: "mtplx", modelID: "qwen3.8-27b-mtplx"
            ),
            ["providers", "--prewarm", "mtplx", "--model", "qwen3.8-27b-mtplx", "--json"]
        )
    }

    func testDecodeProviderWarmup() throws {
        let data = Data(#"{"status":"warm","provider":"mtplx","model":"qwen3.8-27b-mtplx","endpoint_class":"local","latency_ms":1234}"#.utf8)
        let snapshot = try CAPTOperatorCLI.decodeProviderWarmup(data)
        XCTAssertEqual(snapshot.status, "warm")
        XCTAssertEqual(snapshot.provider, "mtplx")
        XCTAssertEqual(snapshot.model, "qwen3.8-27b-mtplx")
        XCTAssertEqual(snapshot.endpointClass, "local")
        XCTAssertEqual(snapshot.latencyMs, 1234)
    }

    func testPrewarmPolicyOnlyTargetsLocalOpenAICompatibleProviders() throws {
        let local = try CAPTOperatorCLI.decodeProviders(Data(#"[{"id":"mtplx","name":"MTPLX","kind":"local","transport":"openai_compatible","key_ref":"","context_limit":262144,"enabled":true,"selected":true,"health":"green","models":["qwen3.8-27b-mtplx"],"capabilities":["chat"]}]"#.utf8))[0]
        let ollama = try CAPTOperatorCLI.decodeProviders(Data(#"[{"id":"ollama","name":"Ollama","kind":"local","transport":"ollama","key_ref":"","context_limit":8192,"enabled":true,"selected":true,"health":"green","models":["m"],"capabilities":["chat"]}]"#.utf8))[0]
        XCTAssertTrue(CAPTOperatorCLI.requiresPrewarm(local, modelID: "qwen3.8-27b-mtplx"))
        XCTAssertFalse(CAPTOperatorCLI.requiresPrewarm(ollama, modelID: "m"))
        XCTAssertFalse(CAPTOperatorCLI.requiresPrewarm(local, modelID: ""))
    }

}
