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
}
