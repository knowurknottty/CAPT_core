import SwiftUI
import CAPTCoreDesktop

struct LedgerView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        List(store.recentEvents) { event in
            HStack(alignment: .top, spacing: 12) {
                Text("#\(event.sequence)")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .frame(width: 58, alignment: .trailing)
                VStack(alignment: .leading, spacing: 4) {
                    Text(event.type).font(.headline)
                    HStack(spacing: 8) {
                        Text(event.actorKind)
                        if let missionID = event.missionID {
                            Text(shortID(missionID)).monospaced()
                        }
                        Text(event.occurredAt)
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    Text(event.streamID)
                        .font(.caption2.monospaced())
                        .foregroundStyle(.tertiary)
                }
            }
            .padding(.vertical, 4)
        }
        .overlay {
            if store.recentEvents.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "list.bullet.rectangle.portrait")
                        .font(.system(size: 30))
                    Text("No runtime events loaded").font(.headline)
                    Text("Reconnect or refresh to project the authoritative EventStore timeline.")
                        .foregroundStyle(.secondary)
                }
            }
        }
        .onAppear { store.refreshHistory() }
    }

    private func shortID(_ value: String) -> String {
        value.count > 14 ? "…" + value.suffix(13) : value
    }
}
