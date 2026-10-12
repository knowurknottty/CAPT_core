import Foundation
import XCTest
@testable import CAPTCoreDesktop

final class CAPTProviderNetworkPolicyTests: XCTestCase {
    func testOpenRouterCannotUseLocalOnlyWithDefaultSettings() {
        let settings = CAPTExecutionAuthoritySettings.default
        XCTAssertEqual(settings.providerNetwork, .localOnly)
        XCTAssertEqual(settings.effectiveProviderNetwork(for: "openrouter"), .remoteAllowed)
        XCTAssertEqual(settings.effectiveProviderNetwork(for: " OpenRouter "), .remoteAllowed)
    }

    func testLocalProviderRetainsExplicitLocalOnly() {
        let settings = CAPTExecutionAuthoritySettings.default
        XCTAssertEqual(settings.effectiveProviderNetwork(for: "ollama"), .localOnly)
        XCTAssertEqual(settings.effectiveProviderNetwork(for: "llama.cpp"), .localOnly)
    }
}
