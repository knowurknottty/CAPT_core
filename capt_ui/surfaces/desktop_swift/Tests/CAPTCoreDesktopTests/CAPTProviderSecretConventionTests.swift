import XCTest
@testable import CAPTCoreDesktop

final class CAPTProviderSecretConventionTests: XCTestCase {
    func testOpenRouterUsesRuntimeKeychainContract() {
        let location = CAPTProviderSecretConvention.location(providerID: "openrouter")
        XCTAssertEqual(location.service, "capt-provider")
        XCTAssertEqual(location.account, "openrouter")
        XCTAssertEqual(location.reference, "keychain:openrouter")
    }

    func testProviderIdentifiersAreTrimmedBeforeReferenceConstruction() {
        let location = CAPTProviderSecretConvention.location(providerID: "  openrouter  ")
        XCTAssertEqual(location.account, "openrouter")
        XCTAssertEqual(location.reference, "keychain:openrouter")
    }
}
