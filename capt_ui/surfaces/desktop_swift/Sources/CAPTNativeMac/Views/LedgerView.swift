import SwiftUI
import CAPTCoreDesktop

struct LedgerView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var showTransportPhases = false

    private let routinePhases: Set<String> = [
        "ToolExecutionPrepared", "ToolExecutionAdmitted",
        "ToolExecutionDispatching", "ToolExecutionSettling",
    ]

    private var visibleEvents: [CAPTEventSummary] {
        showTransportPhases ? store.recentEvents : store.recentEvents.filter {
            !routinePhases.contains($0.type)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            Toggle("Show routine tool transport phases", isOn: $showTransportPhases)
                .toggleStyle(.switch).controlSize(.small)
                .padding(.horizontal, 18).padding(.vertical, 10)
            Text("\(visibleEvents.count) shown from the latest \(store.recentEvents.count) events · all events remain in the immutable ledger")
                .font(.caption).foregroundStyle(.secondary).padding(.bottom, 4)
            List(visibleEvents) { event in
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
            if visibleEvents.isEmpty {
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
    }

    private func shortID(_ value: String) -> String {
        value.count > 14 ? "…" + value.suffix(13) : value
    }
}
