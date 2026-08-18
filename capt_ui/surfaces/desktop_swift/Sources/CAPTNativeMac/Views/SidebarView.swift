import SwiftUI

enum CAPTSidebarSection: String, CaseIterable, Identifiable {
    case chat = "Chat"
    case missions = "Missions"
    case approvals = "Approvals"
    case providers = "Providers"
    case memory = "Memory"
    case evidence = "Evidence"
    case labs = "Labs"
    case runtime = "Runtime"
    case ledger = "Ledger"
    case settings = "Settings"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .chat: return "bubble.left.and.bubble.right"
        case .missions: return "scope"
        case .approvals: return "checkmark.circle.badge.questionmark"
        case .providers: return "cpu"
        case .memory: return "brain.head.profile"
        case .evidence: return "checkmark.seal"
        case .labs: return "flask"
        case .runtime: return "externaldrive.connected.to.line.below"
        case .ledger: return "list.bullet.rectangle.portrait"
        case .settings: return "gearshape"
        }
    }
}

struct SidebarView: View {
    @Binding var selection: CAPTSidebarSection
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        List(selection: $selection) {
            Section {
                Button {
                    store.newChat()
                    selection = .chat
                } label: {
                    Label("New Chat", systemImage: "square.and.pencil")
                }
            }

            if !store.sessions.isEmpty {
                Section("Recent Chats") {
                    ForEach(store.sessions.prefix(20)) { session in
                        Button {
                            store.activateSession(session.id)
                            selection = .chat
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                HStack(spacing: 6) {
                                    Text(session.title).lineLimit(1)
                                    if let pending = session.pendingApproval,
                                       pending.isActionable() {
                                        Image(systemName: "person.crop.circle.badge.checkmark")
                                            .font(.caption2)
                                            .foregroundStyle(.orange)
                                            .help("Approval required")
                                    }
                                }
                                Text(session.missionID.map(shortMission) ?? "Local draft")
                                    .font(.caption2.monospaced())
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .buttonStyle(.plain)
                        .listRowBackground(
                            store.activeSessionID == session.id
                                ? Color.accentColor.opacity(0.12) : Color.clear
                        )
                    }
                }
            }

            Section("CAPT") {
                ForEach(CAPTSidebarSection.allCases) { item in
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
            }
        }
        .listStyle(.sidebar)
        .navigationTitle("CAPT")
    }

    private func shortMission(_ id: String) -> String {
        id.count > 26 ? String(id.prefix(26)) + "…" : id
    }

    private func count(for item: CAPTSidebarSection) -> Int? {
        switch item {
        case .missions: return store.missions.count
        case .approvals: return store.pendingApprovals.count
        case .evidence: return store.evidenceItems.count
        case .labs: return store.labEngines.count
        case .ledger: return store.recentEvents.count
        default: return nil
        }
    }
}
