import SwiftUI
import CAPTCoreDesktop

struct EvidenceBrowserView: View {
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        List(store.evidenceItems) { item in
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(item.statement)
                        .font(.headline)
                        .lineLimit(2)
                    Spacer()
                    Text(item.promotionState.uppercased())
                        .font(.caption2.bold())
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(.quaternary, in: Capsule())
                }
                HStack(spacing: 16) {
                    Label("\(item.evidenceCount) evidence", systemImage: "doc.text.magnifyingglass")
                    Label(item.verificationStatus ?? "not verified", systemImage: "checkmark.seal")
                    Label(item.guardVerdict ?? "no claim decision", systemImage: "shield.lefthalf.filled")
                }
                .font(.caption)
                .foregroundStyle(.secondary)
                if let missionID = item.missionID {
                    Text(missionID)
                        .font(.caption2.monospaced())
                        .foregroundStyle(.tertiary)
                        .textSelection(.enabled)
                }
            }
            .padding(.vertical, 6)
        }
        .overlay {
            if store.evidenceItems.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "checkmark.seal").font(.system(size: 30))
                    Text("No claim evidence yet").font(.headline)
                    Text("Provider output appears here as evidence before verification or claim acceptance.")
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
            }
        }
        .onAppear { store.refreshHistory() }
    }
}
