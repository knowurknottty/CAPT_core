import SwiftUI
import CAPTCoreDesktop

struct LedgerView: View {
    @ObservedObject var store: CAPTOperatorStore
    @State private var showTransportPhases = false
    @State private var showOnlyDecisions = false
    @State private var searchText = ""

    private var visibleEvents: [CAPTEventSummary] {
        store.recentEvents.filter { event in
            (showTransportPhases || !CAPTLedgerSemantics.transportNoise.contains(event.type)) &&
            (!showOnlyDecisions || CAPTLedgerSemantics.isDecisionOrResult(event)) &&
            (searchText.isEmpty || event.type.localizedCaseInsensitiveContains(searchText) ||
             event.streamID.localizedCaseInsensitiveContains(searchText) ||
             (event.missionID ?? "").localizedCaseInsensitiveContains(searchText) ||
             String(event.sequence).contains(searchText))
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Event Ledger").font(.title2.bold())
                    Text("What CAPT actually recorded · chronological evidence, not current task status")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Refresh") { store.refreshHistory() }
            }.padding(.horizontal, 18).padding(.top, 12)
            TextField("Search event, stream, mission, or sequence", text: $searchText)
                .textFieldStyle(.roundedBorder)
                .accessibilityIdentifier("ledger-search")
                .padding(.horizontal, 18)
            HStack(spacing: 14) {
                Toggle("Decisions and results only", isOn: $showOnlyDecisions)
                Toggle("Show tool transport phases", isOn: $showTransportPhases)
            }
                .toggleStyle(.switch).controlSize(.small)
                .padding(.horizontal, 18).padding(.vertical, 10)
            Text("\(visibleEvents.count) shown · latest \(store.recentEvents.count) of the immutable ledger · filtering does not delete history")
                .font(.caption).foregroundStyle(.secondary).padding(.bottom, 4)
            List(visibleEvents) { event in
            HStack(alignment: .top, spacing: 12) {
                Text("#\(event.sequence)")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .frame(width: 58, alignment: .trailing)
                VStack(alignment: .leading, spacing: 4) {
                    Text(CAPTLedgerSemantics.readableName(event.type)).font(.callout.weight(.semibold))
                    if CAPTLedgerSemantics.readableName(event.type) != event.type {
                        Text(event.type).font(.caption2.monospaced()).foregroundStyle(.tertiary)
                    }
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
                    Text("No matching ledger events").font(.headline)
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
