import SwiftUI

enum CAPTSidebarSection: String, CaseIterable, Identifiable {
    case chat = "Chat"
    case missions = "Missions"
    case providers = "Providers"
    case evidence = "Evidence"
    case settings = "Settings"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .chat: return "bubble.left.and.bubble.right"
        case .missions: return "scope"
        case .providers: return "cpu"
        case .evidence: return "checkmark.seal"
        case .settings: return "gearshape"
        }
    }
}

struct SidebarView: View {
    @Binding var selection: CAPTSidebarSection

    var body: some View {
        List(CAPTSidebarSection.allCases, selection: $selection) { item in
            Label(item.rawValue, systemImage: item.systemImage)
                .tag(item)
        }
        .listStyle(.sidebar)
        .navigationTitle("CAPT")
    }
}
