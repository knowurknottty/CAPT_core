import SwiftUI
import CAPTCoreDesktop

struct StatusBarView: View {
    @ObservedObject var store: CAPTOperatorStore

    private var connectionTone: InversionTone {
        switch store.connectionState {
        case .connected: return .success
        case .connecting: return .amber
        case .failed: return .danger
        case .disconnected: return .neutral
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            InversionDivider()
            HStack(spacing: 10) {
                HStack(spacing: 6) {
                    Circle()
                        .fill(connectionTone.color)
                        .frame(width: 7, height: 7)
                    Text(store.connectionLabel)
                        .fontWeight(.medium)
                }

                statusDivider

                Label(store.provider, systemImage: "bolt.horizontal")
                    .lineLimit(1)
                Text(store.model)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .foregroundStyle(.secondary)

                if !store.providerWarmLabel.isEmpty {
                    InversionStatusBadge(
                        store.providerWarmLabel,
                        tone: store.providerWarmState == "failed" ? .danger : .cyan,
                        monospaced: true
                    )
                }

                if let issue = store.runtimeCompatibilityIssue {
                    InversionStatusBadge("RUNTIME API GAP", tone: .danger, monospaced: true)
                        .help(issue)
                } else if store.selectedProviderBlockedByNetworkAuthority {
                    InversionStatusBadge("NETWORK BLOCK", tone: .danger, monospaced: true)
                        .help("Selected provider requires remote network authority")
                }

                Spacer(minLength: 8)

                if store.isBusy {
                    ProgressView().controlSize(.mini)
                }

                HStack(spacing: 6) {
                    Text("PI")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(InversionTone.violet.color)
                    Text(store.promptIntelligence)
                        .font(.caption.monospaced().weight(.medium))
                }

                statusDivider

                InversionStatusBadge(
                    store.taskState == "—" ? "idle" : store.taskState,
                    tone: store.taskState == "—" ? .neutral : nil,
                    monospaced: true
                )
            }
            .font(.caption)
            .padding(.horizontal, 14)
            .padding(.vertical, 7)
            .background(.regularMaterial)
        }
    }

    private var statusDivider: some View {
        Rectangle()
            .fill(Color.primary.opacity(0.10))
            .frame(width: 1, height: 14)
    }
}
