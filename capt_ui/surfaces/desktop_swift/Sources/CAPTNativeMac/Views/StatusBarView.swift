import SwiftUI
import CAPTCoreDesktop

struct StatusBarView: View {
    @ObservedObject var store: CAPTOperatorStore

    private var indicator: Color {
        switch store.connectionState {
        case .connected: return .green
        case .connecting: return .yellow
        case .failed: return .red
        case .disconnected: return .secondary
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(indicator)
                .frame(width: 8, height: 8)
            Text(store.connectionLabel)
            Divider().frame(height: 14)
            Label(store.provider, systemImage: "bolt.horizontal")
            Text(store.model)
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
            if store.isBusy { ProgressView().controlSize(.small) }
            Text(store.taskState)
                .foregroundStyle(.secondary)
        }
        .font(.caption)
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
        .background(.bar)
    }
}
