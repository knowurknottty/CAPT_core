import Foundation

public struct CAPTProviderSecretLocation: Equatable, Sendable {
    public let service: String
    public let account: String
    public let reference: String

    public init(service: String, account: String, reference: String) {
        self.service = service
        self.account = account
        self.reference = reference
    }
}

public enum CAPTProviderSecretConvention {
    public static let keychainService = "capt-provider"

    public static func location(providerID: String) -> CAPTProviderSecretLocation {
        let account = providerID.trimmingCharacters(in: .whitespacesAndNewlines)
        return CAPTProviderSecretLocation(
            service: keychainService,
            account: account,
            reference: "keychain:\(account)"
        )
    }
}
