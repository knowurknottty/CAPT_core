import SwiftUI

enum CAPTSidebarSection: String, CaseIterable, Identifiable {
    case chat = "Chat"
    case missions = "Missions"
    case bots = "Bots"
    case approvals = "Approvals"
    case providers = "Providers"
    case skills = "Skills"
    case memory = "Memory"
    case evidence = "Evidence"
    case runtime = "Runtime"
    case ledger = "Ledger"
    case settings = "Settings"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .chat: return "bubble.left.and.bubble.right"
        case .missions: return "scope"
        case .bots: return "person.2"
        case .approvals: return "checkmark.circle.badge.questionmark"
        case .providers: return "cpu"
        case .skills: return "puzzlepiece.extension"
        case .memory: return "brain.head.profile"
        case .evidence: return "checkmark.seal"
        case .runtime: return "externaldrive.connected.to.line.below"
        case .ledger: return "list.bullet.rectangle.portrait"
        case .settings: return "gearshape"
        }
    }

    var tone: InversionTone {
        switch self {
        case .bots: return .cyan
        case .approvals: return .amber
        case .skills: return .violet
        case .evidence: return .cyan
        case .runtime: return .success
        case .settings: return .violet
        default: return .neutral
        }
    }
}

struct SidebarView: View {
    @Binding var selection: CAPTSidebarSection
    @ObservedObject var store: CAPTOperatorStore

    var body: some View {
        List(selection: $selection) {
            Section {
                HStack {
                    InversionBrandMark()
                    Spacer()
                    Circle()
                        .fill(connectionTone.color)
                        .frame(width: 7, height: 7)
                        .shadow(color: connectionTone.color.opacity(0.35), radius: 3)
                        .help(store.connectionLabel)
                }
                .padding(.vertical, 6)
                .listRowSeparator(.hidden)

                Button {
                    store.newChat()
                    selection = .chat
                } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "plus")
                            .font(.system(size: 11, weight: .bold))
                            .frame(width: 22, height: 22)
                            .background(InversionTone.amber.color.opacity(0.12), in: Circle())
                            .foregroundStyle(InversionTone.amber.color)
                        Text("New Chat")
                            .fontWeight(.semibold)
                        Spacer()
                        Text("⌘N")
                            .font(.caption2.monospaced())
                            .foregroundStyle(.tertiary)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .padding(.vertical, 2)
            }

            Section {
                ForEach(CAPTSidebarSection.allCases) { item in
                    HStack(spacing: 9) {
                        Image(systemName: item.systemImage)
                            .symbolRenderingMode(.hierarchical)
                            .foregroundStyle(
                                selection == item && item.tone != .neutral
                                    ? item.tone.color : Color.secondary
                            )
                            .frame(width: 18)
                        Text(item.rawValue)
                        Spacer()
                        if let count = count(for: item), count > 0 {
                            Text("\(count)")
                                .font(.caption2.monospacedDigit().weight(.medium))
                                .foregroundStyle(.secondary)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.primary.opacity(0.055), in: Capsule())
                        }
                    }
                    .tag(item)
                }
            } header: {
                Text("CONTROL PLANE")
                    .font(.caption2.weight(.semibold))
                    .tracking(1.15)
            }

            if !store.sessions.isEmpty {
                Section {
                    ForEach(store.sessions.prefix(8)) { session in
                        Button {
                            store.activateSession(session.id)
                            selection = .chat
                        } label: {
                            VStack(alignment: .leading, spacing: 3) {
                                HStack(spacing: 6) {
                                    Text(session.title)
                                        .lineLimit(1)
                                        .font(.callout.weight(
                                            store.activeSessionID == session.id ? .semibold : .regular
                                        ))
                                    Spacer(minLength: 2)
                                    if let pending = session.pendingApproval,
                                       pending.isActionable() {
                                        Circle()
                                            .fill(InversionTone.amber.color)
                                            .frame(width: 6, height: 6)
                                            .help("Approval required")
                                    }
                                }
                                Text(session.missionID.map(shortMission) ?? "local draft")
                                    .font(.caption2.monospaced())
                                    .foregroundStyle(.tertiary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .listRowBackground(
                            store.activeSessionID == session.id
                                ? Color.primary.opacity(0.055) : Color.clear
                        )
                    }
                } header: {
                    Text("RECENT")
                        .font(.caption2.weight(.semibold))
                        .tracking(1.15)
                }
            }
        }
        .listStyle(.sidebar)
        .navigationTitle("CAPT")
    }

    private var connectionTone: InversionTone {
        switch store.connectionState {
        case .connected: return .success
        case .connecting: return .amber
        case .failed: return .danger
        case .disconnected: return .neutral
        }
    }

    private func shortMission(_ id: String) -> String {
        id.count > 26 ? String(id.prefix(26)) + "…" : id
    }

    private func count(for item: CAPTSidebarSection) -> Int? {
        switch item {
        case .missions: return store.missions.filter(\.isMultiTask).count
        case .bots: return store.bots.count
        case .approvals: return store.pendingApprovals.count
        case .skills: return store.managedSkills?.skills.count
        case .evidence: return store.evidenceItems.count
        case .ledger: return store.recentEvents.count
        default: return nil
        }
    }
}
