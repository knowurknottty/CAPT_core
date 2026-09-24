import SwiftUI

struct ContentView: View {
    @ObservedObject var store: CAPTOperatorStore
    @Binding var selection: CAPTSidebarSection
    @State private var inspectorVisible = true

    var body: some View {
        NavigationSplitView {
            SidebarView(selection: $selection, store: store)
                .navigationSplitViewColumnWidth(min: 184, ideal: 224, max: 278)
        } detail: {
            VStack(spacing: 0) {
                if inspectorVisible {
                    HSplitView {
                        primaryView
                            .frame(minWidth: 590)
                        InspectorView(store: store)
                            .frame(minWidth: 284, idealWidth: 320, maxWidth: 390)
                    }
                } else {
                    primaryView
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
                StatusBarView(store: store)
            }
        }
        .toolbar {
            ToolbarItemGroup {
                Button { store.refreshAll() } label: {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
                .help("Refresh authoritative runtime state")

                Button { store.connect() } label: {
                    Label(
                        store.connectionState == .connected ? "Reconnect" : "Connect",
                        systemImage: "bolt.horizontal.circle"
                    )
                }
                .help("Connect to CAPT RuntimeService")

                Button { inspectorVisible.toggle() } label: {
                    Label(
                        inspectorVisible ? "Hide Inspector" : "Show Inspector",
                        systemImage: "sidebar.right"
                    )
                }
                .help(inspectorVisible ? "Hide operator inspector" : "Show operator inspector")
            }
        }
    }

    @ViewBuilder
    private var primaryView: some View {
        switch selection {
        case .chat:
            ChatView(store: store)
        case .missions:
            MissionBrowserView(store: store)
        case .bots:
            BotBrowserView(store: store)
        case .approvals:
            ApprovalQueueView(store: store)
        case .providers:
            ProviderControlView(store: store)
        case .skills:
            SkillsView(store: store, selection: $selection)
        case .memory:
            MemoryContextView(store: store)
        case .evidence:
            EvidenceBrowserView(store: store)
        case .ledger:
            LedgerView(store: store)
        case .runtime:
            RuntimeControlView(store: store)
        case .settings:
            SettingsView(store: store)
        }
    }
}
