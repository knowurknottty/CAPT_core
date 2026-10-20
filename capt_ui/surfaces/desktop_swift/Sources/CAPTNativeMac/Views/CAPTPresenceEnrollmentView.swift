import AppKit
import CryptoKit
import SwiftUI
import CAPTCoreDesktop

/// Explicit, local-only enrollment ceremony entrypoint.
/// This screen does NOT register an operator identity with RuntimeService.
struct CAPTPresenceEnrollmentView: View {
    @State private var keyID = "operator-primary"
    @State private var busy = false
    @State private var fingerprint: String?
    @State private var publicKeyPEM: String?
    @State private var message = "No CAPT governance registration has been performed."

    var body: some View {
        InversionPanel(tone: .amber) {
            VStack(alignment: .leading, spacing: 12) {
                InversionSectionHeader(
                    "Operator presence (UPG-041 preview)",
                    detail: "Create a device-bound, Touch ID-protected signing key. This is only the first stage of enrollment; generating the key never grants CAPT permission.",
                    symbol: "touchid", tone: .amber
                )
                TextField("Local key identifier", text: $keyID)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 360)

                Button {
                    enrollFromExplicitUserAction()
                } label: {
                    Label("Create Secure Enclave key", systemImage: "touchid")
                }
                .disabled(busy)
                .help("Uses the current device biometric set and creates a non-exportable P-256 private key.")

                if let fingerprint {
                    InversionKeyValueRow(
                        "Unregistered public-key SHA-256",
                        value: fingerprint,
                        tone: .amber, monospaced: true
                    )
                    Button("Copy unregistered public key (PEM)") {
                        guard let publicKeyPEM else { return }
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(publicKeyPEM, forType: .string)
                    }
                    .help("The public key is not a certificate, attestation, or approved CAPT registration.")
                }
                Text(message)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Label(
                    "Issuer authentication remains disabled: runtime enrollment, one-time challenge consumption, independent key custody and dispatch binding are not yet implemented.",
                    systemImage: "exclamationmark.shield"
                )
                .font(.caption)
                .foregroundStyle(.secondary)
            }
        }
    }

    private func enrollFromExplicitUserAction() {
        guard !busy else { return }
        busy = true
        let key = keyID
        message = "Requesting a device-protected key. No CAPT approval is being issued."
        Task.detached(priority: .userInitiated) {
            let result: Result<CAPTSecureEnclavePresence.Enrollment, Error>
            do {
                result = .success(try CAPTSecureEnclavePresence.enrollExplicitly(keyId: key))
            } catch {
                result = .failure(error)
            }
            await MainActor.run {
                busy = false
                switch result {
                case .success(let enrollment):
                    publicKeyPEM = enrollment.publicKeyPEM
                    fingerprint = SHA256.hash(data: Data(enrollment.publicKeyPEM.utf8))
                        .map { String(format: "%02x", $0) }.joined()
                    message = "Local key created; public key not registered with CAPT. No issuer privilege exists."
                case .failure:
                    message = "Secure Enclave enrollment refused or unavailable. Existing keys are never overwritten; check device biometric availability and app signing."
                }
            }
        }
    }
}
