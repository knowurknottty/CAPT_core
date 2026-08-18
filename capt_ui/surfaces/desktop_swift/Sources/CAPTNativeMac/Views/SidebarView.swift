import SwiftUI

enum CAPTSidebarSection: String, CaseIterable, Identifiable {
    case chat = "Chat"
    case missions = "Missions"
    case providers = "Providers"
    case evidence = "Evidence"
    case ledger = "Ledger"
    case settings = "Settings"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .chat: return "bubble.left.and.bubble.right"
        case .missions: return "scope"
        case .providers: return "cpu"
        case .evidence: return "checkmark.seal"
        case .ledger: return "list.bullet.rectangle.portrait"
        case .settings: return "gearshape"
        }
    }
}

struct SidebarView: View {
    @Binding var selection: CAPTSidebarSection
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        List(CAPTSidebarSection.allCases, selection: $selection) { item in
            HStack {
                Label(item.rawValue, systemImage: item.systemImage)
                Spacer()
                if let count = count(for: item), count > 0 {
                    Text("\(count)")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
                .tag(item)
        }
        .listStyle(.sidebar)
        .navigationTitle("CAPT")
    }

    private func count(for item: CAPTSidebarSection) -> Int? {
        switch item {
        case .missions: return store.missions.count
        case .evidence: return store.evidenceItems.count
        case .ledger: return store.recentEvents.count
        default: return nil
        }
    }
}
